import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(command_prefix='!', intents=intents, help_command=None)

    async def setup_hook(self):
        await self.load_extension('cogs.general')
        print('Cogs General loaded successfully.')

        await self.tree.sync()
        print('Slash commands synced successfully.')


    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------------------------------------')
        await self.tree.sync()

bot = MyBot()

if __name__ == '__main__':
    bot.run(TOKEN)