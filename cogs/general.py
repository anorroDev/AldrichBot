import discord
from discord.ext import commands
from discord import app_commands


class General(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Посмотреть задержку бота.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Пинг: {latency}ms")

    @ping.error
    async def ping_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        await interaction.response.send_message("Произошла ошибка при выполнении команды /ping.", ephemeral=True)

    @app_commands.command(name="userinfo", description="Узнать информацию о пользователе")
    @app_commands.describe(member="Choose a member to get information about")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member) -> None:
        joined_at = member.joined_at.strftime("%d.%m.%Y") if member.joined_at else "Unknown"
        roles = [role.name for role in member.roles if role.name != "@everyone"]

        reply_text = (
            f"👤 **Пользователь:** {member.mention}\n"
            f"🆔 **ID:** {member.id}\n"
            f"📅 **Присоединился к серверу:** {joined_at}\n"
            f"🎭 **Ролей:** {len(roles)}"
        )

        await interaction.response.send_message(reply_text)
    
    @userinfo.error
    async def userinfo_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        await interaction.response.send_message("Произошла ошибка при выполнении команды /userinfo. Убедитесь, что вы указали существующего пользователя.", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
