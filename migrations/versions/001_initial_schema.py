"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-07-31

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tables are managed by SQLAlchemy metadata create_all in development.
    # For production Postgres, prefer: alembic revision --autogenerate
    # This stub marks the baseline revision for Compose workflows.
    pass


def downgrade() -> None:
    pass
