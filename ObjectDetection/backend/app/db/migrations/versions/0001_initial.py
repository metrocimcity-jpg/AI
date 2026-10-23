"""Initial schema."""

from __future__ import annotations

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db.models import Base

    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    from app.db.models import Base

    Base.metadata.drop_all(op.get_bind())
