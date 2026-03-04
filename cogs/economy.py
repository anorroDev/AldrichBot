import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import random
import asyncio


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="balance", description="Посмотреть сколько у тебя душ")
    @app_commands.describe(member="Выберите пользователя, чтобы посмотреть его баланс (необязательно)")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        target = member or interaction.user
        
        async with self.bot.db.execute("SELECT balance, bank FROM users WHERE id = ?", (target.id,)) as cursor:
            row = await cursor.fetchone()
            
        balance = row[0] if row else 0
        bank = row[1] if row and row[1] else 0 

        embed = discord.Embed(title=f"⚖️ Сосуд душ: {target.display_name}", color=discord.Color.dark_purple())
        embed.add_field(name="С собой:", value=f"`{balance}` 👻", inline=True)
        embed.add_field(name="В тайнике:", value=f"`{bank}` 🏰", inline=True)
        
        await interaction.response.send_message(embed=embed)

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

    @app_commands.command(name="deposit", description="Спрятать души в безопасный тайник")
    async def deposit(self, interaction: discord.Interaction, amount: int) -> None:
        if amount <= 0:
            await interaction.response.send_message("❌ Нельзя спрятать пустоту!", ephemeral=True)
            return

        async with self.bot.db.execute("SELECT balance FROM users WHERE id = ?", (interaction.user.id,)) as cursor:
            row = await cursor.fetchone()
        balance = row[0] if row else 0

        if balance < amount:
            await interaction.response.send_message("❌ У тебя нет столько душ с собой!", ephemeral=True)
            return

        await self.bot.db.execute("UPDATE users SET balance = balance - ?, bank = bank + ? WHERE id = ?", (amount, amount, interaction.user.id))
        await self.bot.db.commit()

        await interaction.response.send_message(f"🏰 `{amount}` душ отправлено в тайник.")

    @app_commands.command(name="withdraw", description="Забрать души из тайника")
    async def withdraw(self, interaction: discord.Interaction, amount: int) -> None:
        if amount <= 0:
            return await interaction.response.send_message("❌ Укажи нормальную сумму!", ephemeral=True)

        async with self.bot.db.execute("SELECT bank FROM users WHERE id = ?", (interaction.user.id,)) as cursor:
            row = await cursor.fetchone()
        bank = row[0] if row and row[0] else 0

        if bank < amount:
            return await interaction.response.send_message("❌ В твоем тайнике нет столько душ!", ephemeral=True)

        await self.bot.db.execute("UPDATE users SET balance = balance + ?, bank = bank - ? WHERE id = ?", (amount, amount, interaction.user.id))
        await self.bot.db.commit()

        await interaction.response.send_message(f"👻 Ты забрал `{amount}` душ из тайника.")

    # ---------------------------------------------- Заработок ----------------------------------------------
    def get_farm_cooldown(interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            return app_commands.Cooldown(1, 3600)

        role_ids = [role.id for role in interaction.user.roles]

        if 1446126804908638348 in role_ids:
            return None

        return app_commands.Cooldown(1, 3600)


    @app_commands.command(name="farm", description="Отправиться на охоту за душами. ОСТОРОЖНО: Можно потерять всё!")
    @app_commands.checks.dynamic_cooldown(get_farm_cooldown, key=lambda i: i.user.id)
    async def farm(self, interaction: discord.Interaction) -> None:
        chance = random.randint(1, 100)
        
        if chance <= 15:
            await self.bot.db.execute("UPDATE users SET balance = 0 WHERE id = ?", (interaction.user.id,))
            await self.bot.db.commit()
            
            embed = discord.Embed(
                title="☠️ ВЫ ПОГИБЛИ!", 
                description="Тьма поглотила вас на охоте. **Вы потеряли все души**, которые были при вас!", 
                color=discord.Color.red()
            )
            embed.set_footer(text="Надеюсь, вы успели спрятать часть в тайник...")
            await interaction.response.send_message(embed=embed)
        else:
            reward = random.randint(20, 70) 
            
            query = "INSERT INTO users (id, balance, bank) VALUES (?, ?, 0) ON CONFLICT(id) DO UPDATE SET balance = balance + ?"
            await self.bot.db.execute(query, (interaction.user.id, reward, reward))
            await self.bot.db.commit()
            
            await interaction.response.send_message(f"⚔️ Охота прошла успешно! Вы поглотили `{reward}` душ.\n*Не забудьте спрятать их в тайник (`/deposit`), пока вас не убили!*")


    @farm.error
    async def farm_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.CommandOnCooldown):
            minutes_left = int(error.retry_after // 60)
            seconds_left = int(error.retry_after % 60)
            await interaction.response.send_message(
                f"⏳ Твои силы иссякли. Следующая охота будет доступна через `{minutes_left} мин. {seconds_left} сек.`", 
                ephemeral=True
            )
        else:
            print(f"Ошибка в фарме: {error}")
            await interaction.response.send_message("❌ Системная ошибка при попытке выйти на охоту.", ephemeral=True)

    # ---------------------------------------------- Административные команды ----------------------------------------------
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