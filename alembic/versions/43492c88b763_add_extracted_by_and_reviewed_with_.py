"""add extracted_by and reviewed_with_changes to ledgerentry

Revision ID: 43492c88b763
Revises: c05040306f69
Create Date: 2026-07-28 14:33:31.429915

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "43492c88b763"
down_revision: Union[str, Sequence[str], None] = "c05040306f69"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "ledgerentry", sa.Column("extracted_by", sa.String(), nullable=True)
    )
    op.add_column(
        "ledgerentry", sa.Column("reviewed_with_changes", sa.Boolean(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ledgerentry", "reviewed_with_changes")
    op.drop_column("ledgerentry", "extracted_by")
