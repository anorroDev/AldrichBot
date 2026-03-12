import discord
from discord.ext import commands
from discord import app_commands

def get_progress_bar(current: int, total: int, length: int = 8) -> str:
    if total <= 0: 
        return f"[{'▰' * length}] 100%"
        
    percent = int((current / total) * 100)
    if percent > 100: percent = 100
    if percent < 0: percent = 0
        
    filled = int(length * current / total)
    if filled > length: filled = length
    if filled < 0: filled = 0
        
    empty = length - filled
    return f"[{'▰' * filled}{'▱' * empty}] {percent}%"

ACHIEVEMENTS = {
    "activity": [
        {"id": "msg_100", "name": "Местный ", "desc": "Напишите 100 сообщений в чатах.", "target": 100, "type": "messages", "reward_text": "100 АП + Роль", "reward_ap": 100, "reward_role": 1480297619577372762},
        {"id": "msg_1000", "name": "Легенда чата", "desc": "Напишите 1000 сообщений.", "target": 1000, "type": "messages", "reward_text": "500 АП + Роль Мудреца", "reward_ap": 500, "reward_role": 1480298458035519579},
        {"id": "msg_5000", "name": "Магистр Слов", "desc": "Напишите 5000 сообщений.", "target": 5000, "type": "messages", "reward_text": "1000 АП + Роль Хранителя Архивов", "reward_ap": 5000, "reward_role": 1480298580341293209},
        {"id": "voice_10", "name": "Душа компании", "desc": "Проведите 10 часов в голосовых каналах.", "target": 36000, "type": "voice", "reward_text": "100 АП + Роль", "reward_ap": 100, "reward_role": 1480299968567971840},
        {"id": "voice_50", "name": "Задрот", "desc": "Проведите 50 часов в голосовых каналах.", "target": 180000, "type": "voice", "reward_text": "250 АП", "reward_ap": 250},
        {"id": "voice_100", "name": "Голос Сервера", "desc": "Проведите 100 часов в голосовых каналах.", "target": 360000, "type": "voice", "reward_text": "500 АП + Роль", "reward_ap": 500, "reward_role": 1480300125065707612},
        {"id": "voice_500", "name": "Призрак Войса", "desc": "Проведите 500 часов в голосовых каналах.", "target": 1800000, "type": "voice", "reward_text": "5000 АП + Роль", "reward_ap": 5000, "reward_role": 1480300525978386493}

    ],
    "game": [
        {"id": "lvl_10", "name": "Закаленный в боях", "desc": "Достигните 10 уровня у костра.", "target": 10, "type": "level", "reward_text": "100 АП + Роль Перельный", "reward_ap": 100, "reward_role": 1480302681091477615},
        {"id": "lvl_50", "name": "Элден Лорд", "desc": "Достигните 50 уровня у костра.", "target": 50, "type": "level", "reward_text": "1000 АП + Роль Лорд Пепла", "reward_ap": 1000, "reward_role": 1480303132369092759},
        {"id": "lvl_100", "name": "Истинный Владыка", "desc": "Достигните 100 уровня у костра.", "target": 100, "type": "level", "reward_text": "2500 АП + Роль Лорд Пепла", "reward_ap": 2500, "reward_role": 1480303132369092759},
        {"id": "souls_10000", "name": "Лорд Пепла", "desc": "Накопите 10 000 душ.", "target": 10000, "type": "souls", "reward_text": "250 АП", "reward_ap": 100},
        {"id": "souls_100000", "name": "Пожиратель Богов", "desc": "Накопите 100 000 душ.", "target": 100000, "type": "souls", "reward_text": "1500 АП + Роль", "reward_ap": 1500, "reward_role": 1480303511219732601}
    ]
}

class AchievementUI(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user

    async def generate_embed(self, category: str):
        async with self.bot.db.execute("SELECT message_count, voice_time, level, total_souls_farmed FROM users WHERE id = ?", (self.user.id,)) as cursor:
            row = await cursor.fetchone()
            
        msgs = row[0] if row and row[0] else 0
        voice = row[1] if row and row[1] else 0
        level = row[2] if row and row[2] else 1
        souls = row[3] if row and row[3] else 0

        async with self.bot.db.execute("SELECT achievement_id FROM user_achievements WHERE user_id = ?", (self.user.id,)) as cursor:
            earned = [r[0] for r in await cursor.fetchall()]

        cat_names = {"activity": "💬 Активность", "game": "⚔️ Игра"}
        embed = discord.Embed(
            description=f"# 🏆 Достижения: {cat_names.get(category, '')}\nВыполняйте условия, чтобы получать уникальные награды.\n Награды включают в себя уникальные роли,\n описание которых вы можете прочитать в #info\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n", 
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=self.user.display_avatar.url)

        for ach in ACHIEVEMENTS[category]:
            is_earned = ach["id"] in earned
            
            if ach["type"] == "messages":
                current = msgs
                display_current = f"{msgs} / {ach['target']}"
            elif ach["type"] == "voice":
                current = voice
                display_current = f"{round(voice/3600, 1)} / {round(ach['target']/3600, 1)} ч."
            elif ach["type"] == "level":
                current = level
                display_current = f"{level} / {ach['target']}"
            elif ach["type"] == "souls":
                current = souls
                display_current = f"{souls} / {ach['target']}"
            else:
                current, display_current = 0, "0"

            if is_earned:
                progress_text = f"`[{'▰' * 8}] 100%` • ✅ Выполнено!"
            else:
                progress_text = f"`{get_progress_bar(current, ach['target'])}` • {display_current}"

            status_icon = "🏅" if is_earned else "🔒"
            embed.add_field(
                name=f"{status_icon} **{ach['name']}**", 
                value=f"*{ach['desc']}*\n🎁 Награда: `{ach['reward_text']}`\nПрогресс: {progress_text}", 
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

class Achievements(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def check_achievements(self, member: discord.Member, channel: discord.TextChannel = None):
        if member.bot: return
        
        async with self.bot.db.execute("SELECT message_count, voice_time, level, total_souls_farmed FROM users WHERE id = ?", (member.id,)) as cursor:
            row = await cursor.fetchone()
        if not row: return
        msgs, voice, level, souls = row

        async with self.bot.db.execute("SELECT achievement_id FROM user_achievements WHERE user_id = ?", (member.id,)) as cursor:
            earned = [r[0] for r in await cursor.fetchall()]

        new_achievements = []
        reward_ap = 0
        reward_souls = 0
        awarded_roles = []

        for cat, achs in ACHIEVEMENTS.items():
            for ach in achs:
                if ach["id"] in earned: continue
                
                is_completed = False
                if ach["type"] == "messages" and msgs >= ach["target"]: is_completed = True
                elif ach["type"] == "voice" and voice >= ach["target"]: is_completed = True
                elif ach["type"] == "level" and level >= ach["target"]: is_completed = True
                elif ach["type"] == "souls" and souls >= ach["target"]: is_completed = True

                if is_completed:
                    new_achievements.append(ach)
                    if "reward_ap" in ach: reward_ap += ach["reward_ap"]
                    if "reward_souls" in ach: reward_souls += ach["reward_souls"]
                    
                    if "reward_role" in ach and ach["reward_role"] != 0:
                        role = member.guild.get_role(ach["reward_role"])
                        if role:
                            try:
                                await member.add_roles(role)
                                awarded_roles.append(role.mention)
                            except discord.Forbidden:
                                pass
                    
                    await self.bot.db.execute("INSERT INTO user_achievements (user_id, achievement_id) VALUES (?, ?)", (member.id, ach["id"]))
        
        if new_achievements:
            if reward_ap > 0 or reward_souls > 0:
                await self.bot.db.execute("""
                    UPDATE users SET 
                    activity_points = activity_points + ?, 
                    total_activity_points = total_activity_points + ?,
                    balance = balance + ?
                    WHERE id = ?
                """, (reward_ap, reward_ap, reward_souls, member.id))
            await self.bot.db.commit()

            if channel:
                for ach in new_achievements:
                    desc = f"Поздравляем! {member.mention} выполнил условие и открыл достижение:\n\n**{ach['name']}**\n*{ach['desc']}*\n\n🎁 Получена награда: `{ach['reward_text']}`"
                    if "reward_role" in ach and ach["reward_role"] != 0:
                        desc += f"\n👑 Вам выдана уникальная роль!"
                        
                    embed = discord.Embed(
                        title="🏆 ДОСТИЖЕНИЕ ПОЛУЧЕНО!",
                        description=desc,
                        color=discord.Color.brand_green()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
            
        query = """
            INSERT INTO users (id, balance, activity_points, total_activity_points, voice_time, message_count) 
            VALUES (?, 0, 0, 0, 0, 1) 
            ON CONFLICT(id) DO UPDATE SET 
            message_count = message_count + 1
        """
        await self.bot.db.execute(query, (message.author.id,))
        await self.bot.db.commit()

        await self.check_achievements(message.author, message.channel)

    @app_commands.command(name="achievements", description="🏆 Посмотреть свои достижения и прогресс")
    async def achievements_cmd(self, interaction: discord.Interaction):
        await interaction.response.send_message("Загрузка достижений...")
        view = AchievementUI(self.bot, interaction.user)
        embed = await view.generate_embed("activity")
        await interaction.edit_original_response(content=None, embed=embed, view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Achievements(bot))