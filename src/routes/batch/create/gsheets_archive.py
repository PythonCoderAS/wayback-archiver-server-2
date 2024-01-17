import datetime
from typing import Literal
from fastapi import UploadFile
from . import add_filled_batch, BatchItem
from csv import DictReader
from typing import TypedDict

from ...queue.batch import QueueBatchReturn
from ....main import app, archive_url_regex, get_archive_save_url_timestamp

heading = (
    "url",
    "capture_dupe_status",
    "new_capture_status",
    "archive_message",
    "archive_info",
    "first_archive_status",
)


class CSVBatchItem(TypedDict):
    url: str
    capture_dupe_status: Literal["New capture", "Already captured", ""]
    new_capture_status: str | Literal[""]
    archive_message: str
    archive_info: str | Literal[""]
    first_archive_status: Literal["First Archive", ""]


@app.post("/batch/create/gsheets_archive")
async def create_batch_gsheets_archive(
    file: UploadFile,
    priority: int = 0,
    tags: list[str] | None = None,
    created_override: datetime.datetime | None = None,
) -> QueueBatchReturn:
    if tags is None:
        tags = []
    tags.append("wayback-machine-gsheets-archive")
    csv_items = (await file.read()).decode().splitlines(False)
    reader = DictReader(csv_items, fieldnames=heading)
    items_list: list[CSVBatchItem] = list(reader)
    items: list[BatchItem] = []
    for item in items_list:
        url = item["url"]
        if match := archive_url_regex.search(item["archive_message"]):
            archived_timestamp = get_archive_save_url_timestamp(match.group(1))
            items.append(
                BatchItem(
                    url=url, completed=archived_timestamp, created=created_override
                )
            )
        elif item["archive_message"]:  # A message other than an URL = failure
            items.append(
                BatchItem(
                    url=url,
                    failed=datetime.datetime.now(tz=datetime.timezone.utc),
                    created=created_override,
                )
            )
    return await add_filled_batch(items, priority=priority, tags=tags)
