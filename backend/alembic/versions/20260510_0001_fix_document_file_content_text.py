"""Fix documents.file_content type for extracted text.

Revision ID: 20260510_0001
Revises:
Create Date: 2026-05-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert legacy PostgreSQL bytea columns to text when the table exists."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                column_type text;
            BEGIN
                SELECT data_type
                INTO column_type
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'documents'
                  AND column_name = 'file_content';

                IF column_type = 'bytea' THEN
                    ALTER TABLE documents ALTER COLUMN file_content DROP DEFAULT;
                    ALTER TABLE documents
                        ALTER COLUMN file_content TYPE text
                        USING CASE
                            WHEN file_content IS NULL THEN ''
                            WHEN octet_length(file_content) = 0 THEN ''
                            ELSE encode(file_content, 'escape')
                        END;
                    ALTER TABLE documents ALTER COLUMN file_content SET DEFAULT '';
                    ALTER TABLE documents ALTER COLUMN file_content SET NOT NULL;
                END IF;
            END $$;
            """
        )
    )


def downgrade() -> None:
    """Restore the legacy bytea type if this migration is rolled back."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                column_type text;
            BEGIN
                SELECT data_type
                INTO column_type
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'documents'
                  AND column_name = 'file_content';

                IF column_type = 'text' THEN
                    ALTER TABLE documents ALTER COLUMN file_content DROP DEFAULT;
                    ALTER TABLE documents
                        ALTER COLUMN file_content TYPE bytea
                        USING convert_to(COALESCE(file_content, ''), 'UTF8');
                    ALTER TABLE documents ALTER COLUMN file_content SET DEFAULT ''::bytea;
                    ALTER TABLE documents ALTER COLUMN file_content SET NOT NULL;
                END IF;
            END $$;
            """
        )
    )
