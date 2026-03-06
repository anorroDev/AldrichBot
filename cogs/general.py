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

    # @app_commands.command(name="userinfo", description="Узнать информацию о пользователе")
    # @app_commands.describe(member="Choose a member to get information about")
    # async def userinfo(self, interaction: discord.Interaction, member: discord.Member) -> None:

    #     embed = discord.Embed(
    #         title="User Information", 
    #         color=discord.Color.blue(), 
    #         timestamp=interaction.created_at
    #     )
        
    #     embed.set_thumbnail(url=member.display_avatar.url)

    #     embed.add_field(name="Username", value=member.name, inline=True)
    #     embed.add_field(name="ID", value=f"`{member.id}`", inline=False)
        
    #     try:
    #         async with self.bot.db.execute("SELECT activity_points, total_activity_points FROM users WHERE id = ?", (member.id,)) as cursor:
    #             row = await cursor.fetchone()
                
    #         current_ap = row[0] if row and row[0] else 0
    #         total_ap = row[1] if row and row[1] else 0
            
    #         ap_text = f"Текущий баланс: `{current_ap}`\nЗа всё время: `{total_ap}`"
    #         embed.add_field(name="🏆 Очки Активности", value=ap_text, inline=False)
            
    #     except Exception as e:
    #         print(f"Ошибка БД в userinfo: {e}")
    #         embed.add_field(name="🏆 Очки Активности", value="Данные недоступны", inline=False)
    #     if member.is_timed_out():
    #         timeout_until = member.timed_out_until
    #         timestamp = int(timeout_until.timestamp())
    #         mute_value = f"🤐 **Да** (Снимется <t:{timestamp}:R>)\nТочное время: <t:{timestamp}:f>"
    #     else:
    #         mute_value = "✅ Нет"
            
    #     embed.add_field(name="Muted", value=mute_value, inline=False)

    #     joined_at = member.joined_at.strftime("%d.%m.%Y") if member.joined_at else "Unknown"
    #     embed.add_field(name="📅 Joined at", value=joined_at, inline=False)
        
    #     roles = [role.mention for role in member.roles if role.name != "@everyone"]
    #     roles_text = ", ".join(roles) if roles else "No roles"
    #     embed.add_field(name=f"🎭 Роли ({len(roles)})", value=roles_text, inline=False)

    #     embed.set_footer(
    #         text=f"Invoked by {interaction.user.display_name}", 
    #         icon_url=interaction.user.display_avatar.url
    #     )

    #     await interaction.response.send_message(embed=embed)

    # @userinfo.error
    # async def userinfo_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    #     await interaction.response.send_message("Произошла ошибка при выполнении команды /userinfo. Убедитесь, что вы указали существующего пользователя.", ephemeral=True)
    
    # @app_commands.command(name="top_activity", description="🏆 Посмотреть топ-10 самых активных участников сервера за всё время")
    # async def top_activity(self, interaction: discord.Interaction) -> None:
        
    #     # Запрашиваем из базы 10 человек и сортируем по ИСТОРИЧЕСКИМ очкам (total_activity_points)
    #     async with self.bot.db.execute("SELECT id, total_activity_points FROM users WHERE total_activity_points > 0 ORDER BY total_activity_points DESC LIMIT 10") as cursor:
    #         rows = await cursor.fetchall()

    #     if not rows:
    #         await interaction.response.send_message("📭 Пока никто на сервере не заработал Очков Активности.", ephemeral=True)
    #         return

    #     embed = discord.Embed(title="🏆 Зал Славы: Самые активные участники", color=discord.Color.gold())
        
    #     description = ""
    #     for index, row in enumerate(rows, start=1):
    #         user_id = row[0]
    #         points = row[1]
            
    #         medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else "🏅"
    #         description += f"{medal} **{index}.** <@{user_id}> — Заработано всего: `{points}` АП\n"

    #     embed.description = description
    #     embed.set_footer(text="Будьте активней, чтобы попасть сюда!")
        
    #     await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="userinfo", description="Узнать информацию о пользователе")
    @app_commands.describe(member="Выберите пользователя")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member) -> None:

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

        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        roles_text = ", ".join(roles) if roles else "No roles"
        embed.add_field(name=f"🎭 Роли ({len(roles)})", value=roles_text, inline=False)

        embed.set_footer(
            text=f"Invoked by {interaction.user.display_name}", 
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.response.send_message(embed=embed)
        
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))