import discord
from discord.ext import commands
from discord import app_commands

SHOP_ITEMS = [
    {
        "value": 1477601614171738193, # Обязательно замени на ID реальной роли на твоем сервере!
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
        
        if not item: return await interaction.response.send_message("❌ Ошибка: Товар не найден.", ephemeral=True)

        price = item["price"]
        role = interaction.guild.get_role(role_id)
        
        if not role: return await interaction.response.send_message("❌ Ошибка: Роль не найдена на сервере.", ephemeral=True)
        if role in interaction.user.roles: return await interaction.response.send_message("❌ У вас уже есть эта роль!", ephemeral=True)

        async with self.bot.db.execute("SELECT activity_points FROM users WHERE id = ?", (interaction.user.id,)) as cursor:
            row = await cursor.fetchone()
        
        # Если профиля нет, row будет None. Считаем, что баланс 0.
        balance = row[0] if row else 0

        if balance < price:
            return await interaction.response.send_message(f"❌ Недостаточно Очков Активности! Нужно: `{price}` АП, у вас: `{balance}` АП.", ephemeral=True)

        try:
            await interaction.user.add_roles(role, reason="Покупка в магазине ролей")
        except discord.Forbidden:
            return await interaction.response.send_message("❌ У меня нет прав выдать эту роль. Моя роль должна быть ВЫШЕ покупаемой!", ephemeral=True)

        await self.bot.db.execute("UPDATE users SET activity_points = activity_points - ? WHERE id = ?", (price, interaction.user.id))
        await self.bot.db.commit()

        await interaction.response.send_message(f"🎉 Вы успешно купили роль {role.mention} за `{price}` АП!", ephemeral=True)


class ShopView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(timeout=None)
        self.add_item(ShopSelect(bot, guild))


class Activity(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="leaderboard", description="🏆 Посмотреть доску почета (Топ по Уровню и Активности)")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            description="## 🏆 Доска почета сервера\n==========\n", 
            color=discord.Color.gold()
        )

        async with self.bot.db.execute("SELECT id, level FROM users WHERE level IS NOT NULL ORDER BY level DESC LIMIT 5") as cursor:
            level_rows = await cursor.fetchall()

        level_text = ""
        for index, row in enumerate(level_rows, start=1):
            medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else "🏅"
            level_text += f"{medal} <@{row[0]}> — **{row[1]}** уровень\n"

        if not level_text:
            level_text = "Пока никто не повысил уровень...\n"

        level_text += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
        embed.add_field(name="🔥 Высшие чины (Топ по уровню)", value=level_text, inline=False)

        async with self.bot.db.execute("SELECT id, activity_points, total_activity_points FROM users WHERE activity_points > 0 ORDER BY activity_points DESC LIMIT 5") as cursor:
            ap_rows = await cursor.fetchall()

        ap_text = ""
        for index, row in enumerate(ap_rows, start=1):
            medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else "🏅"
            ap_text += f"{medal} <@{row[0]}> — Текущие: `{row[1]}` (Всего: `{row[2]}`)\n"

        if not ap_text:
            ap_text = "Пока никто не проявил активность...\n"

        ap_text += "\n=========="
        
        embed.add_field(name="✨ Топ активных", value=ap_text, inline=False)
        embed.set_footer(text="Будьте активней и прокачивайте уровень, чтобы попасть сюда!")

        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="shop", description="🛒 Открыть магазин ролей за Очки Активности")
    async def shop(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            description="# 🛒 Магазин Ролей\nЗдесь вы можете обменять Очки Активности (АП) на эксклюзивные роли.\n==========\n",
            color=discord.Color.green()
        )
        for item in SHOP_ITEMS:
            role = interaction.guild.get_role(int(item["value"]))
            role_name = role.name if role else "Неизвестная роль"
            embed.add_field(name=f"{item['emoji']} {role_name}", value=f"Цена: `{item['price']}` АП\n*{item['description']}*", inline=False)
            
        embed.set_footer(text="Выберите роль в меню ниже, чтобы совершить покупку!")
        await interaction.response.send_message(embed=embed, view=ShopView(self.bot, interaction.guild))


    # ---------------------------------------------- Административные команды ----------------------------------------------
    
    @app_commands.command(name="change_balance", description="🛡️ [АДМИН] Изменить баланс душ пользователя")
    @app_commands.checks.has_permissions(administrator=True) 
    @app_commands.describe(action="Что сделать с балансом?", member="Выберите пользователя", amount="Укажите сумму")
    @app_commands.choices(action=[
        app_commands.Choice(name="✏️ Установить (Set)", value="set"),
        app_commands.Choice(name="➕ Добавить (Add)", value="add"),
        app_commands.Choice(name="➖ Отнять (Remove)", value="remove")
    ])
    async def change_balance(self, interaction: discord.Interaction, action: app_commands.Choice[str], member: discord.Member, amount: int) -> None:
        async with self.bot.db.execute("SELECT balance FROM users WHERE id = ?", (member.id,)) as cursor:
            row = await cursor.fetchone()
        
        # Защита от создания пустых профилей
        if not row:
            return await interaction.response.send_message(f"❌ У {member.mention} еще нет профиля! Пусть сначала напишет `/game`.", ephemeral=True)
            
        current_balance = row[0]
        
        if action.value == "set":
            new_balance = amount
            action_text = "установлен на"
        elif action.value == "add":
            new_balance = current_balance + amount
            action_text = "пополнен на"
        elif action.value == "remove":
            new_balance = current_balance - amount
            action_text = "уменьшен на"
            if new_balance < 0: new_balance = 0 
                
        await self.bot.db.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, member.id))
        await self.bot.db.commit()

        await interaction.response.send_message(f"💰 Баланс **{member.display_name}** {action_text} `{amount}` душ. \n💰 Текущий счет: `{new_balance}`", ephemeral=True)


    @change_balance.error
    async def change_balance_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Эта команда доступна только администраторам!", ephemeral=True)
        else:
            print(f"[ОШИБКА В ИЗМЕНЕНИИ БАЛАНСА]: {error}") 
            await interaction.response.send_message(f"❌ Системная ошибка: `{error}`", ephemeral=True)


    @app_commands.command(name="give_activity", description="🛡️ [АДМИН] Наградить пользователя Очками Активности")
    @app_commands.describe(member="Кого наградить?", amount="Сколько очков дать?")
    @app_commands.checks.has_permissions(administrator=True)
    async def give_activity(self, interaction: discord.Interaction, member: discord.Member, amount: int) -> None:
        if amount <= 0: return await interaction.response.send_message("❌ Количество очков должно быть больше нуля!", ephemeral=True)

        async with self.bot.db.execute("SELECT activity_points FROM users WHERE id = ?", (member.id,)) as cursor:
            row = await cursor.fetchone()
            
        if not row:
            return await interaction.response.send_message(f"❌ У {member.mention} еще нет профиля! Пусть сначала напишет `/game`.", ephemeral=True)

        query = "UPDATE users SET activity_points = activity_points + ?, total_activity_points = total_activity_points + ? WHERE id = ?"
        await self.bot.db.execute(query, (amount, amount, member.id))
        await self.bot.db.commit()

        await interaction.response.send_message(f"🏆 Администратор наградил {member.mention} Очками Активности в размере: `{amount}` АП!")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Activity(bot))