from typing import Annotated
from fastapi import Path
import sqlalchemy

from ....models import Job, Batch

from ....main import (
    JobPaginationQueryArgs,
    PaginationInfo,
    PaginationOutput,
    apply_job_filtering,
    async_session,
    app,
)
from ...job.shared_models import JobReturn


@app.get("/batch/{batch_id}/jobs")
async def get_batch_jobs(
    batch_id: Annotated[
        int,
        Path(
            title="Batch ID", description="The ID of the batch you want info on", ge=1
        ),
    ],
    query_params: JobPaginationQueryArgs,
) -> PaginationOutput[JobReturn]:
    async with async_session() as session, session.begin():
        stmt = (
            apply_job_filtering(query_params, True)
            .join(Batch.jobs)
            .where(Batch.id == batch_id)
        )
        job_count = await session.scalar(stmt)
        stmt2 = (
            apply_job_filtering(query_params, False)
            .join(Batch.jobs)
            .where(Batch.id == batch_id)
            .options(sqlalchemy.orm.joinedload(Job.batches))
        )
        result = await session.scalars(stmt2)
        return PaginationOutput(
            data=[JobReturn.from_job(job) for job in result.unique().all()],
            pagination=PaginationInfo(
                current_page=query_params["page"],
                total_pages=job_count // 100 + 1,
                items=job_count,
            ),
        )
