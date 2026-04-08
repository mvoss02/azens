import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from core.config import settings
from core.database import Base
from models.cv import (
    CV,  # noqa: F401 - NEEDED: Base.metadata only knows about models that have been imported
)
from models.feedback import (
    Feedback,  # noqa: F401 - NEEDED: Base.metadata only knows about models that have been imported
)
from models.question import (
    Question,  # noqa: F401 - NEEDED: Base.metadata only knows about models that have been imported
)
from models.session import (
    Session,  # noqa: F401 - NEEDED: Base.metadata only knows about models that have been imported
)
from models.subscription import (
    Subscription,  # noqa: F401 - NEEDED: Base.metadata only knows about models that have been imported
)
from models.transcript import (
    Transcript,  # noqa: F401 - NEEDED: Base.metadata only knows about models that have been imported
)
from models.user import (
    User,  # noqa: F401 - NEEDED: Base.metadata only knows about models that have been imported
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# Override the URL from alembic.ini with our app's config
config.set_main_option('sqlalchemy.url', settings.database_url)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )

    with context.begin_transaction():
        context.run_migrations()


# This helper is sync — alembic's context.configure is not async
def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=NullPool,
    )

    async with connectable.connect() as connection:
        # run_sync bridges async connection - sync alembic internals
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
