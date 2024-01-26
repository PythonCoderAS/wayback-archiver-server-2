from typing import Iterable
from ...main import app, async_session
from ...models import URL, Batch, Job
from sqlalchemy import select
import sqlalchemy.orm

from . import JobReturn

from ...server_side_grid import IServerSideGetRowsRequest, LoadSuccessParams

sort_map = {"url": URL.url}


@app.post("/job/grid_sort")
async def get_job_grid_sort(
    request: IServerSideGetRowsRequest, batch_id: int | None = None
) -> LoadSuccessParams[JobReturn]:
    """Get job grid sort."""

    selected = [Job]
    offset = request.startRow
    limit = request.endRow - request.startRow
    query = (
        select(*selected)
        .options(sqlalchemy.orm.joinedload(Job.batches))
        .offset(offset)
        .limit(limit)
    )
    if request.sortModel:
        for sort in request.sortModel:
            sort_attribute = sort_map.get(sort.colId, None) or getattr(Job, sort.colId)
            if sort.sort == "asc":
                query = query.order_by(sort_attribute)
            else:
                query = query.order_by(sort_attribute.desc())
    count_query = select(sqlalchemy.func.count(Job.id))
    if batch_id:
        query = query.where(Job.batches.any(Batch.id == batch_id))
        count_query = count_query.where(Job.batches.any(Batch.id == batch_id))
    async with async_session() as session, session.begin():
        data: Iterable[Job] = await session.scalars(query)
        result = [JobReturn.from_job(row) for row in data.unique()]
        count = await session.scalar(count_query)

    return LoadSuccessParams[JobReturn](
        rowData=result,
        rowCount=count,
    )
