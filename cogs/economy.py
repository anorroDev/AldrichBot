import discord
from discord.ext import commands
from discord import app_commands


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        query = "INSERT INTO users (id, balance) VALUES (?, 1) ON CONFLICT(id) DO UPDATE SET balance = balance + 1"
        await self.bot.db.execute(query, (message.author.id,))
        await self.bot.db.commit()

    @app_commands.command(name="balance", description="Показать баланс пользователя")
    @app_commands.describe(member="Выберите пользователя или оставьте пустым для отображения вашего баланса")

    async def balance(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        target = member or interaction.user
        async with self.bot.db.execute("SELECT balance FROM users WHERE id = ?", (target.id,)) as cursor:
            row = await cursor.fetchone()
        user_balance = row[0] if row else 0

        await interaction.response.send_message(f"💰 Баланс пользователя **{target.display_name}**: `{user_balance}` монет")

    @balance.error
    async def balance_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        print(f"[ОШИБКА В БАЛАНСЕ]: {error}") 
        
        await interaction.response.send_message(f"❌ Системная ошибка: `{error}`", ephemeral=True)
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))