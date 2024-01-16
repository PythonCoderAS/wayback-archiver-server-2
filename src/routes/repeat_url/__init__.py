from ...main import (
    app,
    PaginationQueryArgs,
    PaginationOutput,
    async_session,
    PaginationInfo,
)
from ...models import RepeatURL
import sqlalchemy
from sqlalchemy import select


@app.get("/repeat_url")
async def get_repeat_urls(
    query_params: PaginationQueryArgs,
) -> PaginationOutput[RepeatURL]:
    after = query_params["after"]
    page = query_params["page"]
    desc = query_params["desc"]
    async with async_session() as session, session.begin():
        stmt = select(sqlalchemy.func.count(RepeatURL.id))
        if after:
            stmt = stmt.where(RepeatURL.created_at > after)
        repeat_url_count = await session.scalar(stmt)
        stmt2 = (
            select(RepeatURL)
            .order_by(RepeatURL.id.desc() if desc else RepeatURL.id.asc())
            .offset((page - 1) * 100)
            .limit(100)
        )
        if after:
            stmt2 = stmt2.where(RepeatURL.created_at > after)
        result = await session.scalars(stmt2)
        return PaginationOutput(
            data=result.all(),
            pagination=PaginationInfo(
                current_page=page,
                total_pages=repeat_url_count // 100 + 1,
                items=repeat_url_count,
            ),
        )
