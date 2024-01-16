import datetime
from fastapi import HTTPException
from pydantic import BaseModel
import sqlalchemy
from sqlalchemy import select

from ..job.shared_models import JobReturn
from ...models import Job, URL
from ...main import app, async_session


class URLInfoBody(BaseModel):
    url: str


class URLReturn(BaseModel):
    jobs: list[JobReturn] = []
    first_seen: datetime.datetime
    last_seen: datetime.datetime | None


@app.post("/url")
async def get_url_info(body: URLInfoBody) -> URLReturn:
    async with async_session() as session, session.begin():
        stmt = (
            select(URL)
            .where(URL.url == body.url)
            .limit(1)
            .options(sqlalchemy.orm.joinedload(URL.jobs))
            .options(sqlalchemy.orm.joinedload(URL.jobs, Job.batches))
        )
        url = await session.scalar(stmt)
        if url is None:
            raise HTTPException(status_code=404, detail="URL not found")
        return {
            "jobs": [JobReturn.from_job(job) for job in url.jobs],
            "first_seen": url.first_seen,
            "last_seen": url.last_seen,
        }
