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
    "ring": {"name": "💍 Кольцо Жертвенности", "price": 1000, "desc": "Одноразовое. Спасает ваши души от потери при смертельном ударе на охоте. (Нужно надеть)"},
    "flask": {"name": "🧪 Фляга Бодрости", "price": 500, "desc": "Восстанавливает вашу бодрость (энергию) до максимума (5/5)."}
}

async def get_profile_embed(bot, user: discord.Member):
    async with bot.db.execute("SELECT char_name, level, balance, current_location, stat_points, strength, vitality, luck FROM users WHERE id = ?", (user.id,)) as cursor:
        row = await cursor.fetchone()
        
    if not row or not row[0]: return None 
        
    char_name, level, souls, loc_key, stat_pts, strg, vit, luck = row
    loc_name = LOCATIONS[loc_key]["name"] if loc_key in LOCATIONS else "🏕️ Безопасная зона"
        
    embed = discord.Embed(description=f"# 📜 Профиль: {char_name}\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n", color=discord.Color.blurple())
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="👤 Владелец", value=user.mention, inline=False)
    embed.add_field(name="🔸 Уровень", value=f"**{level}**", inline=True)
    embed.add_field(name="🔸 Души", value=f"**{souls}** 👻", inline=True)
    embed.add_field(name="📍 Локация", value=f"`{loc_name}`", inline=True)
    
    embed.add_field(name="Свободные очки (SP)", value=f"🌟 **{stat_pts}**", inline=False)
    embed.add_field(name="💪 Сила", value=f"**{strg}**", inline=True)
    embed.add_field(name="❤️ Живучесть", value=f"**{vit}**", inline=True)
    embed.add_field(name="🍀 Удача", value=f"**{luck}**", inline=True)
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
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Торговец смотрит не на вас!", ephemeral=True)
        item = ITEMS[item_key]
        
        async with self.bot.db.execute("SELECT balance FROM users WHERE id = ?", (self.user.id,)) as cursor:
            balance = (await cursor.fetchone())[0]

        if balance < item["price"]:
            return await interaction.response.send_message(f"❌ У вас не хватает душ! Нужно {item['price']} 👻.", ephemeral=True)

        await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (item["price"], self.user.id))
        await self.bot.db.execute(
            "INSERT INTO inventory (user_id, item_name, amount, equipped) VALUES (?, ?, 1, 0) ON CONFLICT(user_id, item_name) DO UPDATE SET amount = amount + 1", 
            (self.user.id, item_key)
        )
        await self.bot.db.commit()
        await interaction.response.send_message(f"🛍️ Вы успешно купили **{item['name']}** за {item['price']} 👻!", ephemeral=True)

    @discord.ui.button(label="Купить Кольцо (1000 👻)", style=discord.ButtonStyle.secondary, emoji="💍")
    async def btn_ring(self, interaction: discord.Interaction, button: discord.ui.Button): await self.buy_item(interaction, "ring")

    @discord.ui.button(label="Купить Флягу (500 👻)", style=discord.ButtonStyle.secondary, emoji="🧪")
    async def btn_flask(self, interaction: discord.Interaction, button: discord.ui.Button): await self.buy_item(interaction, "flask")

    @discord.ui.button(label="Снова в бой", style=discord.ButtonStyle.primary, row=1)
    async def btn_hunt(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваша игра!", ephemeral=True)
        await self.farm_view.process_farm(interaction, self.location_key)

    @discord.ui.button(label="🔙 Вернуться в лагерь", style=discord.ButtonStyle.secondary, row=1)
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
        equipped_count = sum([row[2] for row in items if row[2] > 0])
        
        embed = discord.Embed(title="🎒 Инвентарь и Экипировка", color=discord.Color.dark_gold())
        embed.set_thumbnail(url=self.user.display_avatar.url)
        
        desc = f"Экипировано: **{equipped_count}/4 слотов**\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
        
        if not items:
            desc += "Ваш рюкзак абсолютно пуст."
        else:
            for item_id, amount, equipped in items:
                if item_id in ITEMS:
                    item_data = ITEMS[item_id]
                    eq_text = f" *(Надето: {equipped} шт.)*" if equipped > 0 else ""
                    desc += f"**{item_data['name']}** — {amount} шт.{eq_text}\n*{item_data['desc']}*\n\n"
        embed.description = desc
        return embed

    @discord.ui.button(label="Надеть Кольцо", style=discord.ButtonStyle.secondary, emoji="💍", row=0)
    async def btn_equip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш инвентарь!", ephemeral=True)
        items = await self.get_inventory_data()
        equipped_count = sum([row[2] for row in items if row[2] > 0])
        
        if equipped_count >= 4: return await interaction.response.send_message("❌ Заняты все 4 слота экипировки!", ephemeral=True)

        ring_data = next((row for row in items if row[0] == 'ring'), None)
        if not ring_data or ring_data[1] <= ring_data[2]:
            return await interaction.response.send_message("❌ У вас в рюкзаке больше нет свободных колец!", ephemeral=True)

        await self.bot.db.execute("UPDATE inventory SET equipped = equipped + 1 WHERE user_id = ? AND item_name = 'ring'", (self.user.id,))
        await self.bot.db.commit()
        embed = await self.generate_embed()
        await interaction.response.edit_message(content="✅ Вы экипировали Кольцо Жертвенности.", embed=embed, view=self)

    @discord.ui.button(label="Снять Кольцо", style=discord.ButtonStyle.secondary, emoji="💍", row=0)
    async def btn_unequip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш инвентарь!", ephemeral=True)
        items = await self.get_inventory_data()
        ring_data = next((row for row in items if row[0] == 'ring'), None)
        
        if not ring_data or ring_data[2] <= 0: return await interaction.response.send_message("❌ На вас не надето это кольцо!", ephemeral=True)

        await self.bot.db.execute("UPDATE inventory SET equipped = equipped - 1 WHERE user_id = ? AND item_name = 'ring'", (self.user.id,))
        await self.bot.db.commit()
        embed = await self.generate_embed()
        await interaction.response.edit_message(content="✅ Вы сняли Кольцо Жертвенности в рюкзак.", embed=embed, view=self)

    @discord.ui.button(label="Выпить Флягу", style=discord.ButtonStyle.success, emoji="🧪", row=1)
    async def btn_flask(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш инвентарь!", ephemeral=True)
        items = await self.get_inventory_data()
        flask_data = next((row for row in items if row[0] == 'flask'), None)
            
        if not flask_data or flask_data[1] <= 0: return await interaction.response.send_message("❌ У вас нет Фляги Бодрости!", ephemeral=True)

        await self.bot.db.execute("UPDATE inventory SET amount = amount - 1 WHERE user_id = ? AND item_name = 'flask'", (self.user.id,))
        await self.bot.db.execute("UPDATE users SET energy = 5, last_energy_update = 0 WHERE id = ?", (self.user.id,))
        await self.bot.db.commit()
        embed = await self.generate_embed()
        await interaction.response.edit_message(content="✅ Вы выпили Флягу! Энергия восстановлена (5/5).", embed=embed, view=self)

    @discord.ui.button(label="🔙 Вернуться", style=discord.ButtonStyle.primary, row=1)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш персонаж!", ephemeral=True)
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
        async with self.bot.db.execute("SELECT balance, level, lost_souls, energy, last_energy_update, successful_hunts, strength, vitality, luck FROM users WHERE id = ?", (self.user.id,)) as cursor:
            row = await cursor.fetchone()

        if not row: return
        balance, level, lost_souls, energy, last_update, hunts, strength, vitality, luck = row
        now = int(time.time())

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

        death_chance = max(5, loc_data["base_death"] - (level - 1) - (vitality * 0.5))
        roll = random.uniform(0, 100)

        embed = discord.Embed(color=discord.Color.dark_theme())
        embed.set_thumbnail(url=self.user.display_avatar.url)

        # ПРОВЕРЯЕМ КОЛЬЦО
        async with self.bot.db.execute("SELECT amount, equipped FROM inventory WHERE user_id = ? AND item_name = 'ring'", (self.user.id,)) as cursor:
            ring_row = await cursor.fetchone()
        has_equipped_ring = ring_row and ring_row[1] > 0

        if roll <= death_chance:
            if has_equipped_ring:
                # КОЛЬЦО СПАСАЕТ
                await self.bot.db.execute("UPDATE inventory SET amount = amount - 1, equipped = equipped - 1 WHERE user_id = ? AND item_name = 'ring'", (self.user.id,))
                await self.bot.db.execute("UPDATE users SET energy = ?, last_energy_update = ? WHERE id = ?", (energy, last_update, self.user.id))
                await self.bot.db.commit()
                
                embed.title = "💍 КОЛЬЦО РАСКОЛОЛОСЬ!"
                embed.description = f"## Локация: {loc_data['name']}\nСмертельный удар обрушился на вас, но надетое **Кольцо Жертвенности** вспыхнуло ярким светом и рассыпалось в прах. Души сохранены!\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n💰 Текущий баланс: **{balance}** 👻\nОсталось бодрости: ⚡ {energy}/5"
                embed.color = discord.Color.gold()
                await interaction.response.edit_message(embed=embed, view=HuntAgainUI(self.bot.get_cog('Game'), self.user))
            else:
                # ОБЫЧНАЯ СМЕРТЬ
                new_lost_souls = balance
                await self.bot.db.execute("UPDATE users SET balance = 0, lost_souls = ?, current_location = ?, energy = ?, last_energy_update = ? WHERE id = ?", (new_lost_souls, location_key, energy, last_update, self.user.id))
                await self.bot.db.commit()
                
                embed.title = "☠️ ВЫ ПОГИБЛИ!"
                embed.description = f"## Локация: {loc_data['name']}\nТьма поглотила вас.\nВы выронили `{new_lost_souls}` 👻 душ.\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n💰 Текущий баланс: **0** 👻\nОсталось бодрости: ⚡ {energy}/5"
                embed.color = discord.Color.red()
                if lost_souls > 0: embed.description += "\n⚠️ **Предыдущее кровавое пятно исчезло. Старые души утеряны!**"
                await interaction.response.edit_message(embed=embed, view=HuntAgainUI(self.bot.get_cog('Game'), self.user))
        else:
            # ПОБЕДА
            max_farm = loc_data["max_souls"] + (luck * 10)
            base_reward = random.randint(loc_data["min_souls"], max_farm)
            bonus_multiplier = 1 + (strength * 0.01)
            reward = int(base_reward * bonus_multiplier)
            
            pure_reward = reward 
            new_hunts = hunts + 1 
            
            recovered_text = ""
            if lost_souls > 0:
                reward += lost_souls
                recovered_text = f"\n🩸 Вы коснулись пятна крови и вернули `{lost_souls}` 👻 душ!"

            new_balance = balance + reward 
            await self.bot.db.execute("UPDATE users SET balance = balance + ?, lost_souls = 0, current_location = ?, total_souls_farmed = total_souls_farmed + ?, energy = ?, last_energy_update = ?, successful_hunts = ? WHERE id = ?", (reward, location_key, pure_reward, energy, last_update, new_hunts, self.user.id))
            await self.bot.db.commit()
            
            embed.title = "⚔️ Охота успешна!"
            embed.description = f"## Локация: {loc_data['name']}\nВы выжили и принесли `{pure_reward}` 👻 душ.{recovered_text}\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n💰 Текущий баланс: **{new_balance}** 👻\n🏆 Успешных побед: **{new_hunts}**\nОсталось бодрости: ⚡ {energy}/5"
            embed.color = discord.Color.green()
            embed.set_footer(text=f"Шанс смерти: {round(death_chance, 1)}% | Снижено уровнем и живучестью")

            # СПАВН ТОРГОВЦА (15%)
            if random.randint(1, 100) <= 15:
                embed.description += "\n\n🎒 **Странствующий торговец:** *«Эй, путник! Вижу, ты богат. Не хочешь взглянуть на мои товары?»*"
                await interaction.response.edit_message(embed=embed, view=MerchantUI(self.bot.get_cog('Game'), self.user))
            else:
                await interaction.response.edit_message(embed=embed, view=HuntAgainUI(self.bot.get_cog('Game'), self.user))

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
        # Исправлено: добавлены strength, vitality, luck
        await self.bot.db.execute("INSERT INTO users (id, balance, char_name, level, stat_points, energy, last_energy_update, successful_hunts, strength, vitality, luck) VALUES (?, 0, ?, 1, 0, 5, 0, 0, 1, 1, 1) ON CONFLICT(id) DO UPDATE SET char_name = ?", (interaction.user.id, name, name))
        await self.bot.db.commit()
        view = GameUI(self.bot, interaction.user)
        embed = await view.get_main_embed()
        await interaction.response.send_message(content=f"🎉 Вы создали персонажа **{name}**!", embed=embed, view=view)

class Game(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # Метод добавлен
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
        app_commands.Choice(name="🧪 Фляга Бодрости", value="flask")
    ])
    async def give_item(self, interaction: discord.Interaction, member: discord.Member, item_name: app_commands.Choice[str], amount: int):
        # Исправлено: добавлена колонка equipped
        await self.bot.db.execute("INSERT INTO inventory (user_id, item_name, amount, equipped) VALUES (?, ?, ?, 0) ON CONFLICT(user_id, item_name) DO UPDATE SET amount = amount + ?", (member.id, item_name.value, amount, amount))
        await self.bot.db.commit()
        await interaction.response.send_message(f"✅ Вы выдали **{amount} шт. {item_name.name}** игроку {member.mention}.", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Game(bot))