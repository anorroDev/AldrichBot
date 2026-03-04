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
        
        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(name="Username", value=member.name, inline=True)
        embed.add_field(name="ID", value=f"`{member.id}`", inline=False)
        
        if member.is_timed_out():
            timeout_until = member.timed_out_until
            timestamp = int(timeout_until.timestamp())
            mute_value = f"🤐 **Да** (Снимется <t:{timestamp}:R>)\nТочное время: <t:{timestamp}:f>"
        else:
            mute_value = "✅ Нет"
            
        embed.add_field(name="Muted", value=mute_value, inline=False)

        joined_at = member.joined_at.strftime("%d.%m.%Y") if member.joined_at else "Unknown"
        embed.add_field(name="📅 Joined at", value=joined_at, inline=False)
        
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        roles_text = ", ".join(roles) if roles else "No roles"
        embed.add_field(name=f"🎭 Роли ({len(roles)})", value=roles_text, inline=False)

        embed.set_footer(
            text=f"Invoked by {interaction.user.display_name}", 
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.response.send_message(embed=embed)
    @userinfo.error
    async def userinfo_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        await interaction.response.send_message("Произошла ошибка при выполнении команды /userinfo. Убедитесь, что вы указали существующего пользователя.", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
