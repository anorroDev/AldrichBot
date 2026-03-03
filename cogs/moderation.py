import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta


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
        await interaction.response.send_message(f"🔇 Пользователь **{member.display_name}** был заглушен. Причина: `{reason}`")

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
        await interaction.response.send_message(f"🔨 Пользователь **{member.display_name}** был забанен. Причина: `{reason}`")
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