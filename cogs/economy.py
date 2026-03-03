import discord
from discord.ext import commands
from discord import app_commands


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="balance", description="Показать баланс пользователя")
    @app_commands.describe(member="Выберите пользователя или оставьте пустым для отображения вашего баланса")

    async def balance(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        target = member or interaction.user
        async with self.bot.db.execute("SELECT balance FROM users WHERE id = ?", (target.id,)) as cursor:
            row = await cursor.fetchone()
        user_balance = row[0] if row else 0

        await interaction.response.send_message(f"💰 Баланс пользователя **{target.display_name}**: `{user_balance}` душ")

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
            color=discord.Color.gold()
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
            embed.description += f"{medal} <@{user_id}> — `{balance}` душ\n"

        await interaction.followup.send(embed=embed)

    @leaderboard.error
    async def leaderboard_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        print(f"[ОШИБКА В ЛИДЕРБОРДЕ]: {error}") 
        
        await interaction.response.send_message(f"❌ Системная ошибка: `{error}`", ephemeral=True)


    @app_commands.command(name="change_balance", description="Изменить баланс пользователя")
    @app_commands.checks.has_permissions(administrator=True) 
    @app_commands.describe(
        action="Что сделать с балансом?", 
        member="Выберите пользователя", 
        amount="Укажите сумму"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="✏️ Установить (Set)", value="set"),
        app_commands.Choice(name="➕ Добавить (Add)", value="add"),
        app_commands.Choice(name="➖ Отнять (Remove)", value="remove")
    ])
    async def change_balance(self, interaction: discord.Interaction, action: app_commands.Choice[str], member: discord.Member, amount: int) -> None:
        
        async with self.bot.db.execute("SELECT balance FROM users WHERE id = ?", (member.id,)) as cursor:
            row = await cursor.fetchone()
        
        current_balance = row[0] if row else 0 
        
        if action.value == "set":
            new_balance = amount
            action_text = "установлен на"
        elif action.value == "add":
            new_balance = current_balance + amount
            action_text = "пополнен на"
        elif action.value == "remove":
            new_balance = current_balance - amount
            action_text = "уменьшен на"
            # Защита от отрицательного баланса 
            # if new_balance < 0:
            #    new_balance = 0 
                
        query = "INSERT INTO users (id, balance) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET balance = ?"
        await self.bot.db.execute(query, (member.id, new_balance, new_balance))
        await self.bot.db.commit()

        await interaction.response.send_message(f"💰 Баланс **{member.display_name}** {action_text} `{amount}` душ. \n🏦 Текущий счет: `{new_balance}`", ephemeral=True)

    @change_balance.error
    async def change_balance_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Эта команда доступна только администраторам!", ephemeral=True)
        else:
            print(f"[ОШИБКА В ИЗМЕНЕНИИ БАЛАНСА]: {error}") 
            await interaction.response.send_message(f"❌ Системная ошибка: `{error}`", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))