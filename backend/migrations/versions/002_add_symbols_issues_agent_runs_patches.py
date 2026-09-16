"""add symbols issues agent_runs tool_executions patches

Revision ID: 002_add_symbols_issues_agent_runs_patches
Revises: 001_initial_schema
Create Date: 2026-11-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '002_add_symbols_issues_agent_runs_patches'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # symbols
    op.create_table(
        'symbols',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_id', sa.String(length=36), sa.ForeignKey('repository_files.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('symbol_type', sa.String(length=100), nullable=False),
        sa.Column('parent_name', sa.String(length=255), nullable=True),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('docstring', sa.Text(), nullable=True),
        sa.Column('decorators_json', sa.Text(), nullable=True),
        sa.Column('dependencies_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False)
    )
    op.create_index('ix_symbols_repository_id', 'symbols', ['repository_id'])
    op.create_index('ix_symbols_file_id', 'symbols', ['file_id'])
    op.create_index('ix_symbols_name', 'symbols', ['name'])
    op.create_index('ix_symbols_symbol_type', 'symbols', ['symbol_type'])

    # issues
    op.create_table(
        'issues',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        sa.Column('relevant_file', sa.String(length=1024), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)
    )
    op.create_index('ix_issues_repository_id', 'issues', ['repository_id'])
    op.create_index('ix_issues_user_id', 'issues', ['user_id'])

    # agent_runs
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('issue_id', sa.String(length=36), sa.ForeignKey('issues.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='running'),
        sa.Column('current_step', sa.String(length=100), nullable=False, server_default='started'),
        sa.Column('iterations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('root_cause_analysis', sa.Text(), nullable=True),
        sa.Column('proposed_fix_summary', sa.Text(), nullable=True),
        sa.Column('generated_tests', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_log_json', sa.Text(), nullable=True),
        sa.Column('token_usage_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_agent_runs_repository_id', 'agent_runs', ['repository_id'])
    op.create_index('ix_agent_runs_issue_id', 'agent_runs', ['issue_id'])
    op.create_index('ix_agent_runs_user_id', 'agent_runs', ['user_id'])

    # tool_executions
    op.create_table(
        'tool_executions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('agent_run_id', sa.String(length=36), sa.ForeignKey('agent_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tool_name', sa.String(length=100), nullable=False),
        sa.Column('arguments_json', sa.Text(), nullable=False),
        sa.Column('result_json', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='success'),
        sa.Column('execution_time_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False)
    )
    op.create_index('ix_tool_executions_agent_run_id', 'tool_executions', ['agent_run_id'])
    op.create_index('ix_tool_executions_tool_name', 'tool_executions', ['tool_name'])

    # patches
    op.create_table(
        'patches',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_run_id', sa.String(length=36), sa.ForeignKey('agent_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('issue_id', sa.String(length=36), sa.ForeignKey('issues.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_file', sa.String(length=1024), nullable=False),
        sa.Column('unified_diff', sa.Text(), nullable=False),
        sa.Column('original_commit_sha', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending_approval'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tests_passed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_patches_repository_id', 'patches', ['repository_id'])
    op.create_index('ix_patches_agent_run_id', 'patches', ['agent_run_id'])
    op.create_index('ix_patches_issue_id', 'patches', ['issue_id'])
    op.create_index('ix_patches_user_id', 'patches', ['user_id'])


def downgrade() -> None:
    op.drop_table('patches')
    op.drop_table('tool_executions')
    op.drop_table('agent_runs')
    op.drop_table('issues')
    op.drop_table('symbols')
