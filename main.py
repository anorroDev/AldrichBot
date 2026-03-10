import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import aiosqlite

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(command_prefix='#', intents=intents, help_command=None)
        self.db = None

    async def setup_hook(self):
        self.db = await aiosqlite.connect('mybot.db')
     
        # Создание базы данных и таблицы        
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

        try: await self.db.execute("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1")
        except: pass
        try: await self.db.execute("ALTER TABLE users ADD COLUMN stat_points INTEGER DEFAULT 0")
        except: pass
        try: await self.db.execute("ALTER TABLE users ADD COLUMN lost_souls INTEGER DEFAULT 0")
        except: pass
        try: await self.db.execute("ALTER TABLE users ADD COLUMN char_name TEXT")
        except: pass
        try: await self.db.execute("ALTER TABLE users ADD COLUMN current_location TEXT DEFAULT 'graveyard'")
        except: pass
        try: await self.db.execute("ALTER TABLE users ADD COLUMN voice_time INTEGER DEFAULT 0")
        except: pass
        try: await self.db.execute("ALTER TABLE users ADD COLUMN message_count INTEGER DEFAULT 0")
        except: pass
        try: await self.db.execute("ALTER TABLE users ADD COLUMN total_souls_farmed INTEGER DEFAULT 0")
        except: pass
        try: await self.db.execute("ALTER TABLE users ADD COLUMN energy INTEGER DEFAULT 5")
        except: pass
        try: await self.db.execute("ALTER TABLE users ADD COLUMN last_energy_update INTEGER DEFAULT 0")
        except: pass
        try: await self.db.execute("ALTER TABLE users ADD COLUMN successful_hunts INTEGER DEFAULT 0")
        except: pass
        try: await self.db.execute("ALTER TABLE users ADD COLUMN strength INTEGER DEFAULT 1")
        except: pass
        try: await self.db.execute("ALTER TABLE users ADD COLUMN vitality INTEGER DEFAULT 1")
        except: pass
        try: await self.db.execute("ALTER TABLE users ADD COLUMN luck INTEGER DEFAULT 1")
        except: pass
        
        await self.db.commit()    
        print('Database connected and tables ensured.')

        # Загрузка когов
        await self.load_extension('cogs.general')
        await self.load_extension('cogs.moderation')
        await self.load_extension('cogs.activity')
        await self.load_extension("cogs.game")
        await self.load_extension("cogs.voice")
        await self.load_extension("cogs.giveaway")
        await self.load_extension("cogs.achievements")
        print('Cogs loaded successfully.')
          

        await self.tree.sync()
        print('Slash commands synced successfully.')

    # Закрытие базы данных
    async def close(self):
        if self.db:
            await self.db.close()
            print('Database connection closed.')
        await super().close()

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------------------------------------')
        await self.tree.sync()

bot = MyBot()

if __name__ == '__main__':
    bot.run(TOKEN)