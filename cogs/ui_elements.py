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
        super().__init__(placeholder="Выбери свою роль", min_values=1, max_values=1, options=options, custom_id="role_select_menu")

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


class VerifyView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label='Подтвердить', style=discord.ButtonStyle.success, emoji="✅", custom_id='verify_btn') 
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        role_id = 1477632896431947866
        role = interaction.guild.get_role(role_id)

        if not role:
            await interaction.response.send_message("❌ Ошибка: роль для верификации не найдена на сервере. Обратитесь к администратору.", ephemeral=True)
            return
        if role in interaction.user.roles:
            await interaction.response.send_message("⚠️ Вы уже прошли верификацию!", ephemeral=True)
        else:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("✅ Верификация успешна! Вам была выдана роль.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ Упс! У меня нет прав выдавать эту роль. Проверь настройки сервера!", ephemeral=True)


class UIElements(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None: 
        self.bot = bot
        self.bot.add_view(OptionView())
        self.bot.add_view(VerifyView())

    @app_commands.command(name="menu", description="Показать меню выбора ролей")
    async def menu(self, interaction: discord.Interaction) -> None:
        view = OptionView()
        await interaction.response.send_message("Выбери роль из меню ниже:", view=view, ephemeral=True)

    @menu.error
    async def menu_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        await interaction.response.send_message(f"❌ Произошла ошибка: {error}", ephemeral=True)

    @app_commands.command(name="verify", description="Показать кнопку для верификации")
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
    await bot.add_cog(UIElements(bot))