"""Add some indices

Revision ID: b3a25a74012d
Revises: 930b75030da8
Create Date: 2024-01-01 21:30:13.279703

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b3a25a74012d"
down_revision: Union[str, None] = "930b75030da8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(
        op.f("ix_batch_jobs_batch_id"), "batch_jobs", ["batch_id"], unique=False
    )
    op.create_index(
        op.f("ix_batch_jobs_job_id"), "batch_jobs", ["job_id"], unique=False
    )
    op.create_index(op.f("ix_jobs_url_id"), "jobs", ["url_id"], unique=False)
    op.drop_constraint("repeat_urls_batch_id_key", "repeat_urls", type_="unique")
    op.drop_constraint("repeat_urls_url_id_key", "repeat_urls", type_="unique")
    op.create_index(
        op.f("ix_repeat_urls_batch_id"), "repeat_urls", ["batch_id"], unique=True
    )
    op.create_index(
        op.f("ix_repeat_urls_url_id"), "repeat_urls", ["url_id"], unique=True
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_repeat_urls_url_id"), table_name="repeat_urls")
    op.drop_index(op.f("ix_repeat_urls_batch_id"), table_name="repeat_urls")
    op.create_unique_constraint("repeat_urls_url_id_key", "repeat_urls", ["url_id"])
    op.create_unique_constraint("repeat_urls_batch_id_key", "repeat_urls", ["batch_id"])
    op.drop_index(op.f("ix_jobs_url_id"), table_name="jobs")
    op.drop_index(op.f("ix_batch_jobs_job_id"), table_name="batch_jobs")
    op.drop_index(op.f("ix_batch_jobs_batch_id"), table_name="batch_jobs")
    # ### end Alembic commands ###
