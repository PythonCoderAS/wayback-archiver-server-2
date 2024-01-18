import asyncio
import datetime
import os
import re
from contextlib import asynccontextmanager
from os import environ
from traceback import print_exc
from typing import (
    Annotated,
    Awaitable,
    Callable,
    Generic,
    Literal,
    TypedDict,
    TypeVar,
    overload,
)

import sqlalchemy
import sqlalchemy.ext.asyncio
from aiohttp import ClientSession
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select, update
import sentry_sdk
from .models import Job, Batch, URL, RepeatURL
from .routes import load_routes

sentry_sdk.init(
    dsn="https://84178a5ce2503fced1fc13675fff0f4a@o494335.ingest.sentry.io/4506498048589824",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,
)

archive_url_regex = re.compile(r"/web/(\d{14})")


def get_archive_save_url_timestamp(timestamp: str) -> datetime.datetime:
    return datetime.datetime.strptime(timestamp, "%Y%m%d%H%M%S").replace(
        tzinfo=datetime.timezone.utc
    )


# Constants
min_wait_time_between_archives = datetime.timedelta(hours=1)

engine: sqlalchemy.ext.asyncio.AsyncEngine = None
async_session: sqlalchemy.ext.asyncio.async_sessionmaker[
    sqlalchemy.ext.asyncio.AsyncSession
] = None
client_session: ClientSession = None


async def get_current_job(
    curtime=None,
    *,
    session: sqlalchemy.ext.asyncio.AsyncSession | None = None,
    get_batches: bool = False,
) -> Job | None:
    if not curtime:
        curtime = datetime.datetime.now(tz=datetime.timezone.utc)
    stmt = (
        select(Job)
        .where(
            ((Job.delayed_until <= curtime) | (Job.delayed_until == None))
            & (Job.completed == None)
            & (Job.failed == None)
        )
        .order_by(Job.priority.desc(), Job.retry.desc(), Job.id)
        .limit(1)
    )
    if get_batches:
        stmt = stmt.options(sqlalchemy.orm.joinedload(Job.batches))
    if session is None:
        async with async_session() as session, session.begin():
            result = await session.scalars(stmt)
            return result.first()
    else:
        async with session.begin():
            result = await session.scalars(stmt)
            return result.first()


async def exception_logger(coro: Awaitable, name="coroutine"):
    try:
        await coro
    except Exception:
        print(f"Exception in {name}:")
        print_exc()
        raise


async def url_worker():
    global client_session
    while True:
        curtime = datetime.datetime.now(tz=datetime.timezone.utc)
        async with async_session() as session:
            next_job = await get_current_job(curtime=curtime, session=session)
            if next_job is None:
                await asyncio.sleep(1)
                continue
            # First, make sure that we don't have to delay this URL (only one capture per min_wait_time_between_archives)
            if (
                next_job.url.last_seen
                and next_job.url.last_seen + min_wait_time_between_archives > curtime
            ):
                next_queue_time: datetime.datetime = (
                    next_job.url.last_seen + min_wait_time_between_archives
                )
                print(
                    f"Re-querying job id={next_job.id} until {next_queue_time.strftime('%c')}. Last seen at {next_job.url.last_seen.strftime('%c')}."
                )
                async with session.begin():
                    stmt = (
                        update(Job)
                        .where(Job.id == next_job.id)
                        .values(delayed_until=next_queue_time)
                    )
                    await session.execute(stmt)
                continue
            if client_session is None:
                client_session = ClientSession()
            for retry_num in range(5):  # " Up to 4 retries (5 attempts total)
                try:
                    async with client_session.get(
                        "https://web.archive.org/save/" + next_job.url.url,
                        allow_redirects=False,
                    ) as resp:
                        resp.raise_for_status()
                        if match := archive_url_regex.search(
                            resp.headers.get("Location", "")
                        ):
                            saved_dt = get_archive_save_url_timestamp(match.group(1))
                            async with session.begin():
                                await session.execute(
                                    update(URL)
                                    .where(URL.id == next_job.url.id)
                                    .values(last_seen=saved_dt)
                                )
                                await session.execute(
                                    update(Job)
                                    .where(Job.id == next_job.id)
                                    .values(
                                        completed=saved_dt,
                                        failed=None,
                                        delayed_until=None,
                                    )
                                )
                            break
                except Exception:
                    print("Skipping exception during URL archiving:")
                    print_exc()
                await asyncio.sleep(10 * pow(2, retry_num))
            else:  # Ran out of retries, try again
                async with session.begin():
                    if next_job.retry < 4:
                        print(
                            f"Retrying job id={next_job.id} for the {next_job.retry + 1} time."
                        )
                        await session.execute(
                            update(Job)
                            .where(Job.id == next_job.id)
                            .values(
                                retry=next_job.retry + 1,
                                delayed_until=curtime + min_wait_time_between_archives,
                            )
                        )
                    else:
                        await session.execute(
                            update(Job)
                            .where(Job.id == next_job.id)
                            .values(failed=curtime, delayed_until=None)
                        )


async def repeat_url_worker():
    batch = None
    created_at: datetime.datetime = None
    while True:
        curtime = datetime.datetime.now(tz=datetime.timezone.utc)
        async with async_session() as session, session.begin():
            stmt = (
                select(RepeatURL)
                .where(RepeatURL.active_since <= curtime)
                .order_by(RepeatURL.id)
            )
            result = await session.scalars(stmt)
            jobs = result.all()
            stmt2 = (
                select(URL.url)
                .join(Job)
                .where(
                    URL.url.in_([job.url.url for job in jobs])
                    & (Job.completed == None)
                    & (Job.failed == None)
                )
            )
            result = await session.scalars(stmt2)
            existing_jobs = result.all()
            queued: list[Job] = []
            for job in jobs:
                if (
                    not job.url.last_seen
                    or job.url.last_seen + datetime.timedelta(seconds=job.interval)
                    < curtime
                ) and job.url.url not in existing_jobs:  # Job can be re-queued
                    if batch is None or (
                        created_at + datetime.timedelta(minutes=30) < curtime
                    ):
                        async with session.begin_nested():
                            batch = Batch()
                            created_at = curtime
                            session.add(batch)
                    queued.append(
                        Job(url=job.url, priority=10, batches=[batch, job.batch])
                    )
            if queued:
                session.add_all(queued)
        await asyncio.sleep(60)


workers: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(_: FastAPI):
    global engine, async_session
    if engine is None:
        engine = sqlalchemy.ext.asyncio.create_async_engine(
            environ.get("DATABASE_URL", "sqlite:///db.sqlite")
        )
    async_session = sqlalchemy.ext.asyncio.async_sessionmaker(
        engine, expire_on_commit=False
    )
    workers.append(
        asyncio.create_task(exception_logger(url_worker(), name="url_worker"))
    )
    workers.append(
        asyncio.create_task(
            exception_logger(repeat_url_worker(), name="repeat_url_worker")
        )
    )
    load_routes()
    try:
        yield
    finally:
        for worker in workers:
            worker.cancel()
        if engine:
            await engine.dispose()


app = FastAPI(lifespan=lifespan)
os.makedirs("frontend/dist", exist_ok=True)
static_files = StaticFiles(directory="frontend/dist", html=True)
app.mount("/app", static_files, name="frontend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Serves /index.html if we are in /app and there is a 404
@app.middleware("http")
async def spa_middleware(
    req: Request, call_next: Callable[[Request], Awaitable[Response]]
):
    resp = await call_next(req)
    if resp.status_code == 404 and req.url.path.startswith("/app"):
        # Note: Find a better way to do this!
        req.scope["path"] = "/app/index.html"
        resp = await call_next(req)
    return resp


redirect_map: dict[str, str] = {
    "/queue_batch": "/queue/batch",
    "/queue_loop": "/queue/loop",
    "/current_job": "/job/current",
    "/jobs": "/job",
    "/batches": "/batch",
    "/repeat_urls": "/repeat_url",
    "/urls": "/url",
}

regex_redirect_map: dict[re.Pattern, str] = {
    # re.compile(r"^/job/(\d+)$"): r"/job/\1", # Example
}


@app.middleware("http")
async def redirect_middleware(
    req: Request, call_next: Callable[[Request], Awaitable[Response]]
):
    # Only check for redirect if 404
    resp = await call_next(req)
    if resp.status_code == 404:
        if req.url.path in redirect_map:
            return Response(
                status_code=307, headers={"Location": redirect_map[req.url.path]}
            )
        for regex, replacement in regex_redirect_map.items():
            if match := regex.match(req.url.path):
                return Response(
                    status_code=307,
                    headers={"Location": match.expand(replacement)},
                )
    return resp


class PaginationInfo(BaseModel):
    current_page: int
    total_pages: int
    items: int


ModelT = TypeVar("ModelT", bound=BaseModel)


class PaginationOutput(BaseModel, Generic[ModelT]):
    data: list[ModelT]
    pagination: PaginationInfo


Page = Annotated[
    int, Query(title="Page", description="The page of results you want", ge=1, le=100)
]


class PaginationDefaultQueryArgs(TypedDict):
    page: Page
    after: datetime.datetime | None
    desc: bool


async def pagination_default_query_args(
    page: Page = 1, after: datetime.datetime | None = None, desc: bool = False
) -> PaginationDefaultQueryArgs:
    return {"page": page, "after": after, "desc": desc}


PaginationQueryArgs = Annotated[
    PaginationDefaultQueryArgs, Depends(pagination_default_query_args)
]


class JobPaginationDefaultQueryArgs(PaginationDefaultQueryArgs):
    not_started: bool
    completed: bool
    delayed: bool
    failed: bool
    retries_less_than: Literal[1, 2, 3, 4] | None
    retries_greater_than: Literal[0, 1, 2, 3] | None
    retries_equal_to: Literal[0, 1, 2, 3, 4] | None


async def job_pagination_default_query_args(
    page: Page = 1,
    after: datetime.datetime | None = None,
    desc: bool = False,
    not_started: bool = True,
    completed: bool = True,
    delayed: bool = True,
    failed: bool = True,
    retries_less_than: Literal[1, 2, 3, 4] | None = None,
    retries_greater_than: Literal[0, 1, 2, 3] | None = None,
    retries_equal_to: Literal[0, 1, 2, 3, 4] | None = None,
) -> JobPaginationDefaultQueryArgs:
    return {
        "page": page,
        "after": after,
        "desc": desc,
        "not_started": not_started,
        "completed": completed,
        "delayed": delayed,
        "failed": failed,
        "retries_less_than": retries_less_than,
        "retries_greater_than": retries_greater_than,
        "retries_equal_to": retries_equal_to,
    }


JobPaginationQueryArgs = Annotated[
    JobPaginationDefaultQueryArgs, Depends(job_pagination_default_query_args)
]


@overload
def apply_job_filtering(
    query_params: JobPaginationDefaultQueryArgs, is_count_query: Literal[True], /
) -> sqlalchemy.Select[tuple[int]]:
    ...


@overload
def apply_job_filtering(
    query_params: JobPaginationDefaultQueryArgs, is_count_query: Literal[False], /
) -> sqlalchemy.Select[tuple[Job]]:
    ...


def apply_job_filtering(
    query_params: JobPaginationDefaultQueryArgs, is_count_query: bool = False, /
) -> sqlalchemy.Select:
    in_statement = select(sqlalchemy.func.count(Job.id) if is_count_query else Job)
    if (
        len(
            {
                query_params["not_started"],
                query_params["completed"],
                query_params["delayed"],
                query_params["failed"],
            }
        )
        != 1
    ):  # If they are all the same, we can take a shortcut and not apply anything
        # If all 4 are given, we can take a shortcut and not apply anything
        if query_params["not_started"]:
            in_statement = in_statement.where(
                (Job.completed == None)
                & (Job.failed == None)
                & (Job.delayed_until == None)
            )
        if query_params["completed"]:
            in_statement = in_statement.where(Job.completed != None)
        if query_params["delayed"]:
            in_statement = in_statement.where(Job.delayed_until != None)
        if query_params["failed"]:
            in_statement = in_statement.where(Job.failed != None)
    retry_param_count = [
        query_params["retries_less_than"],
        query_params["retries_greater_than"],
        query_params["retries_equal_to"],
    ].count(None)
    if retry_param_count <= 2:
        raise HTTPException(
            status_code=400,
            detail="You must provide only one of retries_less_than, retries_greater_than, or retries_equal_to",
        )
    elif retry_param_count != 3:
        if query_params["retries_less_than"] is not None:
            in_statement = in_statement.where(
                Job.retry < query_params["retries_less_than"]
            )
        if query_params["retries_greater_than"] is not None:
            in_statement = in_statement.where(
                Job.retry > query_params["retries_greater_than"]
            )
        if query_params["retries_equal_to"] is not None:
            in_statement = in_statement.where(
                Job.retry == query_params["retries_equal_to"]
            )
    if query_params["after"]:
        in_statement = in_statement.where(Job.created_at > query_params["after"])
    if not is_count_query:
        in_statement = (
            in_statement.limit(100)
            .order_by(Job.id.desc() if query_params["desc"] else Job.id.asc())
            .offset((query_params["page"] - 1) * 100)
        )
    return in_statement
