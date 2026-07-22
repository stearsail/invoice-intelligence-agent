"""create ledgerentry base table

Revision ID: 60d54c10ea33
Revises:
Create Date: 2026-07-22 15:54:38.942730

Genesis of the schema. `ledgerentry` was originally created outside Alembic
(SQLModel.metadata.create_all, via scripts/init_db.py), so the chain began by
ALTERing a table nothing had created and `alembic upgrade head` failed on an
empty database. This revision supplies that missing starting point, in the
shape the table had before 53dd87d9a3f7 added the review columns. The `job`
table needs no equivalent — 3be1f97995b0 already creates it.

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = "60d54c10ea33"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ledgerentry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_number", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("vendor_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("grand_total", sa.Numeric(), nullable=False),
        sa.Column("invoice_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ledgerentry_invoice_number"),
        "ledgerentry",
        ["invoice_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ledgerentry_vendor_name"),
        "ledgerentry",
        ["vendor_name"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_ledgerentry_vendor_name"), table_name="ledgerentry")
    op.drop_index(op.f("ix_ledgerentry_invoice_number"), table_name="ledgerentry")
    op.drop_table("ledgerentry")
