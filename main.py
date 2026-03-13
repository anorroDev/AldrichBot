import discord
from discord.ext import commands
import os
import logging
from dotenv import load_dotenv
import aiosqlite


load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COGS = [
    'cogs.general',
    'cogs.moderation',
    'cogs.activity',
    'cogs.game',
    'cogs.voice',
    'cogs.achievements',
]


async def ensure_column(db: aiosqlite.Connection, table: str, column: str, definition: str) -> None:
    try:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    except aiosqlite.OperationalError as error:
        if "duplicate column name" not in str(error).lower():
            raise

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(command_prefix='#', intents=intents, help_command=None)
        self.db = None

    async def setup_hook(self):
        self.db = await aiosqlite.connect('mybot.db')

        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                activity_points INTEGER DEFAULT 0,
                total_activity_points INTEGER DEFAULT 0
            )
        """)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS user_achievements (
                user_id INTEGER,
                achievement_id TEXT,
                UNIQUE(user_id, achievement_id)
            )
        """)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER,
                item_name TEXT,
                amount INTEGER DEFAULT 0,
                UNIQUE(user_id, item_name)
            )
        """)

        await ensure_column(self.db, 'users', 'level', 'INTEGER DEFAULT 1')
        await ensure_column(self.db, 'users', 'stat_points', 'INTEGER DEFAULT 0')
        await ensure_column(self.db, 'users', 'lost_souls', 'INTEGER DEFAULT 0')
        await ensure_column(self.db, 'users', 'char_name', 'TEXT')
        await ensure_column(self.db, 'users', 'current_location', "TEXT DEFAULT 'graveyard'")
        await ensure_column(self.db, 'users', 'voice_time', 'INTEGER DEFAULT 0')
        await ensure_column(self.db, 'users', 'message_count', 'INTEGER DEFAULT 0')
        await ensure_column(self.db, 'users', 'total_souls_farmed', 'INTEGER DEFAULT 0')
        await ensure_column(self.db, 'users', 'energy', 'INTEGER DEFAULT 5')
        await ensure_column(self.db, 'users', 'last_energy_update', 'INTEGER DEFAULT 0')
        await ensure_column(self.db, 'users', 'successful_hunts', 'INTEGER DEFAULT 0')
        await ensure_column(self.db, 'users', 'strength', 'INTEGER DEFAULT 1')
        await ensure_column(self.db, 'users', 'vitality', 'INTEGER DEFAULT 1')
        await ensure_column(self.db, 'users', 'luck', 'INTEGER DEFAULT 1')
        await ensure_column(self.db, 'inventory', 'equipped', 'INTEGER DEFAULT 0')

        await self.db.commit()
        logger.info('Database connected and tables ensured.')

        # Загрузка когов
        for cog in COGS:
            await self.load_extension(cog)
            logger.info('Loaded cog: %s', cog)

        logger.info('Cogs loaded successfully.')

        await self.tree.sync()
        logger.info('Slash commands synced successfully.')

    async def close(self):
        if self.db:
            await self.db.close()
            logger.info('Database connection closed.')
        await super().close()

    async def on_ready(self):
        logger.info('Logged in as %s (ID: %s)', self.user, self.user.id)
        logger.info('--------------------------------------------------------------')

bot = MyBot()

if __name__ == '__main__':
    if not TOKEN:
        raise RuntimeError('BOT_TOKEN is not set in the environment.')
    bot.run(TOKEN)
