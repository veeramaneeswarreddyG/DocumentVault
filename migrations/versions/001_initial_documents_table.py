"""Initial documents table creation

Revision ID: 001_initial_documents_table
Revises: 
Create Date: 2026-11-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_initial_documents_table'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'documents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('stored_filename', sa.String(length=255), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_sha256'), 'documents', ['sha256'], unique=False)
    op.create_index(op.f('ix_documents_stored_filename'), 'documents', ['stored_filename'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_documents_stored_filename'), table_name='documents')
    op.drop_index(op.f('ix_documents_sha256'), table_name='documents')
    op.drop_table('documents')
