import datetime

from pydantic import BaseModel

from ...models import Job


class JobReturn(BaseModel):
    id: int
    url: str
    created_at: datetime.datetime
    completed: datetime.datetime | None
    delayed_until: datetime.datetime | None
    priority: int
    retry: int
    failed: datetime.datetime | None
    batches: list[int] = []

    @classmethod
    def from_job(cls, job: Job, batch_ids: list[int] | None = None):
        """Make a JobReturn from a Job

        :param job: The job to make a JobReturn from
        :param batch_ids: Provide a list of batch IDs when a joinedload was not used
        :return: A JobReturn
        """
        return cls(
            id=job.id,
            url=job.url.url,
            created_at=job.created_at,
            completed=job.completed,
            delayed_until=job.delayed_until,
            priority=job.priority,
            retry=job.retry,
            failed=job.failed,
            batches=batch_ids
            if batch_ids != None
            else [batch.id for batch in job.batches],
        )
