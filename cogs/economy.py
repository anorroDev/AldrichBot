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

    @app_commands.command(name="leaderboard", description="Показать топ-10 самых богатых пользователей сервера")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        async with self.bot.db.execute("SELECT id, balance FROM users ORDER BY balance DESC LIMIT 10") as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await interaction.followup.send("Ошибка базы данных или нет данных для отображения таблицы лидеров.")
            return

        embed = discord.Embed(
            title="🏆 Таблица лидеров (Топ-10)",
            description="Самые богатые участники:\n\n",
            color=discord.Color.gold() # Делаем полоску золотой!
        )

        for index, row in enumerate(rows, start=1):
            user_id = row[0]
            balance = row[1]
            
            if index == 1:
                medal = "🥇"
            elif index == 2:
                medal = "🥈"
            elif index == 3:
                medal = "🥉"
            else:
                medal = f"**{index}.**"
            
            # <@{user_id}> - превратит ID в имя (упоминание) пользователя
            embed.description += f"{medal} <@{user_id}> — `{balance}` монет\n"

        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))