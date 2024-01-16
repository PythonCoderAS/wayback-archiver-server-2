from ...main import (
    app,
    PaginationQueryArgs,
    PaginationOutput,
    async_session,
    PaginationInfo,
)
from ...models import URL
import sqlalchemy
from sqlalchemy import select


@app.get("/url")
async def get_urls(
    query_params: PaginationQueryArgs, unique: bool = True
) -> PaginationOutput[URL]:
    after = query_params["after"]
    page = query_params["page"]
    desc = query_params["desc"]
    async with async_session() as session, session.begin():
        stmt = select(sqlalchemy.func.count(URL.id))
        if after:
            stmt = stmt.where(URL.first_seen > after)
        url_count = await session.scalar(stmt)
        stmt2 = (
            select(URL)
            .order_by(URL.id.desc() if desc else URL.id.asc())
            .offset((page - 1) * 100)
            .limit(100)
        )
        if after:
            stmt2 = stmt2.where(URL.first_seen > after)
        result = await session.scalars(stmt2)
        return PaginationOutput(
            data=result.unique().all(),
            pagination=PaginationInfo(
                current_page=page, total_pages=url_count // 100 + 1, items=url_count
            ),
        )
