import datetime

from pydantic import BaseModel, Field
import sqlalchemy
from sqlalchemy import select

from ...models import Batch

from ...main import (
    PaginationInfo,
    PaginationOutput,
    PaginationQueryArgs,
    async_session,
    app,
)


class BatchReturn(BaseModel):
    id: int
    created_at: datetime.datetime
    repeat_url: int | None = None
    jobs: int
    tags: list[str] = Field(default_factory=list)


@app.get("/batch")
async def get_batches(
    query_params: PaginationQueryArgs,
) -> PaginationOutput[BatchReturn]:
    after = query_params["after"]
    page = query_params["page"]
    desc = query_params["desc"]
    async with async_session() as session, session.begin():
        stmt = select(sqlalchemy.func.count(Batch.id))
        if after:
            stmt = stmt.where(Batch.created_at > after)
        batch_count = await session.scalar(stmt)
        stmt2 = (
            select(Batch)
            .order_by(Batch.id.desc() if desc else Batch.id.asc())
            .offset((page - 1) * 100)
            .limit(100)
            .options(sqlalchemy.orm.joinedload(Batch.jobs))
        )
        if after:
            stmt2 = stmt2.where(Batch.created_at > after)
        result = await session.scalars(stmt2)
        return PaginationOutput(
            data=[
                BatchReturn(
                    id=batch.id, created_at=batch.created_at, jobs=len(batch.jobs)
                )
                for batch in result.unique().all()
            ],
            pagination=PaginationInfo(
                current_page=page, total_pages=batch_count // 100 + 1, items=batch_count
            ),
        )
