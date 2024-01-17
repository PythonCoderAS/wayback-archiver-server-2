from typing import Iterable
from pydantic import BaseModel, Field
from sqlalchemy import select
from ....models import Job, URL, Batch
from ....main import app, async_session


class QueueBatchBody(BaseModel):
    urls: list[str]
    tags: list[str] = Field(default_factory=list)


class QueueBatchReturn(BaseModel):
    batch_id: int
    job_count: int


async def add_batch(
    urls: Iterable[str],
    *,
    priority: int = 0,
    tags: list[str],
) -> QueueBatchReturn:
    async with async_session() as session, session.begin():
        batch = Batch()
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
            jobs.append(Job(url=url_map[url], batches=[batch], priority=priority))
        session.add_all(jobs)

    return QueueBatchReturn(batch_id=batch.id, job_count=len(jobs))


@app.post("/queue/batch")
async def queue_batch(
    body: QueueBatchBody, priority: int = 0, unique_only: bool = True
) -> QueueBatchReturn:
    return await add_batch(
        set(body.urls) if unique_only else body.urls, priority, unique_only
    )
