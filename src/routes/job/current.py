from pydantic import BaseModel

from ...main import app, get_current_job
from .shared_models import JobReturn


class CurrentJobReturn(BaseModel):
    job: JobReturn | None


@app.get("/job/current")
async def current_job() -> CurrentJobReturn:
    job = await get_current_job(get_batches=True)
    if job is None:
        return {"job": None}
    return {"job": JobReturn.from_job(job)}
