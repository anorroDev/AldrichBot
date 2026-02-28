import discord
from discord.ext import commands
from discord import app_commands


class UIElements(commands.Cog):
    def __init__(self, bot: commands.bot) -> None:
        self.bot = bot

    options = [
        discord.SelectOption(label="Option 1", description="This is the first option.", emoji="1️⃣", value="option1"),
        discord.SelectOption(label="Option 2", description="This is the second option.", emoji="2️⃣", value="option2"),
        discord.SelectOption(label="Option 3", description="This is the third option.", emoji="3️⃣", value="option3"),
    ]

    super().__init__(placeholder="Choose an option...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:

        chosen_option = self.values[0]
        
        await interaction.response.send_message(f"You selected: {chosen_option}", ephemeral=True)