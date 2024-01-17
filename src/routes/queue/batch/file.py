from fastapi import UploadFile
from pydantic import BaseModel, Field

from . import QueueBatchReturn, add_batch
from ....main import app

class QueueBatchFileBody(BaseModel):
    file: UploadFile
    tags: list[str] = Field(default_factory=list)

@app.post("/queue/batch/file")
async def queue_batch_file(body: QueueBatchFileBody, priority: int = 0, unique_only: bool = False, ) -> QueueBatchReturn:
    urls = (await body.file.read()).decode().splitlines(False)
    return await add_batch(set(urls) if unique_only else urls, priority, unique_only, tags=body.tags)