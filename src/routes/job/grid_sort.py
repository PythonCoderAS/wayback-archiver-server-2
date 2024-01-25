from typing import Iterable
from ...main import app, async_session
from ...models import Job
from sqlalchemy import select
import sqlalchemy.orm

from . import JobReturn

from ...server_side_grid import IServerSideGetRowsRequest, LoadSuccessParams


@app.post("/job/grid_sort")
async def get_job_grid_sort(
    request: IServerSideGetRowsRequest,
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
    count_query = select(sqlalchemy.func.count(Job.id))
    async with async_session() as session, session.begin():
        data: Iterable[Job] = await session.scalars(query)
        result = [JobReturn.from_job(row) for row in data.unique()]
        count = await session.scalar(count_query)

    return LoadSuccessParams[JobReturn](
        rowData=result,
        rowCount=count,
    )
