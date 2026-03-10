import discord
from discord.ext import commands
from discord import app_commands

ACHIEVEMENTS = {
    "activity": [
        {"id": "msg_100", "name": "Новичок ", "desc": "Напишите 100 сообщений в чатах.", "target": 100, "type": "messages", "reward_text": "50 АП", "reward_ap": 50},
        {"id": "msg_1000", "name": "Легенда чата", "desc": "Напишите 1000 сообщений.", "target": 1000, "type": "messages", "reward_text": "500 АП", "reward_ap": 300},
        {"id": "voice_100", "name": "Душа компании", "desc": "Проведите 100 часов в голосовых каналах.", "target": 36000, "type": "voice", "reward_text": "500 АП", "reward_ap": 500}
    ],
    "game": [
        {"id": "lvl_10", "name": "Закаленный в боях", "desc": "Достигните 10 уровня у костра.", "target": 10, "type": "level", "reward_text": "100 АП", "reward_ap": 100},
        {"id": "souls_10000", "name": "Лорд Пепла", "desc": "Накопите 10 000 душ.", "target": 10000, "type": "souls", "reward_text": "250 АП", "reward_ap": 100}
    ]
}

class VerifyView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label='Подтвердить', style=discord.ButtonStyle.success, emoji="✅", custom_id='verify_btn') 
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        role_id = 1477632896431947866
        role = interaction.guild.get_role(role_id)

        if not role:
            await interaction.response.send_message("❌ Ошибка: роль для верификации не найдена на сервере.", ephemeral=True)
            return
            
        if role in interaction.user.roles:
            await interaction.response.send_message("⚠️ Вы уже прошли верификацию!", ephemeral=True)
        else:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("✅ Верификация успешна! Вам была выдана роль.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ Упс! У меня нет прав выдавать эту роль. Моя роль должна быть выше выдаваемой!", ephemeral=True)


class General(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.bot.add_view(VerifyView())

    @app_commands.command(name="ping", description="Посмотреть задержку бота.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Пинг: {latency}ms")

    @ping.error
    async def ping_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        await interaction.response.send_message("Произошла ошибка при выполнении команды /ping.", ephemeral=True)

    @app_commands.command(name="userinfo", description="Узнать информацию о пользователе")
    @app_commands.describe(member="Выберите пользователя (оставьте пустым для себя)")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member | None = None) -> None:

        if member is None:
            member = interaction.user

        embed = discord.Embed(
            title="👤 User Information", 
            color=discord.Color.blue(), 
            timestamp=interaction.created_at
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        # 1. Username
        embed.add_field(name="Username", value=member.name, inline=True)
        # 2. ID
        embed.add_field(name="ID", value=f"`{member.id}`", inline=False)
        
        # 3. Дата
        joined_at = member.joined_at.strftime("%d.%m.%Y") if member.joined_at else "Unknown"
        embed.add_field(name="📅 Joined at", value=joined_at, inline=False)

        # 4. Мут
        if member.is_timed_out():
            timeout_until = member.timed_out_until
            timestamp = int(timeout_until.timestamp())
            mute_value = f"🤐 **Да** (Снимется <t:{timestamp}:R>)\nТочное время: <t:{timestamp}:f>"
        else:
            mute_value = "✅ Нет"
        embed.add_field(name="Muted", value=mute_value, inline=False)

        # 5. Очки Активности
        try:
            async with self.bot.db.execute("SELECT activity_points, total_activity_points FROM users WHERE id = ?", (member.id,)) as cursor:
                row = await cursor.fetchone()
                
            current_ap = row[0] if row and row[0] else 0
            total_ap = row[1] if row and row[1] else 0
            ap_text = f"Текущий баланс: `{current_ap}`\nЗа всё время: `{total_ap}`"
            
        except Exception as e:
            print(f"Ошибка БД в userinfo: {e}")
            ap_text = "Данные недоступны"
            
        embed.add_field(
            name="▬▬▬▬▬▬▬▬▬▬\n🏆 Очки Активности", 
            value=ap_text, 
            inline=False
        )

        # 6. Игровой профиль
        try:
            async with self.bot.db.execute("SELECT char_name, level FROM users WHERE id = ?", (member.id,)) as cursor:
                prof = await cursor.fetchone()
            if prof and prof[0]:
                char_name = prof[0]
                char_level = prof[1] if prof[1] else 1
                embed.add_field(
                    name="🎮 Персонаж",
                    value=f"**{char_name}** — lvl: `{char_level}`",
                    inline=False
                )
            else:
                embed.add_field(name="🎮 Персонаж", value="Нет персонажа", inline=False)
        except Exception as e:
            print(f"Ошибка БД в userinfo (профиль): {e}")
            embed.add_field(name="🎮 Персонаж", value="Данные недоступны", inline=False)

        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        roles_text = ", ".join(roles) if roles else "No roles"
        embed.add_field(name=f"🎭 Роли ({len(roles)})", value=roles_text, inline=False)

        embed.set_footer(
            text=f"Invoked by {interaction.user.display_name}", 
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="verify", description="Показать сообщение с кнопкой верификации")
    @app_commands.checks.has_permissions(administrator=True)
    async def verify(self, interaction: discord.Interaction) -> None:
        view = VerifyView()
        text = "Нажмите кнопку ниже, чтобы пройти верификацию и получить доступ к остальным каналам сервера."
        await interaction.response.send_message(text, view=view)

    @verify.error
    async def verify_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Эта команда доступна только администраторам!", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Произошла ошибка: {error}", ephemeral=True)    

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))