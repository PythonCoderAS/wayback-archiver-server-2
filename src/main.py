import asyncio
from contextlib import asynccontextmanager
import datetime
from os import environ
import re

from pydantic import BaseModel
import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.ext.asyncio
from sqlalchemy import select, update
from sqlalchemy.orm import Mapped, mapped_column
from fastapi import FastAPI
from aiohttp import ClientSession

engine: sqlalchemy.ext.asyncio.AsyncEngine = None
async_session: sqlalchemy.ext.asyncio.async_sessionmaker[sqlalchemy.ext.asyncio.AsyncSession] = None
client_session: ClientSession = None

class Base(sqlalchemy.orm.MappedAsDataclass, sqlalchemy.ext.asyncio.AsyncAttrs, sqlalchemy.orm.DeclarativeBase):
    pass

class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=sqlalchemy.sql.func.now(), nullable=False)

    jobs: Mapped[list["Job"]] = sqlalchemy.orm.relationship(secondary="jobs_batches", back_populates="batches")

class URL(Base):
    __tablename__ = "urls"


    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(sqlalchemy.String(length=10000), unique=True, index=True)
    first_seen: Mapped[datetime.datetime] = mapped_column(server_default=sqlalchemy.sql.func.now(), nullable=False)
    last_seen: Mapped[datetime.datetime | None] = mapped_column(default=None, nullable=True)

class RepeatURL(Base):
    __tablename__ = "repeat_urls"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[URL] = sqlalchemy.orm.relationship(lazy="joined", innerjoin=True, foreign_keys=[URL.id])
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=sqlalchemy.sql.func.now(), nullable=False)
    batch: Mapped[Batch] = sqlalchemy.orm.relationship(innerjoin=True, foreign_keys=[Batch.id])
    interval: Mapped[int] = mapped_column(default=3600 * 4)
    active_since: Mapped[datetime.datetime | None] = mapped_column(default=None, nullable=True, index=True) # Indicates that a repeat URL is active

    __table_args__ = (sqlalchemy.UniqueConstraint("url"), sqlalchemy.UniqueConstraint("batch"))



class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(sqlalchemy.BigInteger, primary_key=True)
    batches: Mapped[list[Batch]] = sqlalchemy.orm.relationship(Batch, secondary="jobs_batches")
    priority: Mapped[int] = mapped_column(default=0)
    url: Mapped[URL] = sqlalchemy.orm.relationship(lazy="joined")
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=sqlalchemy.sql.func.now(), nullable=False)
    completed: Mapped[datetime.datetime | None] = mapped_column(default=None, nullable=True)
    delayed_until: Mapped[datetime.datetime | None] = mapped_column(default=None, nullable=True) # If a job needs to be delayed, this is the time it should be run at
    retry: Mapped[int] = mapped_column(sqlalchemy.SmallInteger, default=0) # Number of times this job has been retried
    failed: Mapped[datetime.datetime | None] = mapped_column(default=None, nullable=True) # If a job has failed, this is the time it failed at

async def get_current_job(curtime=None) -> Job | None:
    if not curtime:
        curtime = datetime.datetime.now(tz=datetime.timezone.utc)
    # return await Job.objects.filter(ormar.or_(delayed_until__gte=curtime + datetime.timedelta(minutes=45), delayed_until=None), completed=None, failed=None).order_by(["-priority", "created_at"]).select_related("url").first()
    stmt = select(Job).where(((Job.delayed_until <= curtime) | (Job.delayed_until == None)) & (Job.completed == None) & (Job.failed == None)).order_by(Job.priority.desc(), Job.created_at)
    async with async_session() as session:
        result = await session.scalars(stmt)
        return result.first()

        

async def url_worker():
    while True:
        curtime = datetime.datetime.now(tz=datetime.timezone.utc)
        next_job = await get_current_job(curtime=curtime)
        if next_job is None:
            await asyncio.sleep(1)
            continue
        # First, make sure that we don't have to delay this URL (only one capture per 45 minutes)
        if next_job.url.last_seen + datetime.timedelta(minutes=45) > curtime:
            async with async_session() as session:
                stmt = update(Job).where(Job.id == next_job.id).values(delayed_until=next_job.url.last_seen + datetime.timedelta(minutes=45))
                await session.execute(stmt)
            continue
        if client_session is None:
            client_session = ClientSession()
        for _ in range(5): # Up to 4 retries (5 attempts total)
            try:
                async with client_session.get("https://web.archive.org/save" + next_job.url.url, allow_redirects=False) as resp:
                    if match := re.search(r"/web/(\d{14})", resp.headers.get("Location", "")):
                        saved_dt = datetime.datetime.strptime(match.group(1), "%Y%m%d%H%M%S").replace(tzinfo=datetime.timezone.utc)
                        async with async_session() as session:
                            await session.execute(update(URL).where(URL.id == next_job.url.id).values(last_seen=saved_dt))
                            await session.execute(update(Job).where(Job.id == next_job.id).values(completed=curtime))
                        break
            except Exception:
                pass
        else: # Ran out of retries, try again
            async with async_session() as session:
                if next_job.retry < 4:
                    await session.execute(update(Job).where(Job.id == next_job.id).values(retry=next_job.retry + 1, delayed_until=curtime + datetime.timedelta(minutes=45)))
                else:
                    await session.execute(update(Job).where(Job.id == next_job.id).values(failed=curtime))

async def repeat_url_worker():
    batch = None
    created_at: datetime.datetime = None
    while True:
        curtime = datetime.datetime.now(tz=datetime.timezone.utc)
        # jobs = await RepeatURL.objects.filter(active_since_lte=curtime).select_related(["url", "batch"]).all()
        stmt = select(RepeatURL).where(RepeatURL.active_since <= curtime).join(RepeatURL.url).join(RepeatURL.batch).order_by(RepeatURL.created_at)
        async with async_session() as session:
            result = await session.scalars(stmt)
            jobs = result.all()
        queued: list[Job] = []
        for job in jobs:
            if job.url.last_seen + datetime.timedelta(seconds=job.interval) < curtime: # Job can be re-queued
                if batch is None or (created_at + datetime.timedelta(minutes=30) < curtime):
                    # batch = await Batch.objects.create()
                    batch = Batch()
                    created_at = curtime
                queued.append(Job(url=job.url, priority=10, batches=[batch, job.batch]))
        if queued:
            # await Job.objects.bulk_create(queued)
            async with async_session() as session:
                session.add_all(queued)
        await asyncio.sleep(60)



@asynccontextmanager
async def lifespan(_: FastAPI):
    global engine, async_session
    if engine is None:
        engine = sqlalchemy.ext.asyncio.create_async_engine(environ.get("DATABASE_URL", "sqlite://db.sqlite"))
    async_session = sqlalchemy.ext.asyncio.async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    workers.append(asyncio.create_task(url_worker()))
    workers.append(asyncio.create_task(repeat_url_worker()))
    try:
        yield
    finally:
        for worker in workers:
            worker.cancel()
        if engine:
            await engine.dispose()

app = FastAPI(lifespan=lifespan)
workers: list[asyncio.Task] = []

@app.get("/stats")
async def stats():
    # async with asyncio.TaskGroup() as tg:
    #     not_done_jobs_task = tg.create_task(Job.objects.filter(completed=None).count())
    #     completed_jobs_task = tg.create_task(Job.objects.filter(completed__isnull=False).count())
    #     batches_task = tg.create_task(Batch.objects.count())
    #     urls_task = tg.create_task(URL.objects.count())
    #     active_repeat_urls_task = tg.create_task(RepeatURL.objects.filter(active_since__isnull=False).count())
    #     inactive_repeat_urls_task = tg.create_task(RepeatURL.objects.filter(active_since__isnull=True).count())
    async with async_session() as session:
        not_done = (await session.scalar(select(sqlalchemy.func.count(Job.id)).where(Job.completed == None))) or 0
        completed = (await session.scalar(select(sqlalchemy.func.count(Job.id)).where(Job.completed != None))) or 0
        batches = (await session.scalar(select(sqlalchemy.func.count(Batch.id)))) or 0
        urls = (await session.scalar(select(sqlalchemy.func.count(URL.id)))) or 0
        active_repeat_urls = (await session.scalar(select(sqlalchemy.func.count(RepeatURL.id)).where(RepeatURL.active_since != None))) or 0
        inactive_repeat_urls = (await session.scalar(select(sqlalchemy.func.count(RepeatURL.id)).where(RepeatURL.active_since == None))) or 0


    return {
        "jobs": {
            "not_done": not_done,
            "completed": completed,
            "total": not_done + completed,
        },
        "batches": batches,
        "urls": urls,
        "repeat_urls": {
            "active": active_repeat_urls,
            "inactive": inactive_repeat_urls,
            "total": active_repeat_urls + inactive_repeat_urls,
        },
    }

class QueueBatchBody(BaseModel):
    urls: list[str]
    priority: int = 0
    unique_only = True

@app.post("/queue_batch")
async def queue_batch(body: QueueBatchBody):
    batch = Batch()
    urls = body.urls
    if body.unique_only:
        urls = set(urls)
    async with async_session() as session:
        stmt = select(URL).where(URL.url.in_(urls))
        result = await session.scalars(stmt)
        existing_urls_items = result.all()
        existing_urls = {url.url for url in existing_urls_items}
        new_urls = set(urls) - set(existing_urls)
        if new_urls:
            new_url_models = [URL(url=url) for url in new_urls]
            await session.add_all(new_url_models)
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
        await session.add_all(jobs)
        
    return {"batch_id": batch.id, "job_count": len(jobs)}

class QueueRepeatURLBody(BaseModel):
    url: str
    interval: int = 3600 * 4 # One URL can be archived 7x/day


@app.post("/queue_loop")
async def queue_loop(body: QueueRepeatURLBody):
    async with async_session() as session:
        stmt = select(RepeatURL).where(RepeatURL.url.url == body.url)
        result = await session.scalars(stmt)
        repeat = result.first()
        if repeat is None:
            stmt = select(URL).where(URL.url == body.url)
            result = await session.scalars(stmt)
            url = result.first()
            if url is None:
                url = URL(url=body.url)
                await session.add(url)
            batch = Batch()
            repeat = RepeatURL(url=url, interval=body.interval, batch=batch)
            await session.add(repeat)
        else:
            repeat.interval = body.interval
            repeat.active_since = None
    return {"repeat_id": repeat.id}

@app.get("/current_job")
async def current_job():
    job = await get_current_job()
    if job is None:
        return {"job": None}
    return {
        "job": job
    }