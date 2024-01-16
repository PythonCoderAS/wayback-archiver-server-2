from typing import Annotated
from fastapi import HTTPException, Path
import sqlalchemy
from sqlalchemy import select

from ...models import Job

from ...main import async_session, app
from .shared_models import JobReturn


@app.get("/job/{job_id}")
async def get_job(
    job_id: Annotated[
        int,
        Path(title="Job ID", description="The ID of the job you want info on", ge=1),
    ],
) -> JobReturn:
    async with async_session() as session, session.begin():
        stmt = (
            select(Job)
            .where(Job.id == job_id)
            .limit(1)
            .options(sqlalchemy.orm.joinedload(Job.batches))
        )
        job = await session.scalar(stmt)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobReturn.from_job(job)
