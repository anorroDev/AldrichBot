import discord
from discord.ext import commands, tasks
from discord import app_commands
import time
import random
import re


def parse_duration(duration_str: str):
    pattern = r"(\d+)([smhd])"
    match = re.match(pattern, duration_str.lower())
    if not match: 
        return None
    val, unit = int(match.group(1)), match.group(2)
    multiplier = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    return val * multiplier[unit]


class GiveawayView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Участвовать 🎉", style=discord.ButtonStyle.success, custom_id="gw_join")
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_id = interaction.message.id
        user_id = interaction.user.id
        
        async with self.bot.db.execute("SELECT is_active FROM giveaways WHERE message_id = ?", (msg_id,)) as cursor:
            row = await cursor.fetchone()
            
        if not row or not row[0]:
            return await interaction.response.send_message("❌ Этот розыгрыш уже завершен!", ephemeral=True)

        try:
            await self.bot.db.execute("INSERT INTO giveaway_participants (message_id, user_id) VALUES (?, ?)", (msg_id, user_id))
            await self.bot.db.commit()
            await interaction.response.send_message("✅ Вы успешно стали участником розыгрыша! Желаем удачи!", ephemeral=True)
            
        except Exception: 
            await self.bot.db.execute("DELETE FROM giveaway_participants WHERE message_id = ? AND user_id = ?", (msg_id, user_id))
            await self.bot.db.commit()
            await interaction.response.send_message("🚪 Вы забрали свой билет и покинули розыгрыш.", ephemeral=True)


class Giveaway(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.check_giveaways.start()
        
    async def cog_load(self):
        await self.bot.db.execute("CREATE TABLE IF NOT EXISTS giveaways (message_id INTEGER PRIMARY KEY, channel_id INTEGER, end_time INTEGER, prize TEXT, winners_count INTEGER, is_active INTEGER)")
        await self.bot.db.execute("CREATE TABLE IF NOT EXISTS giveaway_participants (message_id INTEGER, user_id INTEGER, UNIQUE(message_id, user_id))")
        await self.bot.db.commit()
        
        self.bot.add_view(GiveawayView(self.bot))

    def cog_unload(self):
        self.check_giveaways.cancel()

    @app_commands.command(name="giveaway", description="🎁 Создать розыгрыш")
    @app_commands.describe(duration="Время (например: 10m, 2h, 1d)", winners="Количество победителей", prize="Что разыгрываем?")
    @app_commands.checks.has_permissions(administrator=True) 
    async def start_gw(self, interaction: discord.Interaction, duration: str, winners: int, prize: str):
        seconds = parse_duration(duration)
        if not seconds: 
            return await interaction.response.send_message("❌ Неверный формат времени! Используйте `10m` (минуты), `2h` (часы), `1d` (дни).", ephemeral=True)
        if winners < 1: 
            return await interaction.response.send_message("❌ Должен быть хотя бы 1 победитель.", ephemeral=True)

        end_time = int(time.time()) + seconds
        
        embed = discord.Embed(
            title="🎁 РОЗЫГРЫШ! 🎁", 
            description=f"**Приз:** {prize}\n**Победителей:** {winners}\n**Итоги:** <t:{end_time}:R> (<t:{end_time}:f>)\n\nЖми кнопку ниже, чтобы забрать билет!", 
            color=discord.Color.gold()
        )
        embed.set_footer(text="Удачи всем участникам!")
        
        await interaction.response.send_message("✅ Розыгрыш успешно запущен!", ephemeral=True)
        
        msg = await interaction.channel.send(embed=embed, view=GiveawayView(self.bot))
        
        await self.bot.db.execute("INSERT INTO giveaways (message_id, channel_id, end_time, prize, winners_count, is_active) VALUES (?, ?, ?, ?, ?, 1)", (msg.id, interaction.channel.id, end_time, prize, winners))
        await self.bot.db.commit()


    @tasks.loop(seconds=15) 
    async def check_giveaways(self):
        if not self.bot.is_ready(): return
        
        current_time = int(time.time())
        async with self.bot.db.execute("SELECT message_id, channel_id, prize, winners_count FROM giveaways WHERE is_active = 1 AND end_time <= ?", (current_time,)) as cursor:
            rows = await cursor.fetchall()

        for row in rows:
            msg_id, channel_id, prize, winners_count = row
            
            await self.bot.db.execute("UPDATE giveaways SET is_active = 0 WHERE message_id = ?", (msg_id,))
            await self.bot.db.commit()

            async with self.bot.db.execute("SELECT user_id FROM giveaway_participants WHERE message_id = ?", (msg_id,)) as p_cursor:
                participants = [r[0] for r in await p_cursor.fetchall()]

            channel = self.bot.get_channel(channel_id)
            if not channel: continue

            try:
                msg = await channel.fetch_message(msg_id)
                embed = msg.embeds[0]
                embed.title = "🎊 РОЗЫГРЫШ ЗАВЕРШЕН 🎊"
                embed.description = f"**Приз:** {prize}\nУчастников было: `{len(participants)}`"
                embed.color = discord.Color.dark_gray()
                await msg.edit(embed=embed, view=None) 
            except: 
                pass

            if not participants:
                await channel.send(f"⚠️ Розыгрыш на **{prize}** завершен, но никто не принял участие..")
                continue

            actual_winners_count = min(winners_count, len(participants))
            winners = random.sample(participants, actual_winners_count)
            winners_mentions = ", ".join(f"<@{w}>" for w in winners)

            await channel.send(f"🎉 Поздравляем {winners_mentions}! Вы выиграли: **{prize}**! Ожидайте, с вами свяжется администрация.")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Giveaway(bot))