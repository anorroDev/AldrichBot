import discord
from discord.ext import commands
from discord import app_commands

SHOP_CATEGORIES = {
    "cosmetic": {
        "title": "🎨 Косметика",
        "description": "Постоянные косметические награды за АП.",
        "color": discord.Color.fuchsia(),
        "items": [
            {
                "id": "cosmetic_role_1",
                "name": "Эмиссар Пепла",
                "emoji": "🎖️",
                "price": 350,
                "description": "Косметическая роль в профиле сервера.",
                "kind": "role",
                "role_id": 1477601614171738193,
                "available": False,
            },
            {
                "id": "cosmetic_role_2",
                "name": "Хранитель Ночи",
                "emoji": "🌙",
                "price": 900,
                "description": "Редкая постоянная роль для активных участников.",
                "kind": "role",
                "role_id": 1477601614171738193,
                "available": False,
            },
        ],
    },
    "game": {
        "title": "🎮 Товары Для Игры",
        "description": "Расходуемые и полезные предметы для RPG-части.",
        "color": discord.Color.orange(),
        "items": [
            {
                "id": "game_flask",
                "name": "Фляга Бодрости",
                "emoji": "🧪",
                "price": 100,
                "description": "Добавляет 1 Флягу Бодрости в инвентарь.",
                "kind": "game_item",
                "item_name": "flask",
                "amount": 1,
                "available": False,
            },
            {
                "id": "game_ring",
                "name": "Кольцо Жертвенности",
                "emoji": "💍",
                "price": 300,
                "description": "Добавляет 1 Кольцо Жертвенности в инвентарь.",
                "kind": "game_item",
                "item_name": "ring",
                "amount": 1,
                "available": False,
            },
        ],
    },
    "special": {
        "title": "✨ Особые",
        "description": "Экспериментальные фичи и будущие интересные товары.",
        "color": discord.Color.blurple(),
        "items": [
            {
                "id": "special_profile_title",
                "name": "Персональный Титул",
                "emoji": "🪪",
                "price": 1500,
                "description": "Скоро: уникальный титул для карточки профиля.",
                "kind": "preview",
                "available": False,
            },
            {
                "id": "soon",
                "name": "Скоро",
                "emoji": "🚧",
                "price": 750,
                "description": "Скоро:.",
                "kind": "preview",
                "available": False,
            },
        ],
    },
}


class ShopCategorySelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, guild: discord.Guild, category_key: str):
        self.bot = bot
        self.guild = guild
        self.category_key = category_key

        category = SHOP_CATEGORIES[category_key]
        options = []
        for item in category["items"]:
            label = item["name"][:100]
            status = "Скоро" if not item.get("available", True) else f"{item['price']} АП"
            options.append(
                discord.SelectOption(
                    label=label,
                    description=f"Цена: {status}"[:100],
                    value=item["id"],
                    emoji=item.get("emoji", "🛒"),
                )
            )

        placeholder = f"Выберите товар: {category['title']}"
        super().__init__(placeholder=placeholder[:150], min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not self.view or interaction.user.id != self.view.owner_id:
            return await interaction.response.send_message("❌ Это не ваш магазин. Откройте /shop для себя.", ephemeral=True)

        category = SHOP_CATEGORIES[self.category_key]
        item = next((x for x in category["items"] if x["id"] == self.values[0]), None)

        if not item:
            return await interaction.response.send_message("❌ Ошибка: товар не найден.", ephemeral=True)

        if not item.get("available", True):
            return await interaction.response.send_message(
                f"🚧 Товар **{item['name']}** пока недоступен.",
                ephemeral=True,
            )

        async with self.bot.db.execute("SELECT activity_points FROM users WHERE id = ?", (interaction.user.id,)) as cursor:
            row = await cursor.fetchone()

        balance = row[0] if row else 0
        price = item["price"]

        if balance < price:
            return await interaction.response.send_message(
                f"❌ Недостаточно АП! Нужно: `{price}`, у вас: `{balance}`.",
                ephemeral=True,
            )

        if item["kind"] == "role":
            role = self.guild.get_role(int(item["role_id"]))
            if not role:
                return await interaction.response.send_message("❌ Роль не найдена на сервере.", ephemeral=True)
            if role in interaction.user.roles:
                return await interaction.response.send_message("❌ У вас уже есть эта роль.", ephemeral=True)

            try:
                await interaction.user.add_roles(role, reason="Покупка в магазине АП")
            except discord.Forbidden:
                return await interaction.response.send_message(
                    "❌ У меня нет прав выдать эту роль. Проверьте порядок ролей.",
                    ephemeral=True,
                )

            await self.bot.db.execute("UPDATE users SET activity_points = activity_points - ? WHERE id = ?", (price, interaction.user.id))
            await self.bot.db.commit()
            return await interaction.response.send_message(
                f"✅ Покупка успешна! Вы получили роль {role.mention} за `{price}` АП.",
                ephemeral=True,
            )

        if item["kind"] == "game_item":
            amount = int(item.get("amount", 1))
            item_name = item["item_name"]

            await self.bot.db.execute(
                "INSERT INTO inventory (user_id, item_name, amount, equipped) VALUES (?, ?, ?, 0) "
                "ON CONFLICT(user_id, item_name) DO UPDATE SET amount = amount + ?",
                (interaction.user.id, item_name, amount, amount),
            )
            await self.bot.db.execute("UPDATE users SET activity_points = activity_points - ? WHERE id = ?", (price, interaction.user.id))
            await self.bot.db.commit()
            return await interaction.response.send_message(
                f"✅ Покупка успешна! В инвентарь добавлено: **{item['name']} x{amount}** за `{price}` АП.",
                ephemeral=True,
            )

        return await interaction.response.send_message("❌ Этот тип товара пока не поддерживается.", ephemeral=True)


class ShopCategoryView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild: discord.Guild, owner_id: int, category_key: str = "cosmetic"):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.owner_id = owner_id
        self.category_key = category_key
        self._rebuild_components()
        self._apply_button_styles()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Это не ваш магазин. Откройте /shop для себя.", ephemeral=True)
            return False
        return True

    def _rebuild_components(self) -> None:

        for child in list(self.children):
            if isinstance(child, ShopCategorySelect):
                self.remove_item(child)
        self.add_item(ShopCategorySelect(self.bot, self.guild, self.category_key))

    def _apply_button_styles(self) -> None:
        mapping = {
            "cosmetic": self.btn_cosmetic,
            "game": self.btn_game,
            "special": self.btn_special,
        }
        for key, button in mapping.items():
            button.style = discord.ButtonStyle.primary if key == self.category_key else discord.ButtonStyle.secondary

    async def _get_balance(self, user_id: int) -> int:
        async with self.bot.db.execute("SELECT activity_points FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        return row[0] if row and row[0] else 0

    async def _get_embed(self) -> discord.Embed:
        category = SHOP_CATEGORIES[self.category_key]
        embed = discord.Embed(
            title=f"🛒 Магазин АП • {category['title']}",
            description=f"{category['description']}\n==========",
            color=category["color"],
        )

        for item in category["items"]:
            state = "🚧 Скоро" if not item.get("available", True) else f"{item['price']} АП"
            embed.add_field(
                name=f"{item.get('emoji', '🛒')} {item['name']}",
                value=f"Цена: `{state}`\n*{item['description']}*",
                inline=False,
            )

        balance = await self._get_balance(self.owner_id)
        embed.set_footer(text=f"Ваш баланс: {balance} АП • Выберите категорию кнопками ниже.")
        return embed

    async def _switch_category(self, interaction: discord.Interaction, category_key: str) -> None:
        if category_key == self.category_key:
            return await interaction.response.defer()

        self.category_key = category_key
        self._rebuild_components()
        self._apply_button_styles()
        await interaction.response.edit_message(embed=await self._get_embed(), view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="🎨 Косметика", style=discord.ButtonStyle.secondary, row=1)
    async def btn_cosmetic(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_category(interaction, "cosmetic")

    @discord.ui.button(label="🎮 Игровые", style=discord.ButtonStyle.secondary, row=1)
    async def btn_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_category(interaction, "game")

    @discord.ui.button(label="✨ Особые", style=discord.ButtonStyle.secondary, row=1)
    async def btn_special(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_category(interaction, "special")


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


    @app_commands.command(name="shop", description="🛒 Открыть магазин за Очки Активности")
    async def shop(self, interaction: discord.Interaction) -> None:
        view = ShopCategoryView(self.bot, interaction.guild, owner_id=interaction.user.id, category_key="cosmetic")
        await interaction.response.send_message(embed=await view._get_embed(), view=view)


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