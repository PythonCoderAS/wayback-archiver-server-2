import asyncio
from contextlib import asynccontextmanager
import datetime
from os import environ
import re
from typing import Annotated, Awaitable, Callable, Generic, Literal, TypeVar, TypedDict, overload
from traceback import print_exc
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.ext.asyncio
from sqlalchemy import select, update
from sqlalchemy.orm import Mapped, mapped_column
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response
from aiohttp import ClientSession

engine: sqlalchemy.ext.asyncio.AsyncEngine = None
async_session: sqlalchemy.ext.asyncio.async_sessionmaker[sqlalchemy.ext.asyncio.AsyncSession] = None
client_session: ClientSession = None

class Base(sqlalchemy.orm.MappedAsDataclass, sqlalchemy.ext.asyncio.AsyncAttrs, sqlalchemy.orm.DeclarativeBase):
    pass

class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    created_at: Mapped[datetime.datetime] = mapped_column(sqlalchemy.DateTime(timezone=True), server_default=sqlalchemy.sql.func.now(), nullable=False, init=False, index=True)

    jobs: Mapped[list["Job"]] = sqlalchemy.orm.relationship("Job", secondary="batch_jobs", back_populates="batches", init=False, repr=False)

class URL(Base):
    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    url: Mapped[str] = mapped_column(sqlalchemy.String(length=10000), unique=True, index=True)
    first_seen: Mapped[datetime.datetime] = mapped_column(sqlalchemy.DateTime(timezone=True), server_default=sqlalchemy.sql.func.now(), nullable=False, init=False, index=True)
    jobs: Mapped[list["Job"]] = sqlalchemy.orm.relationship("Job", back_populates="url", init=False, repr=False)
    last_seen: Mapped[datetime.datetime | None] = mapped_column(sqlalchemy.DateTime(timezone=True), default=None, nullable=True, index=True)

class RepeatURL(Base):
    __tablename__ = "repeat_urls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    url_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey(URL.id), nullable=False, unique=True, init=False)
    url: Mapped[URL] = sqlalchemy.orm.relationship(URL, lazy="joined", innerjoin=True, foreign_keys=[url_id])
    created_at: Mapped[datetime.datetime] = mapped_column(sqlalchemy.DateTime(timezone=True), server_default=sqlalchemy.sql.func.now(), nullable=False, init=False, index=True)
    batch_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey(Batch.id), nullable=False, unique=True, init=False)
    batch: Mapped[Batch] = sqlalchemy.orm.relationship(Batch, lazy="joined", innerjoin=True, foreign_keys=[batch_id])
    interval: Mapped[int] = mapped_column(default=3600 * 4)
    active_since: Mapped[datetime.datetime | None] = mapped_column(sqlalchemy.DateTime(timezone=True), server_default=sqlalchemy.sql.func.now(), nullable=True, index=True, init=False) # Indicates that a repeat URL is active

class BatchJobs(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[int] = mapped_column(sqlalchemy.BigInteger, primary_key=True, autoincrement=True, init=False)
    batch_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey(Batch.id), primary_key=True)
    job_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey("jobs.id"), primary_key=True)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(sqlalchemy.BigInteger, primary_key=True, autoincrement=True, init=False)
    batches: Mapped[list[Batch]] = sqlalchemy.orm.relationship(Batch, secondary="batch_jobs", back_populates="jobs")
    url_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey(URL.id), nullable=False, init=False, repr=False)
    url: Mapped[URL] = sqlalchemy.orm.relationship(URL, lazy="joined", innerjoin=True, foreign_keys=[url_id], back_populates="jobs")
    created_at: Mapped[datetime.datetime] = mapped_column(sqlalchemy.DateTime(timezone=True), server_default=sqlalchemy.sql.func.now(), nullable=False, init=False, index=True)
    completed: Mapped[datetime.datetime | None] = mapped_column(sqlalchemy.DateTime(timezone=True), default=None, nullable=True, index=True)
    delayed_until: Mapped[datetime.datetime | None] = mapped_column(sqlalchemy.DateTime(timezone=True), default=None, nullable=True, index=True) # If a job needs to be delayed, this is the time it should be run at
    priority: Mapped[int] = mapped_column(default=0)
    retry: Mapped[int] = mapped_column(sqlalchemy.SmallInteger, default=0) # Number of times this job has been retried
    failed: Mapped[datetime.datetime | None] = mapped_column(sqlalchemy.DateTime(timezone=True), default=None, nullable=True, index=True) # If a job has failed, this is the time it failed at

async def get_current_job(curtime=None, *, session: sqlalchemy.ext.asyncio.AsyncSession | None = None, get_batches: bool = False) -> Job | None:
    if not curtime:
        curtime = datetime.datetime.now(tz=datetime.timezone.utc)
    stmt = select(Job).where(((Job.delayed_until <= curtime) | (Job.delayed_until == None)) & (Job.completed == None) & (Job.failed == None)).order_by(Job.priority.desc(), Job.retry.desc(), Job.id).limit(1)
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
            # First, make sure that we don't have to delay this URL (only one capture per 45 minutes)
            if next_job.url.last_seen and next_job.url.last_seen + datetime.timedelta(minutes=45) > curtime:
                print(f"Re-querying job id={next_job.id} for 45 minutes. Last seen at {next_job.url.last_seen}. Current time: {curtime}")
                async with session.begin():
                    stmt = update(Job).where(Job.id == next_job.id).values(delayed_until=next_job.url.last_seen + datetime.timedelta(minutes=45))
                    await session.execute(stmt)
                continue
            if client_session is None:
                client_session = ClientSession()
            for _ in range(5): #" Up to 4 retries (5 attempts total)
                try:
                    async with client_session.get("https://web.archive.org/save/" + next_job.url.url, allow_redirects=False) as resp:
                        resp.raise_for_status()
                        if match := re.search(r"/web/(\d{14})", resp.headers.get("Location", "")):
                            saved_dt = datetime.datetime.strptime(match.group(1), "%Y%m%d%H%M%S").replace(tzinfo=datetime.timezone.utc)
                            async with session.begin():
                                await session.execute(update(URL).where(URL.id == next_job.url.id).values(last_seen=saved_dt))
                                await session.execute(update(Job).where(Job.id == next_job.id).values(completed=saved_dt, failed=None, delayed_until=None))
                            break
                except Exception:
                    print("Skipping exception during URL archiving:")
                    print_exc()
                await asyncio.sleep(30)
            else: # Ran out of retries, try again
                async with session.begin():
                    if next_job.retry < 4:
                        print(f"Retrying job id={next_job.id} for the {next_job.retry + 1} time.")
                        await session.execute(update(Job).where(Job.id == next_job.id).values(retry=next_job.retry + 1, delayed_until=curtime + datetime.timedelta(minutes=45)))
                    else:
                        await session.execute(update(Job).where(Job.id == next_job.id).values(failed=curtime, delayed_until=None))

async def repeat_url_worker():
    batch = None
    created_at: datetime.datetime = None
    while True:
        curtime = datetime.datetime.now(tz=datetime.timezone.utc)
        async with async_session() as session, session.begin():
            stmt = select(RepeatURL).where(RepeatURL.active_since <= curtime).order_by(RepeatURL.id)
            result = await session.scalars(stmt)
            jobs = result.all()
            stmt2 = select(URL.url).join(Job).where(URL.url.in_([job.url.url for job in jobs]) & (Job.completed == None) & (Job.failed == None))
            result = await session.scalars(stmt2)
            existing_jobs = result.all()
            queued: list[Job] = []
            for job in jobs:
                if (not job.url.last_seen or job.url.last_seen + datetime.timedelta(seconds=job.interval) < curtime) and job.url.url not in existing_jobs: # Job can be re-queued
                    if batch is None or (created_at + datetime.timedelta(minutes=30) < curtime):
                        async with session.begin_nested():
                            batch = Batch()
                            created_at = curtime
                            session.add(batch)
                    queued.append(Job(url=job.url, priority=10, batches=[batch, job.batch]))
            if queued:
                session.add_all(queued)
        await asyncio.sleep(60)



@asynccontextmanager
async def lifespan(_: FastAPI):
    global engine, async_session, cache
    if engine is None:
        engine = sqlalchemy.ext.asyncio.create_async_engine(environ.get("DATABASE_URL", "sqlite:///db.sqlite"))
    async_session = sqlalchemy.ext.asyncio.async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    workers.append(asyncio.create_task(exception_logger(url_worker(), name="url_worker")))
    workers.append(asyncio.create_task(exception_logger(repeat_url_worker(), name="repeat_url_worker")))
    try:
        yield
    finally:
        for worker in workers:
            worker.cancel()
        if engine:
            await engine.dispose()

app = FastAPI(lifespan=lifespan)
static_files = StaticFiles(directory="frontend/dist", html=True)
app.mount("/app", static_files, name="frontend")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

# Serves /index.html if we are in /app and there is a 404
@app.middleware("http")
async def spa_middleware(req: Request, call_next: Callable[[Request], Awaitable[Response]]):
    resp = await call_next(req)
    if resp.status_code == 404 and req.url.path.startswith("/app"):
        # Note: Find a better way to do this!
        req.scope["path"] = "/app/index.html"
        resp = await call_next(req)
    return resp

workers: list[asyncio.Task] = []

class RetryCount(BaseModel):
    r0: int
    r1: int
    r2: int
    r3: int
    r4: int
    total: int

class StatsJob(BaseModel):
    not_done: RetryCount
    completed: RetryCount
    failed: int 
    total: int

class StatsRepeatURL(BaseModel):
    active: int
    inactive: int
    total: int

class URLStats(BaseModel):
    super_recently_archived: int
    recently_archived: int
    not_recently_archived: int
    total_archived: int
    not_archived: int
    total: int

class Stats(BaseModel):
    jobs: StatsJob
    batches: int
    urls: URLStats
    repeat_urls: StatsRepeatURL

@app.get("/stats")
async def stats() -> Stats:
    async with async_session() as session, session.begin():
        not_done = dict((await session.execute(select(Job.retry, sqlalchemy.func.count(Job.id)).where((Job.completed == None) & (Job.failed == None)).group_by(Job.retry))).all())
        completed = dict((await session.execute(select(Job.retry, sqlalchemy.func.count(Job.id)).where(Job.completed != None).group_by(Job.retry))).all())
        failed = (await session.scalar(select(sqlalchemy.func.count(Job.id)).where(Job.failed != None))) or 0
        batches = (await session.scalar(select(sqlalchemy.func.count(Batch.id)))) or 0
        super_recently_archived_urls = (await session.scalar(select(sqlalchemy.func.count(URL.id)).where(URL.last_seen != None).where(URL.last_seen > datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(minutes=45)))) or 0
        recently_archived_urls = ((await session.scalar(select(sqlalchemy.func.count(URL.id)).where(URL.last_seen != None).where(URL.last_seen > datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(hours=4)))) or 0) - super_recently_archived_urls
        not_recently_archived_urls = (await session.scalar(select(sqlalchemy.func.count(URL.id)).where(URL.last_seen != None).where(URL.last_seen < datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(hours=4)))) or 0
        not_archived_urls = (await session.scalar(select(sqlalchemy.func.count(URL.id)).where(URL.last_seen == None))) or 0
        active_repeat_urls = (await session.scalar(select(sqlalchemy.func.count(RepeatURL.id)).where(RepeatURL.active_since != None))) or 0
        inactive_repeat_urls = (await session.scalar(select(sqlalchemy.func.count(RepeatURL.id)).where(RepeatURL.active_since == None))) or 0


    return Stats(
        jobs=StatsJob(
            not_done=RetryCount(
                r0=not_done.get(0, 0),
                r1=not_done.get(1, 0),
                r2=not_done.get(2, 0),
                r3=not_done.get(3, 0),
                r4=not_done.get(4, 0),
                total=sum(not_done.values())
            ),
            completed=RetryCount(
                r0=completed.get(0, 0),
                r1=completed.get(1, 0),
                r2=completed.get(2, 0),
                r3=completed.get(3, 0),
                r4=completed.get(4, 0),
                total=sum(completed.values())
            ),
            failed=failed,
            total=sum(not_done.values()) + sum(completed.values()) + failed
        ),
        batches=batches,
        urls=URLStats(
            super_recently_archived=super_recently_archived_urls,
            recently_archived=recently_archived_urls,
            not_recently_archived=not_recently_archived_urls,
            total_archived=super_recently_archived_urls + recently_archived_urls + not_recently_archived_urls,
            not_archived=not_archived_urls,
            total=super_recently_archived_urls + recently_archived_urls + not_recently_archived_urls + not_archived_urls
        ),
        repeat_urls=StatsRepeatURL(
            active=active_repeat_urls,
            inactive=inactive_repeat_urls,
            total=active_repeat_urls + inactive_repeat_urls
        )
    )

class QueueBatchBody(BaseModel):
    urls: list[str]
    priority: int = 0
    unique_only: bool = True

class QueueBatchReturn(BaseModel):
    batch_id: int
    job_count: int

@app.post("/queue_batch")
async def queue_batch(body: QueueBatchBody) -> QueueBatchReturn:
    batch = Batch()
    urls = body.urls
    if body.unique_only:
        urls = set(urls)
    async with async_session() as session, session.begin():
        stmt = select(URL).where(URL.url.in_(urls))
        result = await session.scalars(stmt)
        existing_urls_items = result.all()
        existing_urls = {url.url for url in existing_urls_items}
        new_urls = set(urls) - set(existing_urls)
        if new_urls:
            new_url_models = [URL(url=url) for url in new_urls]
            session.add_all(new_url_models)
            del new_urls, new_url_models, existing_urls, existing_urls_items
            # Needed because bulk create doesn't return the created models with their IDs
            stmt = select(URL).where(URL.url.in_(urls))
            result = await session.scalars(stmt)
            url_models = result.all()
        else:
            url_models = existing_urls_items
            del new_urls, existing_urls, existing_urls_items
        url_map = {url.url: url for url in url_models}
        del url_models
        jobs = []
        for url in urls:
            jobs.append(Job(url=url_map[url], batches=[batch], priority=body.priority))
        session.add_all(jobs)
        
    return QueueBatchReturn(batch_id=batch.id, job_count=len(jobs))

class QueueRepeatURLBody(BaseModel):
    url: str
    interval: int = 3600 * 4 # One URL can be archived 7x/day

class QueueLoopReturn(BaseModel):
    repeat_id: int


@app.post("/queue_loop")
async def queue_loop(body: QueueRepeatURLBody) -> QueueLoopReturn:
    async with async_session() as session, session.begin():
        stmt = select(RepeatURL).join(RepeatURL.url).where(URL.url == body.url)
        result = await session.scalars(stmt)
        repeat = result.first()
        if repeat is None:
            stmt = select(URL).where(URL.url == body.url)
            result = await session.scalars(stmt)
            url = result.first()
            if url is None:
                url = URL(url=body.url)
                session.add(url)
            batch = Batch()
            repeat = RepeatURL(url=url, interval=body.interval, batch=batch)
            session.add(repeat)
        else:
            repeat.interval = body.interval
            repeat.active_since = datetime.datetime.now(tz=datetime.timezone.utc)
    return QueueLoopReturn(repeat_id=repeat.id)

class JobReturn(BaseModel):
    id: int
    url: str
    created_at: datetime.datetime
    completed: datetime.datetime | None
    delayed_until: datetime.datetime | None
    priority: int
    retry: int
    failed: datetime.datetime | None
    batches: list[int] = []

    @classmethod
    def from_job(cls, job: Job, batch_ids: list[int] | None = None):
        """Make a JobReturn from a Job

        :param job: The job to make a JobReturn from
        :param batch_ids: Provide a list of batch IDs when a joinedload was not used
        :return: A JobReturn
        """
        return cls(
            id=job.id,
            url=job.url.url,
            created_at=job.created_at,
            completed=job.completed,
            delayed_until=job.delayed_until,
            priority=job.priority,
            retry=job.retry,
            failed=job.failed,
            batches=batch_ids if batch_ids is not None else [batch.id for batch in job.batches]
        )

class CurrentJobReturn(BaseModel):
    job: JobReturn | None

@app.get("/current_job")
async def current_job() -> CurrentJobReturn:
    job = await get_current_job(get_batches=True)
    if job is None:
        return {"job": None}
    return {
        "job": JobReturn.from_job(job)
    }

@app.get("/job/{job_id}")
async def get_job(job_id: Annotated[int, Path(title="Job ID", description="The ID of the job you want info on", ge=1)]) -> JobReturn:
    async with async_session() as session, session.begin():
        stmt = select(Job).where(Job.id == job_id).limit(1).options(sqlalchemy.orm.joinedload(Job.batches))
        job = await session.scalar(stmt)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobReturn.from_job(job)
    
class BatchReturn(BaseModel):
    id: int
    """The ID of the batch"""
    created_at: datetime.datetime
    """The time the batch was created"""
    repeat_url: int | None = None
    """The ID of the repeat URL that the batch represents, if any"""
    jobs: int
    """The number of jobs in the batch"""
    
@app.get("/batch/{batch_id}")
async def get_batch(batch_id: Annotated[int, Path(title="Batch ID", description="The ID of the batch you want info on", ge=1)]) -> BatchReturn:
    async with async_session() as session, session.begin():
        stmt = select(Batch).where(Batch.id == batch_id).limit(1)
        batch = await session.scalar(stmt)
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch not found")
        stmt = select(RepeatURL.id).join(RepeatURL.batch).where(Batch.id == batch_id).limit(1)
        repeat_url = await session.scalar(stmt)
        job_count = await session.scalar(select(sqlalchemy.func.count(Job.id)).join(Batch.jobs).where(Batch.id == batch_id))
        return {
            "id": batch.id,
            "created_at": batch.created_at,
            "repeat_url": repeat_url,
            "jobs": job_count
        }

class PaginationInfo(BaseModel):
    current_page: int
    total_pages: int
    items: int

ModelT = TypeVar("ModelT", bound=BaseModel)

class PaginationOutput(BaseModel, Generic[ModelT]):
    data: list[ModelT]
    pagination: PaginationInfo

Page = Annotated[int, Query(title="Page", description="The page of results you want", ge=1, le=100)]

class PaginationDefaultQueryArgs(TypedDict):
    page: Page
    after: datetime.datetime | None
    desc: bool

async def pagination_default_query_args(page: Page = 1, after: datetime.datetime | None = None, desc: bool = False) -> PaginationDefaultQueryArgs:
    return {
        "page": page,
        "after": after,
        "desc": desc
    }

PaginationQueryArgs = Annotated[PaginationDefaultQueryArgs, Depends(pagination_default_query_args)]

class JobPaginationDefaultQueryArgs(PaginationDefaultQueryArgs):
    not_started: bool
    completed: bool
    delayed: bool
    failed: bool
    retries_less_than: Literal[1, 2, 3, 4] | None
    retries_greater_than: Literal[0, 1, 2, 3] | None
    retries_equal_to: Literal[0, 1, 2, 3, 4] | None

async def job_pagination_default_query_args(page: Page = 1, after: datetime.datetime | None = None, desc: bool = False, not_started: bool = True, completed: bool = True, delayed: bool = True, failed: bool = True, retries_less_than: Literal[1, 2, 3, 4] | None = None, retries_greater_than: Literal[0, 1, 2, 3] | None = None, retries_equal_to: Literal[0, 1, 2, 3, 4] | None = None) -> JobPaginationDefaultQueryArgs:
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
        "retries_equal_to": retries_equal_to
    }

JobPaginationQueryArgs = Annotated[JobPaginationDefaultQueryArgs, Depends(job_pagination_default_query_args)]

@overload
def apply_job_filtering(query_params: JobPaginationDefaultQueryArgs, is_count_query: Literal[True], /) -> sqlalchemy.Select[tuple[int]]: ...
@overload
def apply_job_filtering(query_params: JobPaginationDefaultQueryArgs, is_count_query: Literal[False], /) -> sqlalchemy.Select[tuple[Job]]: ...
def apply_job_filtering(query_params: JobPaginationDefaultQueryArgs, is_count_query: bool = False, /) -> sqlalchemy.Select:
    in_statement = select(sqlalchemy.func.count(Job.id) if is_count_query else Job)
    if len({query_params["not_started"], query_params["completed"], query_params["delayed"], query_params["failed"]}) != 1: # If they are all the same, we can take a shortcut and not apply anything
        # If all 4 are given, we can take a shortcut and not apply anything
        if query_params["not_started"]:
            in_statement = in_statement.where((Job.completed == None) & (Job.failed == None) & (Job.delayed_until == None))
        if query_params["completed"]:
            in_statement = in_statement.where(Job.completed != None)
        if query_params["delayed"]:
            in_statement = in_statement.where(Job.delayed_until != None)
        if query_params["failed"]:
            in_statement = in_statement.where(Job.failed != None)
    retry_param_count = [query_params["retries_less_than"], query_params["retries_greater_than"], query_params["retries_equal_to"]].count(None)
    if retry_param_count <= 2:
        raise HTTPException(status_code=400, detail="You must provide only one of retries_less_than, retries_greater_than, or retries_equal_to")
    elif retry_param_count != 3:
        if query_params["retries_less_than"] is not None:
            in_statement = in_statement.where(Job.retry < query_params["retries_less_than"])
        if query_params["retries_greater_than"] is not None:
            in_statement = in_statement.where(Job.retry > query_params["retries_greater_than"])
        if query_params["retries_equal_to"] is not None:
            in_statement = in_statement.where(Job.retry == query_params["retries_equal_to"])
    if query_params["after"]:
        in_statement = in_statement.where(Job.created_at > query_params["after"])
    if not is_count_query:
        in_statement = in_statement.limit(100).order_by(Job.id.desc() if query_params["desc"] else Job.id.asc()).offset((query_params["page"] - 1) * 100)
    return in_statement

        


@app.get("/jobs")
async def get_jobs(query_params: JobPaginationQueryArgs) -> PaginationOutput[JobReturn]:
    async with async_session() as session, session.begin():
        job_count = await session.scalar(apply_job_filtering(query_params, True))
        stmt = apply_job_filtering(query_params, False).options(sqlalchemy.orm.joinedload(Job.batches))
        result = await session.scalars(stmt)
        return PaginationOutput(
            data=[JobReturn.from_job(job) for job in result.unique().all()],
            pagination=PaginationInfo(
                current_page=query_params["page"],
                total_pages=job_count // 100 + 1,
                items=job_count
            )
        )

@app.get("/batch/{batch_id}/jobs")
async def get_batch_jobs(batch_id: Annotated[int, Path(title="Batch ID", description="The ID of the batch you want info on", ge=1)], query_params: JobPaginationQueryArgs) -> PaginationOutput[JobReturn]:
    async with async_session() as session, session.begin():
        stmt = apply_job_filtering(query_params, True).join(Batch.jobs).where(Batch.id == batch_id)
        job_count = await session.scalar(stmt)
        stmt2 = apply_job_filtering(query_params, False).join(Batch.jobs).where(Batch.id == batch_id).options(sqlalchemy.orm.joinedload(Job.batches))
        result = await session.scalars(stmt2)
        return PaginationOutput(
            data=[JobReturn.from_job(job) for job in result.unique().all()],
            pagination=PaginationInfo(
                current_page=query_params["page"],
                total_pages=job_count // 100 + 1,
                items=job_count
            )
        )

@app.get("/batches")
async def get_batches(query_params: PaginationQueryArgs) -> PaginationOutput[BatchReturn]:
    after = query_params["after"]
    page = query_params["page"]
    desc = query_params["desc"]
    async with async_session() as session, session.begin():
        stmt = select(sqlalchemy.func.count(Batch.id))
        if after:
            stmt = stmt.where(Batch.created_at > after)
        batch_count = await session.scalar(stmt)
        stmt2 = select(Batch).order_by(Batch.id.desc() if desc else Batch.id.asc()).offset((page - 1) * 100).limit(100).options(sqlalchemy.orm.joinedload(Batch.jobs))
        if after:
            stmt2 = stmt2.where(Batch.created_at > after)
        result = await session.scalars(stmt2)
        return PaginationOutput(
            data=[BatchReturn(id=batch.id, created_at=batch.created_at, jobs=len(batch.jobs)) for batch in result.unique().all()],
            pagination=PaginationInfo(
                current_page=page,
                total_pages=batch_count // 100 + 1,
                items=batch_count
            )
        )

@app.get("/repeat_urls")
async def get_repeat_urls(query_params: PaginationQueryArgs) -> PaginationOutput[RepeatURL]:
    after = query_params["after"]
    page = query_params["page"]
    desc = query_params["desc"]
    async with async_session() as session, session.begin():
        stmt = select(sqlalchemy.func.count(RepeatURL.id))
        if after:
            stmt = stmt.where(RepeatURL.created_at > after)
        repeat_url_count = await session.scalar(stmt)
        stmt2 = select(RepeatURL).order_by(RepeatURL.id.desc() if desc else RepeatURL.id.asc()).offset((page - 1) * 100).limit(100)
        if after:
            stmt2 = stmt2.where(RepeatURL.created_at > after)
        result = await session.scalars(stmt2)
        return PaginationOutput(
            data=result.all(),
            pagination=PaginationInfo(
                current_page=page,
                total_pages=repeat_url_count // 100 + 1,
                items=repeat_url_count
            )
        )
    
@app.get("/urls")
async def get_urls(query_params: PaginationQueryArgs, unique: bool = True) -> PaginationOutput[URL]:
    after = query_params["after"]
    page = query_params["page"]
    desc = query_params["desc"]
    async with async_session() as session, session.begin():
        stmt = select(sqlalchemy.func.count(URL.id))
        if after:
            stmt = stmt.where(URL.first_seen > after)
        url_count = await session.scalar(stmt)
        stmt2 = select(URL).order_by(URL.id.desc() if desc else URL.id.asc()).offset((page - 1) * 100).limit(100)
        if after:
            stmt2 = stmt2.where(URL.first_seen > after)
        result = await session.scalars(stmt2)
        return PaginationOutput(
            data=result.unique().all(),
            pagination=PaginationInfo(
                current_page=page,
                total_pages=url_count // 100 + 1,
                items=url_count
            )
        )

class URLInfoBody(BaseModel):
    url: str

class URLReturn(BaseModel):
    jobs: list[JobReturn] = []
    first_seen: datetime.datetime
    last_seen: datetime.datetime | None

@app.post("/url")
async def get_url_info(body: URLInfoBody) -> URLReturn:
    async with async_session() as session, session.begin():
        stmt = select(URL).where(URL.url == body.url).limit(1).options(sqlalchemy.orm.joinedload(URL.jobs)).options(sqlalchemy.orm.joinedload(URL.jobs, Job.batches))
        url = await session.scalar(stmt)
        if url is None:
            raise HTTPException(status_code=404, detail="URL not found")
        return {
            "jobs": [JobReturn.from_job(job) for job in url.jobs],
            "first_seen": url.first_seen,
            "last_seen": url.last_seen
        }