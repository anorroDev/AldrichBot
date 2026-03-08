import discord
from discord.ext import commands
import time

HUB_CHANNEL_ID = 1479945694608363621
CATEGORY_ID = 1446126355983896637

class RenameModal(discord.ui.Modal, title='Изменить название комнаты'):
    name_input = discord.ui.TextInput(
        label='Новое название',
        placeholder='Например: Фарм душ / Идем на босса',
        min_length=1,
        max_length=30
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if channel:
            await channel.edit(name=self.name_input.value)
            await interaction.response.send_message(f"✅ Название канала изменено на **{self.name_input.value}**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Вы не в голосовом канале!", ephemeral=True)

class LimitModal(discord.ui.Modal, title='Установить лимит участников'):
    limit_input = discord.ui.TextInput(
        label='Число от 0 до 99 (0 - без лимита)',
        placeholder='Например: 4',
        min_length=1,
        max_length=2
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(self.limit_input.value)
            if limit < 0 or limit > 99:
                raise ValueError
                
            channel = interaction.user.voice.channel if interaction.user.voice else None
            if channel:
                await channel.edit(user_limit=limit)
                text = f"установлен на **{limit}** человек(а)" if limit > 0 else "**снят** (безлимит)"
                await interaction.response.send_message(f"✅ Лимит {text}.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Вы не в голосовом канале!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Ошибка! Введите целое число от 0 до 99.", ephemeral=True)

class VoiceControlPanel(discord.ui.View):
    def __init__(self, owner_id: int, cog):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.cog = cog

    @discord.ui.button(label="Закрыть", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="vc_lock", row=0)
    async def btn_lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id: return await interaction.response.send_message("❌ Это не ваша комната!", ephemeral=True)
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel: return await interaction.response.send_message("❌ Вы должны находиться в голосовом канале!", ephemeral=True)

        await channel.set_permissions(interaction.guild.default_role, connect=False)
        await interaction.response.send_message("🔒 Канал закрыт от посторонних.", ephemeral=True)

    @discord.ui.button(label="Открыть", style=discord.ButtonStyle.success, emoji="🔓", custom_id="vc_unlock", row=0)
    async def btn_unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id: return await interaction.response.send_message("❌ Это не ваша комната!", ephemeral=True)
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel: return await interaction.response.send_message("❌ Вы должны находиться в голосовом канале!", ephemeral=True)

        await channel.set_permissions(interaction.guild.default_role, connect=True)
        await interaction.response.send_message("🔓 Канал открыт для всех.", ephemeral=True)

    @discord.ui.button(label="Изменить имя", style=discord.ButtonStyle.primary, emoji="✏️", custom_id="vc_rename", row=0)
    async def btn_rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id: return await interaction.response.send_message("❌ Это не ваша комната!", ephemeral=True)
        await interaction.response.send_modal(RenameModal())

    @discord.ui.button(label="Лимит мест", style=discord.ButtonStyle.secondary, emoji="👥", custom_id="vc_limit", row=0)
    async def btn_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id: return await interaction.response.send_message("❌ Это не ваша комната!", ephemeral=True)
        await interaction.response.send_modal(LimitModal())

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="✅ Кого пустить в канал?", min_values=1, max_values=1, row=1, custom_id="vc_allow")
    async def select_allow(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        if interaction.user.id != self.owner_id: return await interaction.response.send_message("❌ Это не ваша комната!", ephemeral=True)
        target_user = select.values[0]
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel: return await interaction.response.send_message("❌ Вы не в канале!", ephemeral=True)

        await channel.set_permissions(target_user, connect=True)
        await interaction.response.send_message(f"✅ {target_user.mention} получил доступ к комнату!", ephemeral=True)

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="⛔ Кого выгнать?", min_values=1, max_values=1, row=2, custom_id="vc_deny")
    async def select_deny(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        if interaction.user.id != self.owner_id: return await interaction.response.send_message("❌ Это не ваша комната!", ephemeral=True)
        target_user = select.values[0]
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel: return await interaction.response.send_message("❌ Вы не в канале!", ephemeral=True)
        if target_user.id == self.owner_id: return await interaction.response.send_message("❌ Нельзя выгнать себя!", ephemeral=True)

        await channel.set_permissions(target_user, connect=False)
        if target_user in channel.members: await target_user.move_to(None)
        await interaction.response.send_message(f"⛔ {target_user.mention} выгнан и заблокирован!", ephemeral=True)

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="👑 Кому передать права?", min_values=1, max_values=1, row=3, custom_id="vc_transfer")
    async def select_transfer(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        if interaction.user.id != self.owner_id: return await interaction.response.send_message("❌ Это не ваша комната!", ephemeral=True)
        new_owner = select.values[0]
        channel = interaction.user.voice.channel if interaction.user.voice else None
        
        if not channel: return await interaction.response.send_message("❌ Вы не в канале!", ephemeral=True)
        if new_owner.id == self.owner_id: return await interaction.response.send_message("❌ Вы и так владелец!", ephemeral=True)

        self.cog.temp_channels[channel.id] = new_owner.id
        self.owner_id = new_owner.id
        await interaction.response.send_message(f"👑 Права на комнату официально переданы {new_owner.mention}!", ephemeral=False)

class VoiceMaster(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.temp_channels = {}  
        self.voice_sessions = {} 

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot: return

        if after.channel and not before.channel:
            self.voice_sessions[member.id] = time.time()

        elif before.channel and not after.channel:
            if member.id in self.voice_sessions:
                start_time = self.voice_sessions.pop(member.id)
                duration = int(time.time() - start_time)

                if duration > 10: 
                    query = """
                        INSERT INTO users (id, balance, bank, activity_points, total_activity_points, voice_time) 
                        VALUES (?, 0, 0, 0, 0, ?) 
                        ON CONFLICT(id) DO UPDATE SET 
                        voice_time = voice_time + ?
                    """
                    await self.bot.db.execute(query, (member.id, duration, duration))
                    await self.bot.db.commit()

        if after.channel and after.channel.id == HUB_CHANNEL_ID:
            if not member.guild_permissions.set_voice_channel_status:
                await member.move_to(None)
                try:
                    await member.send("❌ **Доступ запрещен!**\nСоздавать приватные комнаты могут только пользователи с правом «Устанавливать статус голосового канала». Зарабатывайте достижения, чтобы получить доступ!")
                except discord.Forbidden:
                    pass
                return

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
                        description="Вы владелец этого канала!\nИспользуйте панель ниже для управления настройками.",
                        color=discord.Color.dark_purple()
                    )
                    await new_channel.send(f"{member.mention}", embed=embed, view=VoiceControlPanel(member.id, self))

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