from sqlalchemy import *
from migrate import *


from migrate.changeset import schema
pre_meta = MetaData()
post_meta = MetaData()
gallery = Table('gallery', post_meta,
    Column('id', Integer, primary_key=True, nullable=False),
    Column('favorite', Boolean),
    Column('dead', Boolean, default=ColumnDefault(False)),
    Column('path', Text),
    Column('type', Integer, nullable=False),
    Column('thumbnail_path', Text),
    Column('image_hash', Text),
    Column('uuid', Text, nullable=False),
    Column('last_read', Integer),
    Column('read_count', Integer, nullable=False, default=ColumnDefault(0)),
    Column('time_added', Integer),
)


def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine; bind
    # migrate_engine to your metadata
    pre_meta.bind = migrate_engine
    post_meta.bind = migrate_engine
    post_meta.tables['gallery'].columns['favorite'].create()


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    pre_meta.bind = migrate_engine
    post_meta.bind = migrate_engine
    post_meta.tables['gallery'].columns['favorite'].drop()
