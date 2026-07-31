"""Add expiring WhatsApp agent routing sessions.

Revision ID: 20260731_0006
Revises: 20260605_0005
Create Date: 2026-07-31
"""

from alembic import op
import sqlalchemy as sa

revision = "20260731_0006"
down_revision = "20260605_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create privacy-preserving WhatsApp participant-to-agent sessions."""
    op.create_table(
        "whatsapp_agent_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recipient_number", sa.Text(), nullable=False),
        sa.Column("participant_hash", sa.String(64), nullable=False),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "recipient_number",
            "participant_hash",
            name="uq_whatsapp_sessions_recipient_participant",
        ),
    )
    op.create_index(
        "ix_whatsapp_agent_sessions_company_id",
        "whatsapp_agent_sessions",
        ["company_id"],
    )


def downgrade() -> None:
    """Drop WhatsApp agent routing sessions."""
    op.drop_table("whatsapp_agent_sessions")
