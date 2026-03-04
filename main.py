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
        # Загрузка когов
        await self.load_extension('cogs.general')
        await self.load_extension('cogs.moderation')
        await self.load_extension('cogs.ui_elements')
        await self.load_extension('cogs.economy')
        print('Cogs loaded successfully.')
        
        # Инициализация базы данных
        self.db = await aiosqlite.connect('mybot.db')
        
        # Создание таблиц
        try:
            await self.db.execute("ALTER TABLE users ADD COLUMN bank INTEGER DEFAULT 0")
        except aiosqlite.OperationalError:
            pass    
        await self.db.commit()
        print('Database connected and tables ensured.')


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