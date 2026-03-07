import discord
from discord.ext import commands
import time

HUB_CHANNEL_ID = 1479945694608363621  
CATEGORY_ID = 1446126355983896637     


class VoiceControlPanel(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=None)
        self.owner_id = owner_id

    @discord.ui.button(label="Закрыть", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="vc_lock")
    async def btn_lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Только владелец комнаты может это делать!", ephemeral=True)
            
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel:
            return await interaction.response.send_message("❌ Вы должны находиться в голосовом канале!", ephemeral=True)

        await channel.set_permissions(interaction.guild.default_role, connect=False)
        await interaction.response.send_message("🔒 Канал закрыт. Теперь сюда нельзя зайти без приглашения.", ephemeral=True)

    @discord.ui.button(label="Открыть", style=discord.ButtonStyle.success, emoji="🔓", custom_id="vc_unlock")
    async def btn_unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Только владелец комнаты может это делать!", ephemeral=True)
            
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel:
            return await interaction.response.send_message("❌ Вы должны находиться в голосовом канале!", ephemeral=True)

        await channel.set_permissions(interaction.guild.default_role, connect=True)
        await interaction.response.send_message("🔓 Канал открыт для всех желающих!", ephemeral=True)



class VoiceMaster(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Словари для хранения временных данных в оперативной памяти
        self.temp_channels = {}  # {channel_id: owner_id} - список созданных рум
        self.voice_sessions = {} # {user_id: start_timestamp} - кто когда зашел в голос

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot: return 


        if after.channel and not before.channel:
            self.voice_sessions[member.id] = time.time()

        elif before.channel and not after.channel:
            if member.id in self.voice_sessions:
                start_time = self.voice_sessions.pop(member.id)
                duration = int(time.time() - start_time)

                if duration > 10: # Сохраняем только если просидел дольше 10 секунд (защита от спама)
                    query = """
                        INSERT INTO users (id, balance, bank, activity_points, total_activity_points, voice_time) 
                        VALUES (?, 0, 0, 0, 0, ?) 
                        ON CONFLICT(id) DO UPDATE SET 
                        voice_time = voice_time + ?
                    """
                    await self.bot.db.execute(query, (member.id, duration, duration))
                    await self.bot.db.commit()



        if after.channel and after.channel.id == HUB_CHANNEL_ID:
            guild = member.guild
            category = guild.get_channel(CATEGORY_ID)
            
            if category:
                new_channel = await guild.create_voice_channel(
                    name=f"Комната {member.display_name}", 
                    category=category,
                    bitrate=64000
                )
                
                try:
                    await member.move_to(new_channel)
                    self.temp_channels[new_channel.id] = member.id 
                    
                    embed = discord.Embed(
                        title=f"🎧 Приватная комната: {member.display_name}",
                        description="Вы владелец этого канала!\nИспользуйте кнопки ниже, чтобы открыть или закрыть доступ.",
                        color=discord.Color.dark_purple()
                    )
                    await new_channel.send(f"{member.mention}", embed=embed, view=VoiceControlPanel(member.id))

                except discord.HTTPException:
                    await new_channel.delete()

        if before.channel and before.channel.id in self.temp_channels:
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                    del self.temp_channels[before.channel.id]
                except:
                    pass

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceMaster(bot))