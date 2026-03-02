import discord
from discord.ext import commands
from discord import app_commands


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

    @clear.error
    async def clear_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("У вас нет прав для использования этой команды.", ephemeral=True)
        elif isinstance(error, app_commands.CommandInvokeError):
            await interaction.response.send_message("Произошла ошибка при выполнении команды /clear. Убедитесь, что бот имеет права на удаление сообщений.", ephemeral=True)
        else:
            await interaction.response.send_message("Произошла неизвестная ошибка при выполнении команды /clear.", ephemeral=True)

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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))