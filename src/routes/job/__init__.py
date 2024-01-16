import sqlalchemy

from ...models import Job

from ...main import (
    JobPaginationQueryArgs,
    PaginationInfo,
    PaginationOutput,
    apply_job_filtering,
    async_session,
    app,
)
from .shared_models import JobReturn


@app.get("/job")
async def get_jobs(query_params: JobPaginationQueryArgs) -> PaginationOutput[JobReturn]:
    async with async_session() as session, session.begin():
        job_count = await session.scalar(apply_job_filtering(query_params, True))
        stmt = apply_job_filtering(query_params, False).options(
            sqlalchemy.orm.joinedload(Job.batches)
        )
        result = await session.scalars(stmt)
        return PaginationOutput(
            data=[JobReturn.from_job(job) for job in result.unique().all()],
            pagination=PaginationInfo(
                current_page=query_params["page"],
                total_pages=job_count // 100 + 1,
                items=job_count,
            ),
        )
