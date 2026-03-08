import discord
from discord.ext import commands
from discord import app_commands


def get_progress_bar(current: int, total: int, length: int = 10) -> str:

    if total <= 0: return f"[{'█' * length}]"
    if current >= total: return f"[{'█' * length}]"
    if current <= 0: return f"[{'░' * length}]"
    
    filled_length = int(length * current / total)
    empty_length = length - filled_length
    
    return f"[{'█' * filled_length}{'░' * empty_length}]"


ACHIEVEMENTS = {
    "activity": [
        {"id": "msg_100", "name": "Новичок пера", "desc": "Напишите 100 сообщений в чатах.", "target": 100, "type": "messages", "reward": "50 АП"},
        {"id": "msg_1000", "name": "Легенда чата", "desc": "Напишите 1000 сообщений.", "target": 1000, "type": "messages", "reward": "500 АП"},
        {"id": "voice_10", "name": "Душа компании", "desc": "Проведите 10 часов в голосовых каналах.", "target": 36000, "type": "voice", "reward": "300 АП"}
    ],
    "game": [
        {"id": "lvl_10", "name": "Закаленный в боях", "desc": "Достигните 10 уровня у костра.", "target": 10, "type": "level", "reward": "100 Душ"},
        {"id": "souls_10000", "name": "Лорд Пепла", "desc": "Накопите 10 000 душ.", "target": 10000, "type": "souls", "reward": "250 АП"}
    ]
}


class Achievements(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
            
        query = """
            INSERT INTO users (id, balance, bank, activity_points, total_activity_points, voice_time, message_count) 
            VALUES (?, 0, 0, 0, 0, 0, 1) 
            ON CONFLICT(id) DO UPDATE SET 
            message_count = message_count + 1
        """
        await self.bot.db.execute(query, (message.author.id,))
        await self.bot.db.commit()


class AchievementUI(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user

    async def generate_embed(self, category: str):
        # Достаем всю статистику игрока
        async with self.bot.db.execute("SELECT message_count, voice_time, level, balance FROM users WHERE id = ?", (self.user.id,)) as cursor:
            row = await cursor.fetchone()
            
        msgs = row[0] if row and row[0] else 0
        voice = row[1] if row and row[1] else 0
        level = row[2] if row and row[2] else 1
        souls = row[3] if row and row[3] else 0

        # Смотрим, какие ачивки он УЖЕ получил
        async with self.bot.db.execute("SELECT achievement_id FROM user_achievements WHERE user_id = ?", (self.user.id,)) as cursor:
            earned = [r[0] for r in await cursor.fetchall()]

        cat_names = {"activity": "💬 Активность", "game": "⚔️ Игра"}
        embed = discord.Embed(
            description=f"# 🏆 Достижения: {cat_names.get(category, '')}\nВыполняйте условия, чтобы получать уникальные награды.\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n", 
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=self.user.display_avatar.url)

        # Рисуем каждую ачивку
        for ach in ACHIEVEMENTS[category]:
            is_earned = ach["id"] in earned
            
            # Определяем, какую цифру проверять
            if ach["type"] == "messages":
                current = msgs
                display_current = f"{msgs} / {ach['target']}"
            elif ach["type"] == "voice":
                current = voice
                display_current = f"{round(voice/3600, 1)} / {round(ach['target']/3600, 1)} ч." # Переводим секунды в часы
            elif ach["type"] == "level":
                current = level
                display_current = f"{level} / {ach['target']}"
            elif ach["type"] == "souls":
                current = souls
                display_current = f"{souls} / {ach['target']}"
            else:
                current, display_current = 0, "0"

            if is_earned:
                progress_text = f"`[{'█' * 10}]` ✅ Выполнено!"
            else:
                progress_text = f"`{get_progress_bar(current, ach['target'])}` {display_current}"

            status_icon = "🏅" if is_earned else "🔒"
            embed.add_field(
                name=f"{status_icon} **{ach['name']}**", 
                value=f"*{ach['desc']}*\n🎁 Награда: `{ach['reward']}`\nПрогресс: {progress_text}", 
                inline=False
            )
            
        return embed

    @discord.ui.button(label="💬 Активность", style=discord.ButtonStyle.primary, custom_id="ach_activity")
    async def btn_activity(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("❌ Это не ваша статистика!", ephemeral=True)
        embed = await self.generate_embed("activity")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⚔️ Игра", style=discord.ButtonStyle.danger, custom_id="ach_game")
    async def btn_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return await interaction.response.send_message("❌ Это не ваша статистика!", ephemeral=True)
        embed = await self.generate_embed("game")
        await interaction.response.edit_message(embed=embed, view=self)
        


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Achievements(bot))