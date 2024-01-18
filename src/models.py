import datetime
from typing import Self
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column
import sqlalchemy.ext.asyncio
import sqlalchemy.orm


class Base(
    sqlalchemy.orm.MappedAsDataclass,
    sqlalchemy.ext.asyncio.AsyncAttrs,
    sqlalchemy.orm.DeclarativeBase,
):
    pass


class BatchTag(Base):
    __tablename__ = "batch_tags"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    name: Mapped[str] = mapped_column(
        sqlalchemy.String(length=256), unique=True, index=True
    )

    batches: Mapped[list["Batch"]] = sqlalchemy.orm.relationship(
        "Batch",
        secondary="batch_tag_batches",
        back_populates="tags",
        init=False,
        repr=False,
    )

    @classmethod
    async def resolve_list(cls, names: set[str]) -> list[Self]:
        from .main import async_session

        if not names:
            return []

        async with async_session() as session, session.begin():
            stmt = select(cls).where(cls.name.in_(names))
            result = (await session.scalars(stmt)).all()
            seen = {r.name: r for r in result}
            seen_set = set(seen.keys())
            missing = names - seen_set
            if missing:
                newly_created: list[BatchTag] = [
                    BatchTag(name=name) for name in missing
                ]
                session.add_all(newly_created)
                return [*seen.values(), *newly_created]
            return list(seen.values())


class BatchTagBatch(Base):
    __tablename__ = "batch_tag_batches"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    batch_id: Mapped[int] = mapped_column(
        sqlalchemy.ForeignKey("batches.id"), index=True
    )
    batch_tag_id: Mapped[int] = mapped_column(
        sqlalchemy.ForeignKey(BatchTag.id), index=True
    )

    batch: Mapped["Batch"] = sqlalchemy.orm.relationship(
        "Batch", lazy="joined", innerjoin=True, foreign_keys=[batch_id], viewonly=True
    )
    batch_tag: Mapped["BatchTag"] = sqlalchemy.orm.relationship(
        "BatchTag",
        lazy="joined",
        innerjoin=True,
        foreign_keys=[batch_tag_id],
        viewonly=True,
    )

    __table_args__ = (
        sqlalchemy.UniqueConstraint(
            "batch_id", "batch_tag_id", name="_batch_batch_tag_uc"
        ),
    )


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sqlalchemy.DateTime(timezone=True),
        server_default=sqlalchemy.sql.func.now(),
        nullable=False,
        init=False,
        index=True,
    )
    locked: Mapped[bool] = mapped_column(
        default=False
    )  # Indicates that a batch is locked (no more jobs can be added to it)

    jobs: Mapped[list["Job"]] = sqlalchemy.orm.relationship(
        "Job", secondary="batch_jobs", back_populates="batches", init=False, repr=False
    )
    tags: Mapped[list[BatchTag]] = sqlalchemy.orm.relationship(
        BatchTag,
        secondary="batch_tag_batches",
        back_populates="batches",
        default_factory=list,
    )


class URL(Base):
    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    url: Mapped[str] = mapped_column(
        sqlalchemy.String(length=10000), unique=True, index=True
    )
    first_seen: Mapped[datetime.datetime] = mapped_column(
        sqlalchemy.DateTime(timezone=True),
        server_default=sqlalchemy.sql.func.now(),
        nullable=False,
        init=False,
        index=True,
    )
    jobs: Mapped[list["Job"]] = sqlalchemy.orm.relationship(
        "Job", back_populates="url", init=False, repr=False
    )
    last_seen: Mapped[datetime.datetime | None] = mapped_column(
        sqlalchemy.DateTime(timezone=True), default=None, nullable=True, index=True
    )


class RepeatURL(Base):
    __tablename__ = "repeat_urls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    url_id: Mapped[int] = mapped_column(
        sqlalchemy.ForeignKey(URL.id),
        nullable=False,
        unique=True,
        init=False,
        index=True,
    )
    url: Mapped[URL] = sqlalchemy.orm.relationship(
        URL, lazy="joined", innerjoin=True, foreign_keys=[url_id]
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        sqlalchemy.DateTime(timezone=True),
        server_default=sqlalchemy.sql.func.now(),
        nullable=False,
        init=False,
        index=True,
    )
    batch_id: Mapped[int] = mapped_column(
        sqlalchemy.ForeignKey(Batch.id),
        nullable=False,
        unique=True,
        init=False,
        index=True,
    )
    batch: Mapped[Batch] = sqlalchemy.orm.relationship(
        Batch, lazy="joined", innerjoin=True, foreign_keys=[batch_id]
    )
    interval: Mapped[int] = mapped_column(default=3600 * 4)
    active_since: Mapped[datetime.datetime | None] = mapped_column(
        sqlalchemy.DateTime(timezone=True),
        server_default=sqlalchemy.sql.func.now(),
        nullable=True,
        index=True,
        init=False,
    )  # Indicates that a repeat URL is active


class BatchJobs(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[int] = mapped_column(
        sqlalchemy.BigInteger, primary_key=True, autoincrement=True, init=False
    )
    batch_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey(Batch.id), index=True)
    job_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey("jobs.id"), index=True)

    batch: Mapped[Batch] = sqlalchemy.orm.relationship(
        Batch, lazy="joined", innerjoin=True, foreign_keys=[batch_id], viewonly=True
    )
    job: Mapped["Job"] = sqlalchemy.orm.relationship(
        "Job", lazy="joined", innerjoin=True, foreign_keys=[job_id], viewonly=True
    )

    __table_args__ = (
        sqlalchemy.UniqueConstraint("batch_id", "job_id", name="_batch_job_uc"),
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(
        sqlalchemy.BigInteger, primary_key=True, autoincrement=True, init=False
    )
    url_id: Mapped[int] = mapped_column(
        sqlalchemy.ForeignKey(URL.id),
        nullable=False,
        init=False,
        repr=False,
        index=True,
    )
    url: Mapped[URL] = sqlalchemy.orm.relationship(
        URL, lazy="joined", innerjoin=True, foreign_keys=[url_id], back_populates="jobs"
    )
    batches: Mapped[list[Batch]] = sqlalchemy.orm.relationship(
        Batch, secondary="batch_jobs", back_populates="jobs", default_factory=list
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        sqlalchemy.DateTime(timezone=True),
        server_default=sqlalchemy.sql.func.now(),
        nullable=False,
        init=False,
        index=True,
    )
    completed: Mapped[datetime.datetime | None] = mapped_column(
        sqlalchemy.DateTime(timezone=True), default=None, nullable=True, index=True
    )
    delayed_until: Mapped[datetime.datetime | None] = mapped_column(
        sqlalchemy.DateTime(timezone=True), default=None, nullable=True, index=True
    )  # If a job needs to be delayed, this is the time it should be run at
    priority: Mapped[int] = mapped_column(default=0)
    retry: Mapped[int] = mapped_column(
        sqlalchemy.SmallInteger, default=0
    )  # Number of times this job has been retried
    failed: Mapped[datetime.datetime | None] = mapped_column(
        sqlalchemy.DateTime(timezone=True), default=None, nullable=True, index=True
    )  # If a job has failed, this is the time it failed at
