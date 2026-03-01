import discord
from discord.ext import commands
from discord import app_commands


class RoleSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label="Role 1", value="1477601614171738193"), 
            discord.SelectOption(label="Role 2", value="1477601755347816639"),
            discord.SelectOption(label="Role 3", value="1477601777586143242")
        ]
        super().__init__(placeholder="Выбери свою роль", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        
        if role:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"✅ Тебе успешно выдана роль **{role.name}**!", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ Упс! У меня нет прав выдавать эту роль. Проверь настройки сервера!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ошибка: такая роль не найдена на сервере.", ephemeral=True)
    
class OptionView(discord.ui.View):
    def __init__(self) -> None: 
        super().__init__(timeout=None)
        self.add_item(RoleSelect())


class UIElements(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None: 
        self.bot = bot

    @app_commands.command(name="menu", description="Показать меню выбора ролей")
    async def menu(self, interaction: discord.Interaction) -> None:
        view = OptionView()
        await interaction.response.send_message("Выбери роль из меню ниже:", view=view, ephemeral=True)

    @menu.error
    async def menu_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        await interaction.response.send_message(f"❌ Произошла ошибка: {error}", ephemeral=True)

        
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UIElements(bot))