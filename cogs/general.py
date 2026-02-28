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

        embed = discord.Embed(
            title="User Information", 
            color=discord.Color.blue(), 
            timestamp=interaction.created_at
            )
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)

        embed.add_field(name="Username", value=member.name, inline=True)
        embed.add_field(name="ID", value=member.id, inline=False)
        embed.add_field(name="Muted", value="Yes" if member.is_timed_out() else "No", inline=False)

        joined_at = member.joined_at.strftime("%d.%m.%Y") if member.joined_at else "Unknown"
        embed.add_field(name="📅 Joined at", value=joined_at, inline=False)
        
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        roles_text = ", ".join(roles) if roles else "No roles"
        embed.add_field(name=f"🎭 Роли ({len(roles)})", value=roles_text, inline=False)

        embed.set_footer(text=f"invoked by {interaction.user.mention}", icon_url=interaction.user.avatar.url)

        await interaction.response.send_message(embed=embed)
    
    @userinfo.error
    async def userinfo_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        await interaction.response.send_message("Произошла ошибка при выполнении команды /userinfo. Убедитесь, что вы указали существующего пользователя.", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
