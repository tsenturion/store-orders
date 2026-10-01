"""Начальная схема магазина

Ревизия: 0001
Предыдущая ревизия: отсутствует
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from polka.config import settings

SCHEMA = settings().database_schema

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('event_failures',
    sa.Column('handler', sa.String(length=40), nullable=False),
    sa.Column('event_id', sa.String(length=120), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('error', sa.String(length=500), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('quarantined', sa.Boolean(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('handler', 'event_id'),
    schema=SCHEMA
    )
    op.create_table('processed_events',
    sa.Column('handler', sa.String(length=40), nullable=False),
    sa.Column('event_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('handler', 'event_id'),
    schema=SCHEMA
    )
    op.create_table('products',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sku', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('category', sa.String(length=60), nullable=False),
    sa.Column('image', sa.String(length=30), nullable=False),
    sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('stock', sa.Integer(), nullable=False),
    sa.Column('reserved', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.CheckConstraint('price > 0'),
    sa.CheckConstraint('stock >= 0 AND reserved >= 0 AND reserved <= stock'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sku'),
    schema=SCHEMA
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('password_hash', sa.String(length=256), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("role IN ('customer', 'warehouse', 'manager')"),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    schema=SCHEMA
    )
    op.create_table('auth_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('csrf', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], [f'{SCHEMA}.users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash'),
    schema=SCHEMA
    )
    op.create_index(op.f(f'ix_{SCHEMA}_auth_sessions_user_id'), 'auth_sessions', ['user_id'], unique=False, schema=SCHEMA)
    op.create_table('orders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('idempotency_key', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('total', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('recipient', sa.String(length=100), nullable=False),
    sa.Column('phone', sa.String(length=30), nullable=False),
    sa.Column('address', sa.String(length=300), nullable=False),
    sa.Column('note', sa.String(length=500), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('created','queued','picking','ready','shipped','delivered','cancelled')"),
    sa.ForeignKeyConstraint(['customer_id'], [f'{SCHEMA}.users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('customer_id', 'idempotency_key'),
    schema=SCHEMA
    )
    op.create_index(op.f(f'ix_{SCHEMA}_orders_created_at'), 'orders', ['created_at'], unique=False, schema=SCHEMA)
    op.create_index(op.f(f'ix_{SCHEMA}_orders_customer_id'), 'orders', ['customer_id'], unique=False, schema=SCHEMA)
    op.create_index(op.f(f'ix_{SCHEMA}_orders_status'), 'orders', ['status'], unique=False, schema=SCHEMA)
    op.create_table('stock_movements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('delta', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=200), nullable=False),
    sa.Column('actor', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], [f'{SCHEMA}.products.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema=SCHEMA
    )
    op.create_index(op.f(f'ix_{SCHEMA}_stock_movements_product_id'), 'stock_movements', ['product_id'], unique=False, schema=SCHEMA)
    op.create_table('documents',
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('content', sa.LargeBinary(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], [f'{SCHEMA}.orders.id'], ),
    sa.PrimaryKeyConstraint('order_id'),
    schema=SCHEMA
    )
    op.create_table('fulfillment_tasks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('assignee_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['assignee_id'], [f'{SCHEMA}.users.id'], ),
    sa.ForeignKeyConstraint(['order_id'], [f'{SCHEMA}.orders.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('order_id'),
    schema=SCHEMA
    )
    op.create_table('notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('text', sa.String(length=300), nullable=False),
    sa.Column('read', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], [f'{SCHEMA}.orders.id'], ),
    sa.ForeignKeyConstraint(['user_id'], [f'{SCHEMA}.users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema=SCHEMA
    )
    op.create_index(op.f(f'ix_{SCHEMA}_notifications_user_id'), 'notifications', ['user_id'], unique=False, schema=SCHEMA)
    op.create_table('order_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('actor', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], [f'{SCHEMA}.orders.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema=SCHEMA
    )
    op.create_index(op.f(f'ix_{SCHEMA}_order_history_order_id'), 'order_history', ['order_id'], unique=False, schema=SCHEMA)
    op.create_table('order_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('picked', sa.Integer(), nullable=False),
    sa.CheckConstraint('quantity > 0 AND picked >= 0 AND picked <= quantity'),
    sa.ForeignKeyConstraint(['order_id'], [f'{SCHEMA}.orders.id'], ),
    sa.ForeignKeyConstraint(['product_id'], [f'{SCHEMA}.products.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema=SCHEMA
    )
    op.create_index(op.f(f'ix_{SCHEMA}_order_items_order_id'), 'order_items', ['order_id'], unique=False, schema=SCHEMA)
    op.create_table('outbox_events',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('event_id', sa.String(length=36), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=60), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('retry_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], [f'{SCHEMA}.orders.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('event_id'),
    schema=SCHEMA
    )
    op.create_index('ix_outbox_pending', 'outbox_events', ['published_at', 'retry_at', 'id'], unique=False, schema=SCHEMA)
    op.create_index(op.f(f'ix_{SCHEMA}_outbox_events_order_id'), 'outbox_events', ['order_id'], unique=False, schema=SCHEMA)
    op.create_table('sales_facts',
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('total', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], [f'{SCHEMA}.orders.id'], ),
    sa.PrimaryKeyConstraint('order_id'),
    schema=SCHEMA
    )
    op.create_index(op.f(f'ix_{SCHEMA}_sales_facts_delivered_at'), 'sales_facts', ['delivered_at'], unique=False, schema=SCHEMA)


def downgrade():
    op.drop_index(op.f(f'ix_{SCHEMA}_sales_facts_delivered_at'), table_name='sales_facts', schema=SCHEMA)
    op.drop_table('sales_facts', schema=SCHEMA)
    op.drop_index(op.f(f'ix_{SCHEMA}_outbox_events_order_id'), table_name='outbox_events', schema=SCHEMA)
    op.drop_index('ix_outbox_pending', table_name='outbox_events', schema=SCHEMA)
    op.drop_table('outbox_events', schema=SCHEMA)
    op.drop_index(op.f(f'ix_{SCHEMA}_order_items_order_id'), table_name='order_items', schema=SCHEMA)
    op.drop_table('order_items', schema=SCHEMA)
    op.drop_index(op.f(f'ix_{SCHEMA}_order_history_order_id'), table_name='order_history', schema=SCHEMA)
    op.drop_table('order_history', schema=SCHEMA)
    op.drop_index(op.f(f'ix_{SCHEMA}_notifications_user_id'), table_name='notifications', schema=SCHEMA)
    op.drop_table('notifications', schema=SCHEMA)
    op.drop_table('fulfillment_tasks', schema=SCHEMA)
    op.drop_table('documents', schema=SCHEMA)
    op.drop_index(op.f(f'ix_{SCHEMA}_stock_movements_product_id'), table_name='stock_movements', schema=SCHEMA)
    op.drop_table('stock_movements', schema=SCHEMA)
    op.drop_index(op.f(f'ix_{SCHEMA}_orders_status'), table_name='orders', schema=SCHEMA)
    op.drop_index(op.f(f'ix_{SCHEMA}_orders_customer_id'), table_name='orders', schema=SCHEMA)
    op.drop_index(op.f(f'ix_{SCHEMA}_orders_created_at'), table_name='orders', schema=SCHEMA)
    op.drop_table('orders', schema=SCHEMA)
    op.drop_index(op.f(f'ix_{SCHEMA}_auth_sessions_user_id'), table_name='auth_sessions', schema=SCHEMA)
    op.drop_table('auth_sessions', schema=SCHEMA)
    op.drop_table('users', schema=SCHEMA)
    op.drop_table('products', schema=SCHEMA)
    op.drop_table('processed_events', schema=SCHEMA)
    op.drop_table('event_failures', schema=SCHEMA)
