import datetime
from pydantic import BaseModel
import sqlalchemy
from sqlalchemy import select
from ..models import Job, URL, Batch, RepeatURL
from ..main import app, async_session, min_wait_time_between_archives


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
        not_done = dict(
            (
                await session.execute(
                    select(Job.retry, sqlalchemy.func.count(Job.id))
                    .where((Job.completed == None) & (Job.failed == None))
                    .group_by(Job.retry)
                )
            ).all()
        )
        completed = dict(
            (
                await session.execute(
                    select(Job.retry, sqlalchemy.func.count(Job.id))
                    .where(Job.completed != None)
                    .group_by(Job.retry)
                )
            ).all()
        )
        failed = (
            await session.scalar(
                select(sqlalchemy.func.count(Job.id)).where(Job.failed != None)
            )
        ) or 0
        batches = (await session.scalar(select(sqlalchemy.func.count(Batch.id)))) or 0
        super_recently_archived_urls = (
            await session.scalar(
                select(sqlalchemy.func.count(URL.id))
                .where(URL.last_seen != None)
                .where(
                    URL.last_seen
                    > datetime.datetime.now(tz=datetime.timezone.utc)
                    - min_wait_time_between_archives
                )
            )
        ) or 0
        recently_archived_urls = (
            (
                await session.scalar(
                    select(sqlalchemy.func.count(URL.id))
                    .where(URL.last_seen != None)
                    .where(
                        URL.last_seen
                        > datetime.datetime.now(tz=datetime.timezone.utc)
                        - datetime.timedelta(hours=4)
                    )
                )
            )
            or 0
        ) - super_recently_archived_urls
        not_recently_archived_urls = (
            await session.scalar(
                select(sqlalchemy.func.count(URL.id))
                .where(URL.last_seen != None)
                .where(
                    URL.last_seen
                    < datetime.datetime.now(tz=datetime.timezone.utc)
                    - datetime.timedelta(hours=4)
                )
            )
        ) or 0
        not_archived_urls = (
            await session.scalar(
                select(sqlalchemy.func.count(URL.id)).where(URL.last_seen == None)
            )
        ) or 0
        active_repeat_urls = (
            await session.scalar(
                select(sqlalchemy.func.count(RepeatURL.id)).where(
                    RepeatURL.active_since != None
                )
            )
        ) or 0
        inactive_repeat_urls = (
            await session.scalar(
                select(sqlalchemy.func.count(RepeatURL.id)).where(
                    RepeatURL.active_since == None
                )
            )
        ) or 0

    return Stats(
        jobs=StatsJob(
            not_done=RetryCount(
                r0=not_done.get(0, 0),
                r1=not_done.get(1, 0),
                r2=not_done.get(2, 0),
                r3=not_done.get(3, 0),
                r4=not_done.get(4, 0),
                total=sum(not_done.values()),
            ),
            completed=RetryCount(
                r0=completed.get(0, 0),
                r1=completed.get(1, 0),
                r2=completed.get(2, 0),
                r3=completed.get(3, 0),
                r4=completed.get(4, 0),
                total=sum(completed.values()),
            ),
            failed=failed,
            total=sum(not_done.values()) + sum(completed.values()) + failed,
        ),
        batches=batches,
        urls=URLStats(
            super_recently_archived=super_recently_archived_urls,
            recently_archived=recently_archived_urls,
            not_recently_archived=not_recently_archived_urls,
            total_archived=super_recently_archived_urls
            + recently_archived_urls
            + not_recently_archived_urls,
            not_archived=not_archived_urls,
            total=super_recently_archived_urls
            + recently_archived_urls
            + not_recently_archived_urls
            + not_archived_urls,
        ),
        repeat_urls=StatsRepeatURL(
            active=active_repeat_urls,
            inactive=inactive_repeat_urls,
            total=active_repeat_urls + inactive_repeat_urls,
        ),
    )
