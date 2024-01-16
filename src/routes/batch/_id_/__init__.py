from typing import Annotated
from fastapi import HTTPException, Path
from sqlalchemy import select
import sqlalchemy

from .. import BatchReturn

from ....models import Batch, Job, RepeatURL

from ....main import async_session, app


@app.get("/batch/{batch_id}")
async def get_batch(
    batch_id: Annotated[
        int,
        Path(
            title="Batch ID", description="The ID of the batch you want info on", ge=1
        ),
    ],
) -> BatchReturn:
    async with async_session() as session, session.begin():
        stmt = select(Batch).where(Batch.id == batch_id).limit(1)
        batch = await session.scalar(stmt)
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch not found")
        stmt = (
            select(RepeatURL.id)
            .join(RepeatURL.batch)
            .where(Batch.id == batch_id)
            .limit(1)
        )
        repeat_url = await session.scalar(stmt)
        job_count = await session.scalar(
            select(sqlalchemy.func.count(Job.id))
            .join(Batch.jobs)
            .where(Batch.id == batch_id)
        )
        return BatchReturn(
            id=batch.id,
            created_at=batch.created_at,
            repeat_url=repeat_url,
            jobs=job_count,
        )
