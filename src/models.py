import datetime
from sqlalchemy.orm import Mapped, mapped_column
import sqlalchemy.ext.asyncio
import sqlalchemy.orm


class Base(
    sqlalchemy.orm.MappedAsDataclass,
    sqlalchemy.ext.asyncio.AsyncAttrs,
    sqlalchemy.orm.DeclarativeBase,
):
    pass


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

    jobs: Mapped[list["Job"]] = sqlalchemy.orm.relationship(
        "Job", secondary="batch_jobs", back_populates="batches", init=False, repr=False
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
    batches: Mapped[list[Batch]] = sqlalchemy.orm.relationship(
        Batch, secondary="batch_jobs", back_populates="jobs"
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
