import datetime
from pydantic import BaseModel
from sqlalchemy import select
from ...models import URL, Batch, RepeatURL
from ...main import app, async_session


class QueueRepeatURLBody(BaseModel):
    url: str
    interval: int = 3600 * 4  # One URL can be archived 7x/day


class QueueLoopReturn(BaseModel):
    repeat_id: int


@app.post("/queue/loop")
async def queue_loop(body: QueueRepeatURLBody) -> QueueLoopReturn:
    async with async_session() as session, session.begin():
        stmt = select(RepeatURL).join(RepeatURL.url).where(URL.url == body.url)
        result = await session.scalars(stmt)
        repeat = result.first()
        if repeat is None:
            stmt = select(URL).where(URL.url == body.url)
            result = await session.scalars(stmt)
            url = result.first()
            if url is None:
                url = URL(url=body.url)
                session.add(url)
            batch = Batch()
            repeat = RepeatURL(url=url, interval=body.interval, batch=batch)
            session.add(repeat)
        else:
            repeat.interval = body.interval
            repeat.active_since = datetime.datetime.now(tz=datetime.timezone.utc)
    return QueueLoopReturn(repeat_id=repeat.id)
