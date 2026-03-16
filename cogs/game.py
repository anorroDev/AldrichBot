import discord
from discord.ext import commands
from discord import app_commands
import random
import math
import asyncio
import aiosqlite
import time

def get_level_cost(target_level: int) -> int:
    if target_level <= 1: return 0
    if target_level == 2: return 673
    if target_level <= 12:
        cost = 673
        for _ in range(3, target_level + 1): cost = int(cost * 1.025)
        return cost
    cost = 0.02 * (target_level**3) + 3.06 * (target_level**2) + 105.6 * target_level - 895
    return math.floor(cost)

LOCATIONS = {
    "graveyard": {"name": "🪦 Кладбище", "base_death": 40, "min_souls": 100, "max_souls": 200, "req_hunts": 0},
    "forest": {"name": "🌲 Проклятый лес", "base_death": 50, "min_souls": 200, "max_souls": 400, "req_hunts": 10},
    "catacombs": {"name": "💀 Катакомбы", "base_death": 55, "min_souls": 500, "max_souls": 750, "req_hunts": 25},
    "castle": {"name": "🏰 Заброшенный замок", "base_death": 65, "min_souls": 800, "max_souls": 1000, "req_hunts": 45},
    "peak": {"name": "🌋 Пик Дракона", "base_death": 75, "min_souls": 1200, "max_souls": 2000, "req_hunts": 70},
    "abyss": {"name": "🌌 Бездна", "base_death": 95, "min_souls": 2500, "max_souls": 4000, "req_hunts": 100}
}

ITEMS = {
    "ring":       {"name": "💍 Кольцо Жертвенности",   "price": 1000, "type": "equippable", "desc": "Одноразовое. При смертельном ударе вспыхивает и разбивается, сохраняя ваши души."},
    "greed_ring": {"name": "💛 Кольцо Жадности",        "price": 1500, "type": "equippable", "desc": "Пассивное. Каждая надетая копия даёт +20% к добытым душам на охоте."},
    "swift_ring": {"name": "🔵 Кольцо Стремительности", "price": 2000, "type": "equippable", "desc": "Пассивное. Каждая надетая копия снижает шанс смерти на 5%."},
    "flask":      {"name": "🧪 Фляга Бодрости",         "price": 500,  "type": "consumable", "desc": "Восстанавливает вашу бодрость (энергию) до максимума (5/5)."},
    "war_scroll": {"name": "📜 Свиток Ярости",          "price": 800,  "type": "consumable", "desc": "Примените перед охотой. Следующая успешная охота принесёт двойные души."},
}

async def get_profile_embed(bot, user: discord.Member):
    async with bot.db.execute(
        "SELECT char_name, level, balance, current_location, stat_points, strength, vitality, luck, energy, successful_hunts "
        "FROM users WHERE id = ?", (user.id,)
    ) as cursor:
        row = await cursor.fetchone()

    if not row or not row[0]: return None

    char_name, level, souls, loc_key, stat_pts, strg, vit, luck, energy, hunts = row
    loc_name = LOCATIONS[loc_key]["name"] if loc_key in LOCATIONS else "🏕️ Безопасная зона"

    async with bot.db.execute("SELECT COUNT(*) FROM user_achievements WHERE user_id = ?", (user.id,)) as cursor:
        ach_count = (await cursor.fetchone())[0]

    async with bot.db.execute("SELECT item_name, equipped FROM inventory WHERE user_id = ? AND equipped > 0", (user.id,)) as cursor:
        equipped_rows = await cursor.fetchall()
    equipped_strs = [f"{ITEMS[r[0]]['name']} x{r[1]}" for r in equipped_rows if r[0] in ITEMS]
    equipped_text = "\n".join(equipped_strs) if equipped_strs else "Нет"

    embed = discord.Embed(description=f"# 📜 Профиль: {char_name}\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n", color=discord.Color.blurple())
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="👤 Владелец", value=user.mention, inline=False)
    embed.add_field(name="🔸 Уровень", value=f"**{level}**", inline=True)
    embed.add_field(name="🔸 Души", value=f"**{souls}** 👻", inline=True)
    embed.add_field(name="⚡ Энергия", value=f"**{energy}/5**", inline=True)
    embed.add_field(name="📍 Локация", value=f"`{loc_name}`", inline=True)
    embed.add_field(name="🏆 Успешных охот", value=f"**{hunts}**", inline=True)
    embed.add_field(name="🎯 Достижений", value=f"**{ach_count}**", inline=True)
    embed.add_field(name="🌟 Очки характеристик", value=f"**{stat_pts}**", inline=False)
    embed.add_field(name="💪 Сила", value=f"**{strg}**", inline=True)
    embed.add_field(name="❤️ Живучесть", value=f"**{vit}**", inline=True)
    embed.add_field(name="🍀 Удача", value=f"**{luck}**", inline=True)
    embed.add_field(name="💍 Экипировка", value=equipped_text, inline=False)
    return embed

class HuntAgainUI(discord.ui.View):
    def __init__(self, cog, user, location_key, farm_view):
        super().__init__(timeout=None)
        self.cog = cog
        self.user = user
        self.location_key = location_key
        self.farm_view = farm_view

    @discord.ui.button(label="🔄 Снова в бой", style=discord.ButtonStyle.primary, custom_id="hunt_again")
    async def btn_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваша игра!", ephemeral=True)
        await self.farm_view.process_farm(interaction, self.location_key)

    @discord.ui.button(label="🔙 Вернуться в лагерь", style=discord.ButtonStyle.secondary, custom_id="hunt_back")
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваша игра!", ephemeral=True)
        embed = await self.farm_view.main_view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.farm_view.main_view)

class MerchantUI(discord.ui.View):
    def __init__(self, cog, user, location_key, farm_view):
        super().__init__(timeout=None)
        self.cog = cog
        self.user = user
        self.bot = cog.bot
        self.location_key = location_key
        self.farm_view = farm_view

    async def buy_item(self, interaction, item_key):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Торговец смотрит не на вас!", ephemeral=True)
        item = ITEMS[item_key]

        async with self.bot.db.execute("SELECT balance FROM users WHERE id = ?", (self.user.id,)) as cursor:
            row = await cursor.fetchone()
        balance = row[0] if row else 0

        if balance < item["price"]:
            return await interaction.response.send_message(f"❌ У вас не хватает душ! Нужно {item['price']} 👻.", ephemeral=True)

        await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (item["price"], self.user.id))
        await self.bot.db.execute(
            "INSERT INTO inventory (user_id, item_name, amount, equipped) VALUES (?, ?, 1, 0) "
            "ON CONFLICT(user_id, item_name) DO UPDATE SET amount = amount + 1",
            (self.user.id, item_key)
        )
        await self.bot.db.commit()
        await interaction.response.send_message(f"🛍️ Куплено: **{item['name']}** за {item['price']} 👻!", ephemeral=True)

    @discord.ui.button(label="💍 Жертвенное (1000)", style=discord.ButtonStyle.secondary, row=0)
    async def btn_ring(self, i: discord.Interaction, b: discord.ui.Button): await self.buy_item(i, "ring")

    @discord.ui.button(label="💛 Жадное (1500)", style=discord.ButtonStyle.secondary, row=0)
    async def btn_greed(self, i: discord.Interaction, b: discord.ui.Button): await self.buy_item(i, "greed_ring")

    @discord.ui.button(label="🔵 Стремительное (2000)", style=discord.ButtonStyle.secondary, row=0)
    async def btn_swift(self, i: discord.Interaction, b: discord.ui.Button): await self.buy_item(i, "swift_ring")

    @discord.ui.button(label="🧪 Фляга (500)", style=discord.ButtonStyle.secondary, row=1)
    async def btn_flask(self, i: discord.Interaction, b: discord.ui.Button): await self.buy_item(i, "flask")

    @discord.ui.button(label="📜 Свиток Ярости (800)", style=discord.ButtonStyle.secondary, row=1)
    async def btn_scroll(self, i: discord.Interaction, b: discord.ui.Button): await self.buy_item(i, "war_scroll")

    @discord.ui.button(label="⚔️ Снова в бой", style=discord.ButtonStyle.primary, row=2)
    async def btn_hunt(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваша игра!", ephemeral=True)
        await self.farm_view.process_farm(interaction, self.location_key)

    @discord.ui.button(label="🔙 Вернуться в лагерь", style=discord.ButtonStyle.secondary, row=2)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваша игра!", ephemeral=True)
        embed = await self.farm_view.main_view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.farm_view.main_view)

class InventoryUI(discord.ui.View):
    def __init__(self, bot, user, main_view=None):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user
        self.main_view = main_view

    async def get_inventory_data(self):
        async with self.bot.db.execute("SELECT item_name, amount, equipped FROM inventory WHERE user_id = ? AND amount > 0", (self.user.id,)) as cursor:
            return await cursor.fetchall()

    async def generate_embed(self):
        items = await self.get_inventory_data()
        items_dict = {row[0]: {"amount": row[1], "equipped": row[2]} for row in items}
        total_equipped = sum(row[2] for row in items if row[2] > 0)

        embed = discord.Embed(title="🎒 Инвентарь и Экипировка", color=discord.Color.dark_gold())
        embed.set_thumbnail(url=self.user.display_avatar.url)

        desc = f"**Занято слотов экипировки: {total_equipped}/4**\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
        if not items:
            desc += "Ваш рюкзак абсолютно пуст."
        else:
            for item_id, data in items_dict.items():
                if item_id in ITEMS:
                    item_data = ITEMS[item_id]
                    amount, equipped = data["amount"], data["equipped"]
                    in_bag = amount - equipped
                    if equipped > 0:
                        eq_text = f" *({equipped} надето, {in_bag} в рюкзаке)*"
                    else:
                        eq_text = f" *({amount} в рюкзаке)*"
                    desc += f"**{item_data['name']}**{eq_text}\n*{item_data['desc']}*\n\n"
        embed.description = desc
        return embed

    async def _equip_ring(self, interaction: discord.Interaction, item_key: str):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Это не ваш инвентарь!", ephemeral=True)
        items = await self.get_inventory_data()
        items_dict = {row[0]: {"amount": row[1], "equipped": row[2]} for row in items}
        total_equipped = sum(row[2] for row in items if row[2] > 0)

        if total_equipped >= 4:
            return await interaction.response.send_message("❌ Заняты все 4 слота экипировки!", ephemeral=True)
        ring_data = items_dict.get(item_key)
        if not ring_data or ring_data["amount"] <= ring_data["equipped"]:
            return await interaction.response.send_message(f"❌ Нет свободных **{ITEMS[item_key]['name']}** в рюкзаке!", ephemeral=True)

        await self.bot.db.execute("UPDATE inventory SET equipped = equipped + 1 WHERE user_id = ? AND item_name = ?", (self.user.id, item_key))
        await self.bot.db.commit()
        embed = await self.generate_embed()
        await interaction.response.edit_message(content=f"✅ Надето: **{ITEMS[item_key]['name']}**.", embed=embed, view=self)

    async def _unequip_ring(self, interaction: discord.Interaction, item_key: str):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Это не ваш инвентарь!", ephemeral=True)
        items = await self.get_inventory_data()
        items_dict = {row[0]: {"amount": row[1], "equipped": row[2]} for row in items}
        ring_data = items_dict.get(item_key)
        if not ring_data or ring_data["equipped"] <= 0:
            return await interaction.response.send_message(f"❌ На вас нет **{ITEMS[item_key]['name']}**!", ephemeral=True)

        await self.bot.db.execute("UPDATE inventory SET equipped = equipped - 1 WHERE user_id = ? AND item_name = ?", (self.user.id, item_key))
        await self.bot.db.commit()
        embed = await self.generate_embed()
        await interaction.response.edit_message(content=f"✅ Снято: **{ITEMS[item_key]['name']}**.", embed=embed, view=self)

    @discord.ui.button(label="💍 Надеть Жертвенное", style=discord.ButtonStyle.secondary, row=0)
    async def btn_equip_ring(self, i: discord.Interaction, b: discord.ui.Button): await self._equip_ring(i, "ring")

    @discord.ui.button(label="💍 Снять Жертвенное", style=discord.ButtonStyle.secondary, row=0)
    async def btn_unequip_ring(self, i: discord.Interaction, b: discord.ui.Button): await self._unequip_ring(i, "ring")

    @discord.ui.button(label="💛 Надеть Жадное", style=discord.ButtonStyle.secondary, row=1)
    async def btn_equip_greed(self, i: discord.Interaction, b: discord.ui.Button): await self._equip_ring(i, "greed_ring")

    @discord.ui.button(label="💛 Снять Жадное", style=discord.ButtonStyle.secondary, row=1)
    async def btn_unequip_greed(self, i: discord.Interaction, b: discord.ui.Button): await self._unequip_ring(i, "greed_ring")

    @discord.ui.button(label="🔵 Надеть Стремительное", style=discord.ButtonStyle.secondary, row=2)
    async def btn_equip_swift(self, i: discord.Interaction, b: discord.ui.Button): await self._equip_ring(i, "swift_ring")

    @discord.ui.button(label="🔵 Снять Стремительное", style=discord.ButtonStyle.secondary, row=2)
    async def btn_unequip_swift(self, i: discord.Interaction, b: discord.ui.Button): await self._unequip_ring(i, "swift_ring")

    @discord.ui.button(label="🧪 Выпить Флягу", style=discord.ButtonStyle.success, row=3)
    async def btn_flask(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Это не ваш инвентарь!", ephemeral=True)
        items = await self.get_inventory_data()
        flask_data = next((row for row in items if row[0] == 'flask'), None)
        if not flask_data or flask_data[1] <= 0:
            return await interaction.response.send_message("❌ У вас нет Фляги Бодрости!", ephemeral=True)
        async with self.bot.db.execute("SELECT energy FROM users WHERE id = ?", (self.user.id,)) as cursor:
            energy_row = await cursor.fetchone()
        if energy_row and energy_row[0] >= 5:
            return await interaction.response.send_message("❌ Бодрость уже максимальна (5/5)!", ephemeral=True)

        await self.bot.db.execute("UPDATE inventory SET amount = amount - 1 WHERE user_id = ? AND item_name = 'flask'", (self.user.id,))
        await self.bot.db.execute("UPDATE users SET energy = 5, last_energy_update = 0 WHERE id = ?", (self.user.id,))
        await self.bot.db.commit()
        embed = await self.generate_embed()
        await interaction.response.edit_message(content="✅ Выпита Фляга! Бодрость восстановлена до 5/5.", embed=embed, view=self)

    @discord.ui.button(label="📜 Применить Свиток", style=discord.ButtonStyle.success, row=3)
    async def btn_scroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Это не ваш инвентарь!", ephemeral=True)
        items = await self.get_inventory_data()
        scroll_data = next((row for row in items if row[0] == 'war_scroll'), None)
        if not scroll_data or scroll_data[1] <= 0:
            return await interaction.response.send_message("❌ У вас нет Свитка Ярости!", ephemeral=True)
        async with self.bot.db.execute("SELECT double_next_hunt FROM users WHERE id = ?", (self.user.id,)) as cursor:
            dnh_row = await cursor.fetchone()
        if dnh_row and dnh_row[0]:
            return await interaction.response.send_message("⚠️ Свиток Ярости уже активен! Идите на охоту.", ephemeral=True)

        await self.bot.db.execute("UPDATE inventory SET amount = amount - 1 WHERE user_id = ? AND item_name = 'war_scroll'", (self.user.id,))
        await self.bot.db.execute("UPDATE users SET double_next_hunt = 1 WHERE id = ?", (self.user.id,))
        await self.bot.db.commit()
        embed = await self.generate_embed()
        await interaction.response.edit_message(content="🔥 Свиток Ярости активирован! Следующая успешная охота принесёт двойные души.", embed=embed, view=self)

    @discord.ui.button(label="🔙 Вернуться", style=discord.ButtonStyle.primary, row=4)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Это не ваш персонаж!", ephemeral=True)
        if self.main_view:
            embed = await self.main_view.get_main_embed()
            await interaction.response.edit_message(content="", embed=embed, view=self.main_view)
        else:
            await interaction.response.edit_message(content="🎒 Инвентарь закрыт.", embed=None, view=None)

class ProfileUI(discord.ui.View):
    def __init__(self, bot, user, main_view):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user
        self.main_view = main_view

    @discord.ui.button(label="🔙 Вернуться в лагерь", style=discord.ButtonStyle.primary, custom_id="profile_back")
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш персонаж!", ephemeral=True)
        embed = await self.main_view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.main_view)

class StatsUI(discord.ui.View):
    def __init__(self, bot, user, main_view):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user
        self.main_view = main_view

    async def generate_embed(self):
        async with self.bot.db.execute("SELECT stat_points, strength, vitality, luck FROM users WHERE id = ?", (self.user.id,)) as cursor:
            row = await cursor.fetchone()
        sp, strg, vit, lck = row if row else (0, 1, 1, 1)

        embed = discord.Embed(
            title="⚖️ Распределение характеристик",
            description=f"Свободных очков: 🌟 **{sp}**\n\n💪 **Сила:** {strg} *(+{strg}% к добытым душам)*\n❤️ **Живучесть:** {vit} *(-{vit * 0.5}% к шансу смерти)*\n🍀 **Удача:** {lck} *(+{lck * 10} к макс. добыче душ)*\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
            color=discord.Color.blue()
        )
        return embed, sp

    async def upgrade_stat(self, interaction, stat_name):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш персонаж!", ephemeral=True)
        async with self.bot.db.execute("SELECT stat_points FROM users WHERE id = ?", (self.user.id,)) as cursor:
            sp = (await cursor.fetchone())[0]
        if sp <= 0: return await interaction.response.send_message("❌ У вас нет свободных очков!", ephemeral=True)

        await self.bot.db.execute(f"UPDATE users SET stat_points = stat_points - 1, {stat_name} = {stat_name} + 1 WHERE id = ?", (self.user.id,))
        await self.bot.db.commit()
        embed, _ = await self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="+1 Сила", style=discord.ButtonStyle.secondary, emoji="💪", row=0)
    async def btn_str(self, interaction: discord.Interaction, button: discord.ui.Button): await self.upgrade_stat(interaction, "strength")
    @discord.ui.button(label="+1 Живучесть", style=discord.ButtonStyle.secondary, emoji="❤️", row=0)
    async def btn_vit(self, interaction: discord.Interaction, button: discord.ui.Button): await self.upgrade_stat(interaction, "vitality")
    @discord.ui.button(label="+1 Удача", style=discord.ButtonStyle.secondary, emoji="🍀", row=0)
    async def btn_luck(self, interaction: discord.Interaction, button: discord.ui.Button): await self.upgrade_stat(interaction, "luck")

    @discord.ui.button(label="🔙 Вернуться", style=discord.ButtonStyle.primary, row=1)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш персонаж!", ephemeral=True)
        embed = await self.main_view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.main_view)

class LevelUpUI(discord.ui.View):
    def __init__(self, bot, user, main_view):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user
        self.main_view = main_view

    async def generate_levelup_embed(self):
        async with self.bot.db.execute("SELECT balance, level FROM users WHERE id = ?", (self.user.id,)) as cursor:
            row = await cursor.fetchone()
        balance, level = (row[0], row[1]) if row else (0, 1)
        
        if level >= 80: return discord.Embed(title="👑 Максимальный уровень", description="Вы достигли предела развития (80 уровень).", color=discord.Color.gold())
            
        cost = get_level_cost(level + 1)
        embed = discord.Embed(description=f"## 🔥 Отдых у костра\n\nЗдесь вы можете пожертвовать собранные души, чтобы стать сильнее.\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n", color=discord.Color.gold())
        embed.set_thumbnail(url=self.user.display_avatar.url)
        embed.add_field(name="🔸 Текущий уровень", value=f"**{level}**", inline=True)
        embed.add_field(name="🔸 Ваши души", value=f"**{balance}** 👻", inline=True)
        embed.add_field(name="🔸 Стоимость улучшения", value=f"**{cost}** 👻", inline=False)
        
        embed.set_footer(text=f"Вам не хватает {cost - balance} душ." if balance < cost else "У вас достаточно душ! Нажмите кнопку повышения уровня.")
        return embed

    @discord.ui.button(label="⬆️ Повысить уровень", style=discord.ButtonStyle.success, row=0, custom_id="lvlup_confirm")
    async def btn_confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш персонаж!", ephemeral=True)
        async with self.bot.db.execute("SELECT balance, level FROM users WHERE id = ?", (self.user.id,)) as cursor:
            row = await cursor.fetchone()
        balance, level = (row[0], row[1]) if row else (0, 1)
        
        if level >= 80: return await interaction.response.send_message("Вы уже достигли максимального уровня!", ephemeral=True)
        next_level = level + 1
        cost = get_level_cost(next_level)
        
        if balance < cost:
            new_embed = await self.generate_levelup_embed()
            new_embed.add_field(name="❌ НЕДОСТАТОЧНО ДУШ", value=f"Нужно еще **{cost - balance}** 👻.", inline=False)
            return await interaction.response.edit_message(embed=new_embed, view=self)
            
        await self.bot.db.execute("UPDATE users SET balance = balance - ?, level = ?, stat_points = stat_points + 1 WHERE id = ?", (cost, next_level, self.user.id))
        await self.bot.db.commit()
        
        new_embed = await self.generate_levelup_embed()
        new_embed.add_field(name="🎉 УРОВЕНЬ ПОВЫШЕН!", value=f"Достигнут **{next_level} уровень**!\nПолучено **1 очко характеристик**.", inline=False)
        await interaction.response.edit_message(embed=new_embed, view=self)

    @discord.ui.button(label="⚖️ Характеристики", style=discord.ButtonStyle.secondary, row=1, custom_id="lvlup_stats")
    async def btn_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш персонаж!", ephemeral=True)
        stats_view = StatsUI(self.bot, self.user, main_view=self.main_view)
        embed, _ = await stats_view.generate_embed()
        await interaction.response.edit_message(embed=embed, view=stats_view)

    @discord.ui.button(label="🔙 Вернуться в лагерь", style=discord.ButtonStyle.primary, row=1, custom_id="lvlup_back")
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш персонаж!", ephemeral=True)
        embed = await self.main_view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.main_view)

class FarmUI(discord.ui.View):
    def __init__(self, bot, user, main_view):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user
        self.main_view = main_view

    async def process_farm(self, interaction: discord.Interaction, location_key: str):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш персонаж!", ephemeral=True)

        loc_data = LOCATIONS[location_key]
        async with self.bot.db.execute(
            "SELECT balance, level, lost_souls, energy, last_energy_update, successful_hunts, strength, vitality, luck, double_next_hunt "
            "FROM users WHERE id = ?", (self.user.id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row: return
        balance, level, lost_souls, energy, last_update, hunts, strength, vitality, luck, double_next_hunt = row
        now = int(time.time())

        async with self.bot.db.execute("SELECT item_name, equipped FROM inventory WHERE user_id = ? AND equipped > 0", (self.user.id,)) as cursor:
            equipped_rings = {r[0]: r[1] for r in await cursor.fetchall()}
        greed_rings = equipped_rings.get('greed_ring', 0)
        swift_rings = equipped_rings.get('swift_ring', 0)

        if hunts < loc_data["req_hunts"]:
            return await interaction.response.send_message(f"🔒 Локация закрыта! Нужно {loc_data['req_hunts']} успешных побед.", ephemeral=True)

        if energy < 5:
            passed_time = now - last_update
            recovered = passed_time // 300 
            if recovered > 0:
                energy += recovered
                if energy >= 5: energy, last_update = 5, 0
                else: last_update += recovered * 300
                await self.bot.db.execute("UPDATE users SET energy = ?, last_energy_update = ? WHERE id = ?", (energy, last_update, self.user.id))
                await self.bot.db.commit()

        if energy < 1:
            time_left = 300 - ((now - last_update) % 300)
            mins, secs = divmod(time_left, 60)
            return await interaction.response.send_message(f"💤 Вы истощены! Очко бодрости через **{mins} мин. {secs} сек.**", ephemeral=True)

        energy -= 1
        if last_update == 0: last_update = now

        death_chance = max(5, loc_data["base_death"] - (level - 1) - (vitality * 0.5) - (swift_rings * 5))
        roll = random.uniform(0, 100)

        embed = discord.Embed(color=discord.Color.dark_theme())
        embed.set_thumbnail(url=self.user.display_avatar.url)

        async with self.bot.db.execute("SELECT amount, equipped FROM inventory WHERE user_id = ? AND item_name = 'ring'", (self.user.id,)) as cursor:
            ring_row = await cursor.fetchone()
        has_equipped_ring = ring_row and ring_row[1] > 0

        if roll <= death_chance:
            if has_equipped_ring:
                await self.bot.db.execute("UPDATE inventory SET amount = amount - 1, equipped = equipped - 1 WHERE user_id = ? AND item_name = 'ring'", (self.user.id,))
                await self.bot.db.execute("UPDATE users SET energy = ?, last_energy_update = ? WHERE id = ?", (energy, last_update, self.user.id))
                await self.bot.db.commit()
                
                embed.title = "💍 КОЛЬЦО РАСКОЛОЛОСЬ!"
                embed.description = f"## Локация: {loc_data['name']}\nСмертельный удар обрушился на вас, но надетое **Кольцо Жертвенности** вспыхнуло ярким светом и рассыпалось в прах. Души сохранены!\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n💰 Текущий баланс: **{balance}** 👻\nОсталось бодрости: ⚡ {energy}/5"
                embed.color = discord.Color.gold()
                await interaction.response.edit_message(embed=embed, view=HuntAgainUI(self.bot.get_cog('Game'), self.user, location_key, self))
            else:
                new_lost_souls = balance
                await self.bot.db.execute("UPDATE users SET balance = 0, lost_souls = ?, current_location = ?, energy = ?, last_energy_update = ? WHERE id = ?", (new_lost_souls, location_key, energy, last_update, self.user.id))
                await self.bot.db.commit()
                
                embed.title = "☠️ ВЫ ПОГИБЛИ!"
                embed.description = f"## Локация: {loc_data['name']}\nТьма поглотила вас.\nВы выронили `{new_lost_souls}` 👻 душ.\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n💰 Текущий баланс: **0** 👻\nОсталось бодрости: ⚡ {energy}/5"
                embed.color = discord.Color.red()
                if lost_souls > 0: embed.description += "\n⚠️ **Предыдущее кровавое пятно исчезло. Старые души утеряны!**"
                await interaction.response.edit_message(embed=embed, view=HuntAgainUI(self.bot.get_cog('Game'), self.user, location_key, self))
        else:
            max_farm = loc_data["max_souls"] + (luck * 10)
            base_reward = random.randint(loc_data["min_souls"], max_farm)
            strength_bonus = 1 + (strength * 0.01)
            greed_bonus = 1 + (greed_rings * 0.20)
            pure_reward = int(base_reward * strength_bonus * greed_bonus)

            bonus_text = ""
            if double_next_hunt:
                pure_reward *= 2
                bonus_text += "\n\n🔥 **Свиток Ярости:** добыча удвоена!"
            if greed_rings > 0:
                bonus_text += f"\n💛 Кольца Жадности (x{greed_rings}): +{greed_rings * 20}% душ"

            reward = pure_reward
            new_hunts = hunts + 1

            recovered_text = ""
            if lost_souls > 0:
                reward += lost_souls
                recovered_text = f"\n🩸 Вы коснулись пятна крови и вернули `{lost_souls}` 👻 душ!"

            new_balance = balance + reward
            await self.bot.db.execute(
                "UPDATE users SET balance = balance + ?, lost_souls = 0, current_location = ?, "
                "total_souls_farmed = total_souls_farmed + ?, energy = ?, last_energy_update = ?, "
                "successful_hunts = ?, double_next_hunt = 0 WHERE id = ?",
                (reward, location_key, pure_reward, energy, last_update, new_hunts, self.user.id)
            )
            await self.bot.db.commit()

            embed.title = "⚔️ Охота успешна!"
            embed.description = (
                f"## Локация: {loc_data['name']}\nВы выжили и принесли `{pure_reward}` 👻 душ."
                f"{recovered_text}{bonus_text}\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
                f"💰 Текущий баланс: **{new_balance}** 👻\n"
                f"🏆 Успешных побед: **{new_hunts}**\n"
                f"Осталось бодрости: ⚡ {energy}/5"
            )
            embed.color = discord.Color.green()
            footer_parts = [f"Шанс смерти: {round(death_chance, 1)}%"]
            if swift_rings > 0:
                footer_parts.append(f"🔵 Стремительность (x{swift_rings}): -{swift_rings * 5}%")
            embed.set_footer(text=" | ".join(footer_parts))

            if random.randint(1, 100) <= 5:
                embed.description += "\n\n🎒 **Странствующий торговец:** *«Эй, путник! Вижу, ты богат. Не хочешь взглянуть на мои товары?»*"
                await interaction.response.edit_message(embed=embed, view=MerchantUI(self.bot.get_cog('Game'), self.user, location_key, self))
            else:
                await interaction.response.edit_message(embed=embed, view=HuntAgainUI(self.bot.get_cog('Game'), self.user, location_key, self))

    @discord.ui.button(label="🪦 Кладбище", style=discord.ButtonStyle.secondary, custom_id="f_grave", row=0)
    async def b_grave(self, i: discord.Interaction, b: discord.ui.Button): await self.process_farm(i, "graveyard")
    @discord.ui.button(label="🌲 Лес", style=discord.ButtonStyle.secondary, custom_id="f_forest", row=0)
    async def b_forest(self, i: discord.Interaction, b: discord.ui.Button): await self.process_farm(i, "forest")
    @discord.ui.button(label="💀 Катакомбы", style=discord.ButtonStyle.secondary, custom_id="f_cata", row=0)
    async def b_cata(self, i: discord.Interaction, b: discord.ui.Button): await self.process_farm(i, "catacombs")

    @discord.ui.button(label="🏰 Замок", style=discord.ButtonStyle.danger, custom_id="f_castle", row=1)
    async def b_castle(self, i: discord.Interaction, b: discord.ui.Button): await self.process_farm(i, "castle")
    @discord.ui.button(label="🌋 Пик Дракона", style=discord.ButtonStyle.danger, custom_id="f_peak", row=1)
    async def b_peak(self, i: discord.Interaction, b: discord.ui.Button): await self.process_farm(i, "peak")
    @discord.ui.button(label="🌌 Бездна", style=discord.ButtonStyle.danger, custom_id="f_abyss", row=1)
    async def b_abyss(self, i: discord.Interaction, b: discord.ui.Button): await self.process_farm(i, "abyss")

    @discord.ui.button(label="🔙 Вернуться в лагерь", style=discord.ButtonStyle.primary, row=2)
    async def b_back(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id != self.user.id: return await i.response.send_message("Это не ваш персонаж!", ephemeral=True)
        embed = await self.main_view.get_main_embed()
        await i.response.edit_message(embed=embed, view=self.main_view)

class GameUI(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user

    async def get_main_embed(self):
        async with self.bot.db.execute("SELECT char_name, level, balance FROM users WHERE id = ?", (self.user.id,)) as cursor:
            row = await cursor.fetchone()
        name, level, souls = row
        
        embed = discord.Embed(description=f"# 🏕️ {name}\n\nВы находитесь в безопасной зоне. Отсюда можно отправиться в рейд или посидеть у костра.\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n", color=discord.Color.dark_theme())
        embed.set_thumbnail(url=self.user.display_avatar.url)
        embed.add_field(name="🔸 Текущий Уровень", value=f"**{level}**", inline=True)
        embed.add_field(name="🔸 Накоплено Душ", value=f"**{souls}** 👻", inline=True)
        embed.add_field(name="🔸 Локация", value="`Безопасная зона`", inline=False)
        return embed

    @discord.ui.button(label="📜 Профиль", style=discord.ButtonStyle.secondary, custom_id="g_profile")
    async def b_profile(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id != self.user.id: return await i.response.send_message("Это не ваш персонаж!", ephemeral=True)
        embed = await get_profile_embed(self.bot, self.user)
        await i.response.edit_message(embed=embed, view=ProfileUI(self.bot, self.user, main_view=self))

    @discord.ui.button(label="🎒 Инвентарь", style=discord.ButtonStyle.secondary, custom_id="g_inv")
    async def b_inv(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id != self.user.id: return await i.response.send_message("Это не ваш персонаж!", ephemeral=True)
        inv_view = InventoryUI(self.bot, self.user, main_view=self)
        embed = await inv_view.generate_embed()
        await i.response.edit_message(embed=embed, view=inv_view)

    @discord.ui.button(label="🔥 Прокачка", style=discord.ButtonStyle.success, custom_id="g_levelup")
    async def b_lvlup(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id != self.user.id: return await i.response.send_message("Это не ваш персонаж!", ephemeral=True)
        lvlup_view = LevelUpUI(self.bot, self.user, main_view=self)
        embed = await lvlup_view.generate_levelup_embed()
        await i.response.edit_message(embed=embed, view=lvlup_view)

    @discord.ui.button(label="⚔️ Охота (Фарм)", style=discord.ButtonStyle.danger, custom_id="g_farm")
    async def b_farm(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id != self.user.id: return await i.response.send_message("Это не ваш персонаж!", ephemeral=True)
        async with self.bot.db.execute("SELECT energy, successful_hunts FROM users WHERE id = ?", (self.user.id,)) as cursor:
            row = await cursor.fetchone()
        energy, hunts = row if row else (5, 0)

        embed = discord.Embed(description=f"## 🗺️ Выбор локации\n\nЭнергия: **{'⚡' * energy}{'⚪' * (5 - energy)}** ({energy}/5)\nУспешных зачисток: 🏆 **{hunts}**\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n", color=discord.Color.dark_red())
        embed.set_thumbnail(url=self.user.display_avatar.url)
        for key, data in LOCATIONS.items():
            status = f"✅ Доступно" if hunts >= data['req_hunts'] else f"🔒 Нужно {data['req_hunts']} побед"
            embed.add_field(name=data['name'], value=f"`{status}` | Риск: {data['base_death']}%", inline=False)
        
        await i.response.edit_message(embed=embed, view=FarmUI(self.bot, self.user, main_view=self))

class RegistrationModal(discord.ui.Modal, title='Создание персонажа'):
    char_name = discord.ui.TextInput(label='Имя вашего героя', placeholder='Например: Арториас', min_length=3, max_length=20)
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        name = self.char_name.value
        await self.bot.db.execute("INSERT INTO users (id, balance, char_name, level, stat_points, energy, last_energy_update, successful_hunts, strength, vitality, luck) VALUES (?, 0, ?, 1, 0, 5, 0, 0, 1, 1, 1) ON CONFLICT(id) DO UPDATE SET char_name = ?", (interaction.user.id, name, name))
        await self.bot.db.commit()
        view = GameUI(self.bot, interaction.user)
        embed = await view.get_main_embed()
        await interaction.response.send_message(content=f"🎉 Вы создали персонажа **{name}**!", embed=embed, view=view)

class Game(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def send_hunt_menu(self, interaction: discord.Interaction, is_edit: bool = False):
        async with self.bot.db.execute("SELECT energy, last_energy_update, successful_hunts FROM users WHERE id = ?", (interaction.user.id,)) as cursor:
            row = await cursor.fetchone()
        energy, last_update, hunts = row if row else (5, 0, 0)
        
        now = int(time.time())
        if energy < 5:
            recovered = (now - last_update) // 300
            if recovered > 0:
                energy = min(5, energy + recovered)
                last_update = 0 if energy == 5 else last_update + (recovered * 300)
                await self.bot.db.execute("UPDATE users SET energy = ?, last_energy_update = ? WHERE id = ?", (energy, last_update, interaction.user.id))
                await self.bot.db.commit()

        embed = discord.Embed(description=f"## 🗺️ Выбор локации\n\nЭнергия: **{'⚡' * energy}{'⚪' * (5 - energy)}** ({energy}/5)\nУспешных зачисток: 🏆 **{hunts}**\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n", color=discord.Color.dark_red())
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        for key, data in LOCATIONS.items():
            status = f"✅ Доступно" if hunts >= data['req_hunts'] else f"🔒 Нужно {data['req_hunts']} побед"
            embed.add_field(name=data['name'], value=f"`{status}` | Риск: {data['base_death']}%", inline=False)
        
        view = FarmUI(self.bot, interaction.user, main_view=GameUI(self.bot, interaction.user))
        if is_edit: await interaction.response.edit_message(embed=embed, view=view)
        else: await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="game", description="🎮 Открыть игровое меню персонажа")
    async def game(self, interaction: discord.Interaction):
        async with self.bot.db.execute("SELECT char_name FROM users WHERE id = ?", (interaction.user.id,)) as cursor:
            row = await cursor.fetchone()
        if not row or not row[0]: return await interaction.response.send_modal(RegistrationModal(self.bot))
        view = GameUI(self.bot, interaction.user)
        embed = await view.get_main_embed()
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="profile", description="Посмотреть профиль персонажа")
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        embed = await get_profile_embed(self.bot, target)
        if not embed: return await interaction.response.send_message("❌ Персонаж не найден.", ephemeral=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="inventory", description="🎒 Открыть свой инвентарь предметов")
    async def inventory(self, interaction: discord.Interaction):
        view = InventoryUI(self.bot, interaction.user)
        embed = await view.generate_embed()
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="give_item", description="🛡️ [АДМИН] Выдать предмет игроку")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(item_name=[
        app_commands.Choice(name="💍 Кольцо Жертвенности", value="ring"),
        app_commands.Choice(name="💛 Кольцо Жадности", value="greed_ring"),
        app_commands.Choice(name="🔵 Кольцо Стремительности", value="swift_ring"),
        app_commands.Choice(name="🧪 Фляга Бодрости", value="flask"),
        app_commands.Choice(name="📜 Свиток Ярости", value="war_scroll"),
    ])
    async def give_item(self, interaction: discord.Interaction, member: discord.Member, item_name: app_commands.Choice[str], amount: int):
        await self.bot.db.execute("INSERT INTO inventory (user_id, item_name, amount, equipped) VALUES (?, ?, ?, 0) ON CONFLICT(user_id, item_name) DO UPDATE SET amount = amount + ?", (member.id, item_name.value, amount, amount))
        await self.bot.db.commit()
        await interaction.response.send_message(f"✅ Вы выдали **{amount} шт. {item_name.name}** игроку {member.mention}.", ephemeral=True)

    @app_commands.command(name="stats", description="📊 Серверная статистика: сообщения, войс, охоты за всё время")
    async def stats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with self.bot.db.execute("SELECT COUNT(*) FROM users WHERE char_name IS NOT NULL") as cursor:
            chars = (await cursor.fetchone())[0]
        async with self.bot.db.execute("SELECT SUM(message_count), SUM(voice_time), SUM(successful_hunts), SUM(total_souls_farmed) FROM users") as cursor:
            row = await cursor.fetchone()
        total_msgs  = row[0] or 0
        total_voice = row[1] or 0
        total_hunts = row[2] or 0
        total_souls = row[3] or 0

        embed = discord.Embed(
            title="📊 Статистика сервера",
            description="Суммарная активность всех участников за всё время.",
            color=discord.Color.blurple()
        )
        embed.add_field(name="🎮 Персонажей создано",   value=f"**{chars:,}**",          inline=True)
        embed.add_field(name="💬 Сообщений отправлено", value=f"**{total_msgs:,}**",   inline=True)
        embed.add_field(name="🎤 Часов в войсе",          value=f"**{round(total_voice / 3600, 1):,}**", inline=True)
        embed.add_field(name="⚔️ Успешных охот",        value=f"**{total_hunts:,}**",  inline=True)
        embed.add_field(name="👻 Душ добыто всего",      value=f"**{total_souls:,}**",  inline=True)
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Game(bot))