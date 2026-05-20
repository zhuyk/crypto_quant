"""initial schema - all existing models

Revision ID: 001_initial
Revises: None
Create Date: 2026-05-20

All tables from app.models.user and app.models.trade:
- users, accounts
- strategies, strategy_instances
- backtest_runs
- trades, positions, klines
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === Users & Accounts ===
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(64), nullable=False),
        sa.Column('email', sa.String(128), nullable=True),
        sa.Column('password_hash', sa.String(256), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_username', 'users', ['username'])

    op.create_table(
        'accounts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('exchange', sa.String(32), nullable=False, server_default='binance'),
        sa.Column('api_key', sa.String(256), nullable=False),
        sa.Column('api_secret', sa.String(256), nullable=False),
        sa.Column('passphrase', sa.String(256), nullable=True),
        sa.Column('is_testnet', sa.Boolean(), default=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_accounts_user_id', 'accounts', ['user_id'])

    # === Strategies ===
    op.create_table(
        'strategies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('category', sa.String(64), nullable=False),
        sa.Column('class_name', sa.String(128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('default_params', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_strategies_name', 'strategies', ['name'])
    op.create_index('ix_strategies_category', 'strategies', ['category'])

    op.create_table(
        'strategy_instances',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('params', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_strategy_instances_user_id', 'strategy_instances', ['user_id'])

    # === Trading ===
    op.create_table(
        'trades',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('strategy_instance_id', sa.Integer(), nullable=True),
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('side', sa.String(16), nullable=False),
        sa.Column('type', sa.String(32), server_default='market'),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('filled_amount', sa.Float(), server_default='0'),
        sa.Column('filled_price', sa.Float(), server_default='0'),
        sa.Column('fee', sa.Float(), server_default='0'),
        sa.Column('fee_currency', sa.String(16), nullable=True),
        sa.Column('status', sa.String(32), server_default='pending'),
        sa.Column('order_id', sa.String(128), nullable=True, unique=True),
        sa.Column('pnl', sa.Float(), server_default='0'),
        sa.Column('pnl_pct', sa.Float(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['strategy_instance_id'], ['strategy_instances.id']),
    )
    op.create_index('ix_trades_symbol', 'trades', ['symbol'])
    op.create_index('ix_trades_user_id', 'trades', ['user_id'])

    op.create_table(
        'positions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('strategy_instance_id', sa.Integer(), nullable=True),
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('side', sa.String(16), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('current_price', sa.Float(), server_default='0'),
        sa.Column('stop_loss', sa.Float(), nullable=True),
        sa.Column('take_profit', sa.Float(), nullable=True),
        sa.Column('unrealized_pnl', sa.Float(), server_default='0'),
        sa.Column('realized_pnl', sa.Float(), server_default='0'),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('opened_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['strategy_instance_id'], ['strategy_instances.id']),
    )
    op.create_index('ix_positions_symbol', 'positions', ['symbol'])
    op.create_index('ix_positions_user_id', 'positions', ['user_id'])

    # === Market Data ===
    op.create_table(
        'klines',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('exchange', sa.String(32), nullable=False),
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('timeframe', sa.String(16), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_klines_exchange', 'klines', ['exchange'])
    op.create_index('ix_klines_symbol', 'klines', ['symbol'])
    op.create_index('ix_klines_timeframe', 'klines', ['timeframe'])
    op.create_index('ix_klines_timestamp', 'klines', ['timestamp'])
    # 复合索引用于快速增量查询
    op.create_index(
        'ix_klines_lookup',
        'klines',
        ['exchange', 'symbol', 'timeframe', 'timestamp'],
        unique=True,
    )

    # === Backtest ===
    op.create_table(
        'backtest_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('strategy_name', sa.String(128), nullable=False),
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('timeframe', sa.String(16), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('initial_capital', sa.Float(), nullable=False, server_default='100000'),
        sa.Column('final_capital', sa.Float(), nullable=True),
        sa.Column('total_return', sa.Float(), nullable=True),
        sa.Column('sharpe_ratio', sa.Float(), nullable=True),
        sa.Column('max_drawdown', sa.Float(), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('win_rate', sa.Float(), nullable=True),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(32), server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )


def downgrade() -> None:
    op.drop_table('backtest_runs')
    op.drop_table('klines')
    op.drop_table('positions')
    op.drop_table('trades')
    op.drop_table('strategy_instances')
    op.drop_table('strategies')
    op.drop_table('accounts')
    op.drop_table('users')
