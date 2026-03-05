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

    @app_commands.command(name="leaderboard", description="Посмотреть доску почета (Топ по Душам и Активности)")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            description="## 🏆 Доска почета сервера\n==========\n", 
            color=discord.Color.gold()
        )

        async with self.bot.db.execute("SELECT id, (balance + bank) as total_souls FROM users WHERE total_souls > 0 ORDER BY total_souls DESC LIMIT 5") as cursor:
            souls_rows = await cursor.fetchall()

        souls_text = ""
        for index, row in enumerate(souls_rows, start=1):
            medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else "🏅"
            souls_text += f"{medal} <@{row[0]}> — `{row[1]}` 👻\n"

        if not souls_text:
            souls_text = "Пока никто не собрал души...\n"

        souls_text += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
        embed.add_field(name="👻 Топ богачей", value=souls_text, inline=False)


        async with self.bot.db.execute("SELECT id, activity_points, total_activity_points FROM users WHERE activity_points > 0 ORDER BY activity_points DESC LIMIT 5") as cursor:
            ap_rows = await cursor.fetchall()

        ap_text = ""
        for index, row in enumerate(ap_rows, start=1):
            medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else "🏅"
            ap_text += f"{medal} <@{row[0]}> — Текущие: `{row[1]}` (Всего: `{row[2]}`)\n"

        if not ap_text:
            ap_text = "Пока никто не проявил активность...\n"

        ap_text += "\n=========="
        
        embed.add_field(name="🏆 Топ активных", value=ap_text, inline=False)

        embed.set_footer(text="Будьте активней, чтобы попасть сюда!")

        await interaction.response.send_message(embed=embed)

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

# ----------------------------------------------- Магазин  ----------------------------------------------
    @app_commands.command(name="shop", description="🛒 Открыть магазин ролей за Очки Активности")
    async def shop(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            description="# 🛒 Магазин Ролей\nЗдесь вы можете обменять Очки Активности (АП) на эксклюзивные роли.\n==========\n",
            color=discord.Color.green()
        )
        
        for item in SHOP_ITEMS:
            role = interaction.guild.get_role(int(item["value"]))
            role_name = role.name if role else "Неизвестная роль"
            
            embed.add_field(
                name=f"{item['emoji']} {role_name}", 
                value=f"Цена: `{item['price']}` АП\n*{item['description']}*", 
                inline=False
            )
            
        embed.set_footer(text="Выберите роль в меню ниже, чтобы совершить покупку!")

        await interaction.response.send_message(embed=embed, view=ShopView(self.bot, interaction.guild))

SHOP_ITEMS = [
    {
        "value": 1477601614171738193,
        "price": 50,
        "description": "Тестовая роль для проверки работы магазина. Не имеет особых привилегий.",
        "emoji": "🧪"
    }
]

class ShopSelect(discord.ui.Select):
    def __init__(self, bot, guild: discord.Guild):
        self.bot = bot
        options = []
        
        for item in SHOP_ITEMS:
            role = guild.get_role(int(item["value"]))
            role_name = role.name if role else f"Удаленная роль ({item['value']})"
            
            options.append(
                discord.SelectOption(
                    label=role_name,
                    description=f"Цена: {item['price']} АП",
                    value=str(item["value"]),
                    emoji=item["emoji"]
                )
            )
            
        super().__init__(placeholder="Выберите роль для покупки...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        item = next((x for x in SHOP_ITEMS if x["value"] == role_id), None)
        
        if not item:
            return await interaction.response.send_message("❌ Ошибка: Товар не найден.", ephemeral=True)

        price = item["price"]
        role = interaction.guild.get_role(role_id)
        
        if not role:
            return await interaction.response.send_message("❌ Ошибка: Роль не найдена на сервере.", ephemeral=True)

        if role in interaction.user.roles:
            return await interaction.response.send_message("❌ У вас уже есть эта роль!", ephemeral=True)

        async with self.bot.db.execute("SELECT activity_points FROM users WHERE id = ?", (interaction.user.id,)) as cursor:
            row = await cursor.fetchone()
        
        balance = row[0] if row and row[0] else 0

        if balance < price:
            return await interaction.response.send_message(f"❌ Недостаточно Очков Активности! Нужно: `{price}` АП, у вас: `{balance}` АП.", ephemeral=True)

        try:
            await interaction.user.add_roles(role, reason="Покупка в магазине ролей")
        except discord.Forbidden:
            return await interaction.response.send_message("❌ У меня нет прав выдать эту роль. Моя роль должна быть ВЫШЕ покупаемой в настройках сервера!", ephemeral=True)

        await self.bot.db.execute("UPDATE users SET activity_points = activity_points - ? WHERE id = ?", (price, interaction.user.id))
        await self.bot.db.commit()

        await interaction.response.send_message(f"🎉 Вы успешно купили роль {role.mention} за `{price}` АП!", ephemeral=True)


class ShopView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(timeout=None)
        self.add_item(ShopSelect(bot, guild))
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

    @app_commands.command(name="give_activity", description="Наградить пользователя Очками Активности")
    @app_commands.describe(member="Кого наградить?", amount="Сколько очков дать?")
    @app_commands.checks.has_permissions(administrator=True)
    async def give_activity(self, interaction: discord.Interaction, member: discord.Member, amount: int) -> None:
        if amount <= 0:
            await interaction.response.send_message("❌ Количество очков должно быть больше нуля!", ephemeral=True)
            return

        query = """
            INSERT INTO users (id, balance, bank, activity_points, total_activity_points) 
            VALUES (?, 0, 0, ?, ?) 
            ON CONFLICT(id) DO UPDATE SET 
            activity_points = activity_points + ?,
            total_activity_points = total_activity_points + ?
        """
        await self.bot.db.execute(query, (member.id, amount, amount, amount, amount))
        await self.bot.db.commit()

        await interaction.response.send_message(f"🏆 Администратор наградил {member.mention} Очками Активности в размере: `{amount}`")
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))