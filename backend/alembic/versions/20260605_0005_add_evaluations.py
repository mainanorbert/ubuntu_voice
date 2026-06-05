"""Add independent RAG evaluation tables.

Revision ID: 20260605_0005
Revises: 20260528_0004
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa

revision = "20260605_0005"
down_revision = "20260528_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create per-agent evaluation datasets and latest-run result tables."""
    op.create_table(
        "evaluation_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("reference_answer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluation_questions_company_id", "evaluation_questions", ["company_id"])
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("total_questions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_questions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("company_id", name="uq_evaluation_runs_company_id"),
    )
    op.create_index("ix_evaluation_runs_company_id", "evaluation_runs", ["company_id"])
    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("reference_answer", sa.Text(), nullable=False),
        sa.Column("generated_answer", sa.Text(), server_default="", nullable=False),
        sa.Column("retrieved_sources", sa.JSON(), nullable=True),
        sa.Column("correctness_passed", sa.Boolean(), nullable=True),
        sa.Column("correctness_explanation", sa.Text(), nullable=True),
        sa.Column("relevance_passed", sa.Boolean(), nullable=True),
        sa.Column("relevance_explanation", sa.Text(), nullable=True),
        sa.Column("groundedness_passed", sa.Boolean(), nullable=True),
        sa.Column("groundedness_explanation", sa.Text(), nullable=True),
        sa.Column("retrieval_relevance_passed", sa.Boolean(), nullable=True),
        sa.Column("retrieval_relevance_explanation", sa.Text(), nullable=True),
        sa.Column("operational_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluation_results_run_id", "evaluation_results", ["run_id"])


def downgrade() -> None:
    """Drop independent evaluation tables."""
    op.drop_table("evaluation_results")
    op.drop_table("evaluation_runs")
    op.drop_table("evaluation_questions")
