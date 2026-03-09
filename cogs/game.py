import discord
from discord.ext import commands
from discord import app_commands
import random
import math
import asyncio
import aiosqlite
import time

def get_level_cost(target_level: int) -> int:
    if target_level <= 1:
        return 0
    if target_level == 2:
        return 673
        
    if target_level <= 12:
        cost = 673
        for _ in range(3, target_level + 1):
            cost = int(cost * 1.025)
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

async def get_profile_embed(bot, user: discord.Member):
    """Генерирует карточку профиля для любого игрока"""
    async with bot.db.execute("SELECT char_name, level, balance, current_location FROM users WHERE id = ?", (user.id,)) as cursor:
        row = await cursor.fetchone()
        
    if not row or not row[0]:
        return None 
        
    char_name = row[0]
    level = row[1]
    souls = row[2]
    loc_key = row[3] if row[3] else "camp"
    
    if loc_key in LOCATIONS:
        loc_name = LOCATIONS[loc_key]["name"]
    else:
        loc_name = "🏕️ Безопасная зона"
        
    embed = discord.Embed(
        description=f"# 📜 Профиль: {char_name}\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="👤 Владелец", value=user.mention, inline=False)
    embed.add_field(name="🔸 Уровень", value=f"**{level}**", inline=True)
    embed.add_field(name="🔸 Души", value=f"**{souls}** 👻", inline=True)
    embed.add_field(name="📍 Последняя локация", value=f"`{loc_name}`", inline=False)
    
    return embed
    
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

class LevelUpUI(discord.ui.View):
    def __init__(self, bot, user, main_view):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user
        self.main_view = main_view

    async def generate_levelup_embed(self):
        async with self.bot.db.execute("SELECT balance, level FROM users WHERE id = ?", (self.user.id,)) as cursor:
            row = await cursor.fetchone()
            
        balance = row[0] if row else 0
        level = row[1] if row and row[1] else 1
        
        if level >= 80:
            return discord.Embed(title="👑 Максимальный уровень", description="Вы достигли предела развития (80 уровень).", color=discord.Color.gold())
            
        cost = get_level_cost(level + 1)
        
        embed = discord.Embed(
            description=f"## 🔥 Отдых у костра\n\nЗдесь вы можете пожертвовать собранные души, чтобы стать сильнее и снизить шанс гибели.\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=self.user.display_avatar.url)
        embed.add_field(name="🔸 Текущий уровень", value=f"**{level}**", inline=True)
        embed.add_field(name="🔸 Ваши души", value=f"**{balance}** 👻", inline=True)
        embed.add_field(name="🔸 Стоимость улучшения", value=f"**{cost}** 👻", inline=False)
        
        if balance < cost:
            embed.set_footer(text=f"Вам не хватает {cost - balance} душ для повышения уровня.")
        else:
            embed.set_footer(text="У вас достаточно душ! Нажмите кнопку повышения уровня.")
            
        return embed

    @discord.ui.button(label="⬆️ Повысить уровень", style=discord.ButtonStyle.success, custom_id="lvlup_confirm")
    async def btn_confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш персонаж!", ephemeral=True)
            
        async with self.bot.db.execute("SELECT balance, level FROM users WHERE id = ?", (self.user.id,)) as cursor:
            row = await cursor.fetchone()
            
        balance = row[0] if row else 0
        level = row[1] if row and row[1] else 1
        
        if level >= 80:
            return await interaction.response.send_message("Вы уже достигли максимального уровня!", ephemeral=True)
            
        next_level = level + 1
        cost = get_level_cost(next_level)
        
        if balance < cost:
            new_embed = await self.generate_levelup_embed()
            new_embed.add_field(
                name="❌ НЕДОСТАТОЧНО ДУШ", 
                value=f"Для повышения уровня не хватает **{cost - balance}** 👻.", 
                inline=False
            )
            return await interaction.response.edit_message(embed=new_embed, view=self)
            
        await self.bot.db.execute("UPDATE users SET balance = balance - ?, level = ?, stat_points = stat_points + 1 WHERE id = ?", (cost, next_level, self.user.id))
        await self.bot.db.commit()
        
        new_embed = await self.generate_levelup_embed()
        new_embed.add_field(
            name="🎉 УРОВЕНЬ ПОВЫШЕН!", 
            value=f"Вы пожертвовали души костру. Достигнут **{next_level} уровень**!\nПолучено **1 очко характеристик**.", 
            inline=False
        )
        await interaction.response.edit_message(embed=new_embed, view=self)

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
        async with self.bot.db.execute("SELECT balance, level, lost_souls, energy, last_energy_update, successful_hunts FROM users WHERE id = ?", (self.user.id,)) as cursor:
            row = await cursor.fetchone()

        if not row: return
        balance, level, lost_souls, energy, last_update, hunts = row
        now = int(time.time())

        if hunts < loc_data["req_hunts"]:
            return await interaction.response.send_message(f"🔒 Локация закрыта! Нужно {loc_data['req_hunts']} успешных побед.", ephemeral=True)

        if energy < 5:
            passed_time = now - last_update
            recovered = passed_time // 300 
            if recovered > 0:
                energy += recovered
                if energy >= 5:
                    energy, last_update = 5, 0
                else:
                    last_update += recovered * 300
                await self.bot.db.execute("UPDATE users SET energy = ?, last_energy_update = ? WHERE id = ?", (energy, last_update, self.user.id))
                await self.bot.db.commit()

        if energy < 1:
            time_left = 300 - ((now - last_update) % 300)
            mins, secs = divmod(time_left, 60)
            return await interaction.response.send_message(f"💤 Вы истощены! Следующее очко бодрости через **{mins} мин. {secs} сек.**", ephemeral=True)

        energy -= 1
        if last_update == 0: 
            last_update = now

        death_chance = max(5, loc_data["base_death"] - (level - 1))
        roll = random.randint(1, 100)

        embed = discord.Embed(color=discord.Color.dark_theme())
        embed.set_thumbnail(url=self.user.display_avatar.url)

        if roll <= death_chance:
            new_lost_souls = balance
            await self.bot.db.execute(
                "UPDATE users SET balance = 0, lost_souls = ?, current_location = ?, energy = ?, last_energy_update = ? WHERE id = ?", 
                (new_lost_souls, location_key, energy, last_update, self.user.id)
            )
            await self.bot.db.commit()
            
            embed.title = "☠️ ВЫ ПОГИБЛИ!"
            embed.description = f"## Локация: {loc_data['name']}\nТьма поглотила вас.\nВы выронили `{new_lost_souls}` 👻 душ.\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n💰 Текущий баланс: **0** 👻\nОсталось бодрости: ⚡ {energy}/5"
            embed.color = discord.Color.red()
            
            if lost_souls > 0:
                embed.description += "\n⚠️ **Предыдущее кровавое пятно исчезло. Старые души утеряны!**"
        else:
            reward = random.randint(loc_data["min_souls"], loc_data["max_souls"])
            pure_reward = reward 
            new_hunts = hunts + 1 
            
            recovered_text = ""
            if lost_souls > 0:
                reward += lost_souls
                recovered_text = f"\n🩸 Вы коснулись пятна крови и вернули `{lost_souls}` 👻 душ!"

            new_balance = balance + reward 

            await self.bot.db.execute(
                "UPDATE users SET balance = balance + ?, lost_souls = 0, current_location = ?, total_souls_farmed = total_souls_farmed + ?, energy = ?, last_energy_update = ?, successful_hunts = ? WHERE id = ?", 
                (reward, location_key, pure_reward, energy, last_update, new_hunts, self.user.id)
            )
            await self.bot.db.commit()
            
            embed.title = "⚔️ Охота успешна!"
            embed.description = f"## Локация: {loc_data['name']}\nВы выжили и принесли `{pure_reward}` 👻 душ.{recovered_text}\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n💰 Текущий баланс: **{new_balance}** 👻\n🏆 Успешных побед: **{new_hunts}**\nОсталось бодрости: ⚡ {energy}/5"
            embed.color = discord.Color.green()
            embed.set_footer(text=f"Шанс смерти: {death_chance}% | Снижено уровнем")

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🪦 Кладбище", style=discord.ButtonStyle.secondary, custom_id="farm_grave", row=0)
    async def btn_grave(self, interaction: discord.Interaction, button: discord.ui.Button): await self.process_farm(interaction, "graveyard")

    @discord.ui.button(label="🌲 Лес", style=discord.ButtonStyle.secondary, custom_id="farm_forest", row=0)
    async def btn_forest(self, interaction: discord.Interaction, button: discord.ui.Button): await self.process_farm(interaction, "forest")

    @discord.ui.button(label="💀 Катакомбы", style=discord.ButtonStyle.secondary, custom_id="farm_cata", row=0)
    async def btn_cata(self, interaction: discord.Interaction, button: discord.ui.Button): await self.process_farm(interaction, "catacombs")

    @discord.ui.button(label="🏰 Замок", style=discord.ButtonStyle.danger, custom_id="farm_castle", row=1)
    async def btn_castle(self, interaction: discord.Interaction, button: discord.ui.Button): await self.process_farm(interaction, "castle")

    @discord.ui.button(label="🌋 Пик Дракона", style=discord.ButtonStyle.danger, custom_id="farm_peak", row=1)
    async def btn_peak(self, interaction: discord.Interaction, button: discord.ui.Button): await self.process_farm(interaction, "peak")

    @discord.ui.button(label="🌌 Бездна", style=discord.ButtonStyle.danger, custom_id="farm_abyss", row=1)
    async def btn_abyss(self, interaction: discord.Interaction, button: discord.ui.Button): await self.process_farm(interaction, "abyss")

    @discord.ui.button(label="🔙 Вернуться в лагерь", style=discord.ButtonStyle.primary, row=2, custom_id="farm_back")
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш персонаж!", ephemeral=True)
        embed = await self.main_view.get_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.main_view)

class GameUI(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user

    async def get_main_embed(self):
        async with self.bot.db.execute("SELECT char_name, level, balance FROM users WHERE id = ?", (self.user.id,)) as cursor:
            row = await cursor.fetchone()
            
        name = row[0]
        level = row[1]
        souls = row[2]
        
        embed = discord.Embed(
            description=f"# 🏕️ {name}\n\nВы находитесь в безопасной зоне. Отсюда можно отправиться в рейд, проверить свои навыки или посидеть у костра.\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n",
            color=discord.Color.dark_theme()
        )
        embed.set_thumbnail(url=self.user.display_avatar.url)
        embed.add_field(name="🔸 Текущий Уровень", value=f"**{level}**", inline=True)
        embed.add_field(name="🔸 Накоплено Душ", value=f"**{souls}** 👻", inline=True)
        embed.add_field(name="🔸 Локация", value="`Безопасная зона`", inline=False)
        return embed

    @discord.ui.button(label="📜 Профиль", style=discord.ButtonStyle.secondary, custom_id="game_profile")
    async def btn_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш персонаж!", ephemeral=True)
            
        embed = await get_profile_embed(self.bot, self.user)
        profile_view = ProfileUI(self.bot, self.user, main_view=self)
        
        await interaction.response.edit_message(embed=embed, view=profile_view)

    @discord.ui.button(label="🔥 Прокачка", style=discord.ButtonStyle.success, custom_id="game_levelup")
    async def btn_lvlup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш персонаж!", ephemeral=True)
            
        lvlup_view = LevelUpUI(self.bot, self.user, main_view=self)
        embed = await lvlup_view.generate_levelup_embed()
        
        await interaction.response.edit_message(embed=embed, view=lvlup_view)

    @discord.ui.button(label="⚔️ Охота (Фарм)", style=discord.ButtonStyle.danger, custom_id="game_farm")
    async def btn_farm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("Это не ваш персонаж!", ephemeral=True)
            
        # Запрашиваем энергию и победы
        async with self.bot.db.execute("SELECT energy, successful_hunts FROM users WHERE id = ?", (self.user.id,)) as cursor:
            row = await cursor.fetchone()
        energy = row[0] if row else 5
        hunts = row[1] if row else 0

        embed = discord.Embed(
            description=f"## 🗺️ Выбор локации\n\nЭнергия: **{'⚡' * energy}{'⚪' * (5 - energy)}** ({energy}/5)\nУспешных зачисток: 🏆 **{hunts}**\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n", 
            color=discord.Color.dark_red()
        )
        embed.set_thumbnail(url=self.user.display_avatar.url)
        
        # Динамически выводим статус локаций
        for key, data in LOCATIONS.items():
            status = f"✅ Доступно" if hunts >= data['req_hunts'] else f"🔒 Нужно {data['req_hunts']} побед"
            embed.add_field(name=data['name'], value=f"`{status}` | Риск: {data['base_death']}%", inline=False)
        
        farm_view = FarmUI(self.bot, self.user, main_view=self)
        await interaction.response.edit_message(embed=embed, view=farm_view)

class RegistrationModal(discord.ui.Modal, title='Создание персонажа'):
    char_name = discord.ui.TextInput(
        label='Имя вашего героя',
        placeholder='Например: Арториас',
        min_length=3,
        max_length=20,
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        name = self.char_name.value
        user_id = interaction.user.id
        
        await self.bot.db.execute(
            "INSERT INTO users (id, balance, char_name, level, stat_points, energy, last_energy_update, successful_hunts) VALUES (?, 0, ?, 1, 0, 5, 0, 0) ON CONFLICT(id) DO UPDATE SET char_name = ?", 
            (user_id, name, name)
        )
        await self.bot.db.commit()
        
        view = GameUI(self.bot, interaction.user)
        embed = await view.get_main_embed()
        
        await interaction.response.send_message(
            content=f"🎉 Вы успешно создали персонажа **{name}**! Добро пожаловать к костру.", 
            embed=embed, 
            view=view
        )


class Game(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="game", description="🎮 Открыть игровое меню персонажа")
    async def game(self, interaction: discord.Interaction) -> None:
        user_id = interaction.user.id
        
        async with self.bot.db.execute("SELECT char_name FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            
        if not row or not row[0]:
            # Вызываем всплывающее окно регистрации
            return await interaction.response.send_modal(RegistrationModal(self.bot))

        view = GameUI(self.bot, interaction.user)
        embed = await view.get_main_embed()
        
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="profile", description="Посмотреть профиль персонажа")
    @app_commands.describe(member="Кого проверить? (Оставьте пустым, чтобы посмотреть себя)")
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        target = member or interaction.user
        
        embed = await get_profile_embed(self.bot, target)
        
        if not embed:
            if target == interaction.user:
                await interaction.response.send_message("❌ У вас еще нет персонажа! Введите `/game`, чтобы создать его.", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ У {target.mention} еще нет персонажа.", ephemeral=True)
            return
            
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Game(bot))