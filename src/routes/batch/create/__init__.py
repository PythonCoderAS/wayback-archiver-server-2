import datetime
from typing import Iterable
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from src.routes.queue.batch import QueueBatchReturn
from ....models import Job, URL, Batch
from ....main import app, async_session


class BatchItem(BaseModel):
    url: str
    completed: datetime.datetime | None = None
    failed: datetime.datetime | None = None
    created: datetime.datetime | None = None

    @model_validator(mode="after")
    def validate(self):
        if self.completed and self.failed:
            raise ValueError("Batch item cannot be both completed and failed")
        if not self.completed and not self.failed:
            raise ValueError("Batch item must be either completed or failed")

    @property
    def effective_creation_time(self) -> datetime.datetime:
        return self.created or self.completed or self.failed


class CreateBatchBody(BaseModel):
    items: list[BatchItem]
    tags: list[str] = Field(default_factory=list)


async def add_filled_batch(
    items: Iterable[BatchItem],
    *,
    priority: int = 0,
    tags: list[str],
) -> QueueBatchReturn:
    urls = [item.url for item in items]
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
        url_map: dict[str, URL] = {url.url: url for url in url_models}
        del url_models
        jobs = []
        for item in items:
            job = Job(
                url=url_map[item.url],
                batches=[batch],
                priority=priority,
                completed=item.completed,
                failed=item.failed,
            )
            job.created_at = item.effective_creation_time
            jobs.append(job)
            url_map[item.url].last_seen = item.completed or url_map[item.url].last_seen
        session.add_all(jobs)

    return QueueBatchReturn(batch_id=batch.id, job_count=len(jobs))


@app.post("/batch/create")
async def create_batch(body: CreateBatchBody, priority: int = 0) -> QueueBatchReturn:
    return await add_filled_batch(body.items, priority=priority, tags=body.tags)
