import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
import random

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    #clear command
    @app_commands.command(name="clear", description="Очистить определённое количество сообщений в канале.")
    @app_commands.describe(amount="Количество сообщений для удаления (до 100).")
    @app_commands.checks.has_permissions(manage_messages=True)
    
    async def clear(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]) -> None:

        await interaction.response.defer(ephemeral=True)
        deleted =await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 Удалено {amount} сообщений.", ephemeral=True)

    #mute command
    @app_commands.command(name="mute", description="Заглушить участника на сервере.")
    @app_commands.describe(member="Участник, которого нужно заглушить.", minutes="Количество минут, на которое нужно заглушить участника.", reason="Причина заглушения.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "Причина не указана") -> None:
        
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("Вы не можете заглушить этого участника, так как его роль выше или равна вашей.", ephemeral=True)
            return
        duration = timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await interaction.response.send_message(f"🔇 Пользователь **{member.display_name}** был заглушен на {minutes} минут. Причина: `{reason}`")

    @app_commands.command(name="unmute", description="[МОД] Досрочно снять мут (таймаут) с пользователя")
    @app_commands.describe(member="Кого размутить?", reason="Причина амнистии")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Причина не указана") -> None:
        
        if not member.is_timed_out():
            await interaction.response.send_message(f"❌ Пользователь **{member.display_name}** и так может говорить! На нём нет мута.", ephemeral=True)
            return

        await member.timeout(None, reason=reason)
        await interaction.response.send_message(f"🔊 Пользователь **{member.display_name}** досрочно освобожден от мута. Причина: `{reason}`")    

    #kick command
    @app_commands.command(name="kick", description="Кикнуть участника с сервера.")
    @app_commands.describe(member="Участник, которого нужно кикнуть.", reason="Причина кика.")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Причина не указана" ) -> None:

        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("Вы не можете кикнуть этого участника, так как его роль выше или равна вашей.", ephemeral=True)
            return

        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 Пользователь **{member.display_name}** был изгнан. Причина: `{reason}`")

    #ban command
    @app_commands.command(name="ban", description="Забанить участника на сервере.")
    @app_commands.describe(member="Участник, которого нужно забанить.", reason="Причина бана.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Причина не указана") -> None:

        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("Вы не можете забанить этого участника, так как его роль выше или равна вашей.", ephemeral=True)
            return

        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 Пользователь **{member.display_name}** был забанен на. Причина: `{reason}`")

    @app_commands.command(name="unban", description=" Снять блокировку (бан) с пользователя")
    @app_commands.describe(user="Пользователь (Выбери из списка или введи его ID)", reason="Причина разбана")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user: discord.User, reason: str = "Причина не указана") -> None:
        
        try:
            await interaction.guild.unban(user, reason=reason)
            await interaction.response.send_message(f"🕊️ Пользователь **{user.name}** был помилован и разбанен. Причина: `{reason}`")
        
        except discord.NotFound:
            await interaction.response.send_message(f"❌ Пользователь **{user.name}** не найден в бан-листе этого сервера!", ephemeral=True)
    
    @app_commands.command(name="roulette", description="Испытать удачу нарушителя... случайным наказанием!")
    @app_commands.describe(member="Кого будем пытать удачей?")
    @app_commands.checks.has_permissions(ban_members=True)
    async def roulette(self, interaction: discord.Interaction, member: discord.Member) -> None:
        
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ Нельзя целиться в того, кто равен или выше тебя по званию!", ephemeral=True)
            return
            
        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("❌ Моя роль ниже, чем у этой жертвы. Я не смогу выдать наказание.", ephemeral=True)
            return
            
        if member.bot:
            await interaction.response.send_message("❌ Бездушные машины не играют в такие игры.", ephemeral=True)
            return

        await interaction.response.defer()

        chance = random.randint(1, 100)
        admin_name = interaction.user.display_name

        if chance == 1:
            try:
                await member.send(f"💥Администратор {admin_name} сыграл с тобой в рулетку. Тебе выпал БАН")
            except:
                pass
            await member.ban(reason=f"Рулетка от админа {admin_name} (1% шанс)")
            await interaction.followup.send(f"💥 {member.mention} выбил 1% шанс и улетел в **БАН** Покойся с миром. ☠️")

        elif chance <= 6:
            try:
                await member.send(f"👢 Администратор {admin_name} выбил тебе кик в рулетке.")
            except:
                pass
            await member.kick(reason=f"Рулетка от админа {admin_name} (5% шанс)")
            await interaction.followup.send(f"👢 {member.mention} получает кик (5% шанс)")

        elif chance <= 26:
            duration = timedelta(hours=1)
            await member.timeout(duration, reason=f"Рулетка от админа {admin_name}")
            await interaction.followup.send(f"🤫 {member.mention} получает **мут на 1 час** (20% шанс).")

        elif chance <= 56:
            duration = timedelta(minutes=5)
            await member.timeout(duration, reason=f"Рулетка от админа {admin_name}")
            await interaction.followup.send(f"😵 {member.mention} отправляется в **мут на 5 минут** (30% шанс).")

        else:
            await interaction.followup.send(f"😅 {member.mention} сегодня везунчик! Никакого наказания (44% шанс). 🍀")

    #error handler for all commands in this cog
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ У вас недостаточно прав для использования этой команды!", ephemeral=True)
        elif isinstance(error, app_commands.BotMissingPermissions):
            await interaction.response.send_message("❌ У меня (бота) нет прав, чтобы сделать это! Проверьте мою роль.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Произошла ошибка: {error}", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))