import discord
from discord.ext import commands, tasks
from discord import app_commands
import time
import random
import re
import asyncio
from datetime import datetime, timedelta, timezone


VERIFY_ROLE_ID = 1477632896431947866


def parse_duration(duration_str: str):
    pattern = r"(\d+)([smhd])"
    match = re.match(pattern, duration_str.lower())
    if not match:
        return None
    val, unit = int(match.group(1)), match.group(2)
    multiplier = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    return val * multiplier[unit]


class GiveawayView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Участвовать 🎉", style=discord.ButtonStyle.success, custom_id="gw_join")
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_id = interaction.message.id
        user_id = interaction.user.id

        async with self.bot.db.execute("SELECT is_active FROM giveaways WHERE message_id = ?", (msg_id,)) as cursor:
            row = await cursor.fetchone()

        if not row or not row[0]:
            return await interaction.response.send_message("❌ Этот розыгрыш уже завершен!", ephemeral=True)

        try:
            await self.bot.db.execute(
                "INSERT INTO giveaway_participants (message_id, user_id) VALUES (?, ?)",
                (msg_id, user_id)
            )
            await self.bot.db.commit()
            await interaction.response.send_message("✅ Вы успешно стали участником розыгрыша! Желаем удачи!", ephemeral=True)
        except Exception:
            await self.bot.db.execute(
                "DELETE FROM giveaway_participants WHERE message_id = ? AND user_id = ?",
                (msg_id, user_id)
            )
            await self.bot.db.commit()
            await interaction.response.send_message("🚪 Вы забрали свой билет и покинули розыгрыш.", ephemeral=True)


class VerifyView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label='Подтвердить', style=discord.ButtonStyle.success, emoji="✅", custom_id='verify_btn')
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        role = interaction.guild.get_role(VERIFY_ROLE_ID)

        if not role:
            await interaction.response.send_message("❌ Ошибка: роль для верификации не найдена на сервере.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("⚠️ Вы уже прошли верификацию!", ephemeral=True)
        else:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("✅ Верификация успешна! Вам была выдана роль.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ Упс! У меня нет прав выдавать эту роль. Моя роль должна быть выше выдаваемой!",
                    ephemeral=True
                )


class HelpView(discord.ui.View):
    def __init__(self, pages: dict, owner_id: int):
        super().__init__(timeout=300)
        self.pages = pages
        self.owner_id = owner_id
        self.current = "general"
        self._rebuild_buttons()

    def _rebuild_buttons(self):
        for item in list(self.children):
            self.remove_item(item)
        for key, data in self.pages.items():
            style = discord.ButtonStyle.primary if key == self.current else discord.ButtonStyle.secondary
            btn = discord.ui.Button(label=data["label"], style=style, custom_id=f"help_{key}")
            btn.callback = self._make_callback(key)
            self.add_item(btn)

    def _make_callback(self, key: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.owner_id:
                return await interaction.response.send_message("❌ Откройте `/help` для себя.", ephemeral=True)
            self.current = key
            self._rebuild_buttons()
            await interaction.response.edit_message(embed=self.build_embed(key), view=self)
        return callback

    def build_embed(self, key: str) -> discord.Embed:
        page = self.pages[key]
        embed = discord.Embed(
            title=page["title"],
            description="▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
            color=page["color"],
        )
        for name, value in page["fields"]:
            embed.add_field(name=name, value=value, inline=False)
        embed.set_footer(text="Все команды являются слэш-командами (/). Нажмите кнопку ниже для смены категории.")
        return embed

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


class General(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self):
        # Создаём таблицы для розыгрышей
        await self.bot.db.execute(
            "CREATE TABLE IF NOT EXISTS giveaways "
            "(message_id INTEGER PRIMARY KEY, channel_id INTEGER, end_time INTEGER, "
            "prize TEXT, winners_count INTEGER, is_active INTEGER)"
        )
        await self.bot.db.execute(
            "CREATE TABLE IF NOT EXISTS giveaway_participants "
            "(message_id INTEGER, user_id INTEGER, UNIQUE(message_id, user_id))"
        )
        await self.bot.db.commit()

        # Восстанавливаем persistent views
        self.bot.add_view(GiveawayView(self.bot))
        self.bot.add_view(VerifyView())

        # Запускаем таск
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()


    # ─────────────────────────────────────────────────────────────────────────────
    #                              /help  command
    # ─────────────────────────────────────────────────────────────────────────────

    HELP_PAGES = {
        "general": {
            "label": "🔧 Общие",
            "color": discord.Color.blurple(),
            "title": "🔧 Общие команды",
            "fields": [
                ("/ping", "Показать задержку бота."),
                ("/userinfo [участник]", "Информация о пользователе: роли, уровень, очки активности, персонаж."),
                ("/avatar [участник]", "Показать аватар пользователя."),
                ("/serverinfo", "Статистика сервера: участники, каналы, роли, буст."),
                ("/afk [причина]", "Установить AFK-статус. Снимается автоматически при сообщении."),
                ("/remind <время> <текст>", "Напоминание в чат. Формат времени: `10m`, `2h`, `1d`."),
                ("/alarm <ЧЧ:ММ> <текст> [дата] [UTC]", "Будильник на точное время дня."),
                ("/roll [макс]", "Бросить кубик (случайное число от 1 до макс)."),
                ("/flip", "Подкинуть монетку — Орел или Решка."),
            ],
        },
        "moderation": {
            "label": "🛡️ Модерация",
            "color": discord.Color.red(),
            "title": "🛡️ Команды модерации",
            "fields": [
                ("/clear <кол-во>", "Удалить от 1 до 100 сообщений в канале. `Права: Manage Messages`"),
                ("/mute <участник> <минуты> [причина]", "Выдать таймаут участнику. `Права: Moderate Members`"),
                ("/unmute <участник> [причина]", "Досрочно снять таймаут. `Права: Moderate Members`"),
                ("/kick <участник> [причина]", "Кикнуть участника с сервера. `Права: Kick Members`"),
                ("/ban <участник> [причина]", "Забанить участника. `Права: Ban Members`"),
                ("/unban <пользователь> [причина]", "Снять бан. `Права: Ban Members`"),
                ("/roulette <участник>", "Случайное наказание: 1% бан, 5% кик, 20% мут на час, 30% мут 5 мин, 44% ничего. `Права: Ban Members`"),
            ],
        },
        "activity": {
            "label": "📊 Активность",
            "color": discord.Color.gold(),
            "title": "📊 Активность и Магазин",
            "fields": [
                ("/leaderboard", "Доска почёта — Топ-5 по уровню и по текущим очкам активности."),
                ("/shop", "Открыть магазин АП: косметика, игровые предметы, особые предметы."),
                ("/achievements", "Ваши достижения и прогресс по трём категориям: Активность, Игра, Секретные."),
                ("Как зарабатываются АП?", "За каждое сообщение в чате **+1 АП**.\nЗа время в голосовых каналах **+1 АП / 5 мин**.\nЗа выполнение достижений — крупные бонусы."),
            ],
        },
        "game": {
            "label": "⚔️ Игра",
            "color": discord.Color.dark_red(),
            "title": "⚔️ RPG-система «Охота за Душами»",
            "fields": [
                ("/game", "Открыть главное игровое меню. Здесь можно охотиться за душами, улучшаться у костра, открыть Лавку и посетить торговца."),
                ("/profile [участник]", "Карточка персонажа: уровень, души, энергия, характеристики, экипировка."),
                ("/inventory", "Инвентарь и менеджер экипировки."),
                ("Локации (разблокируются по охотам):", "🪦 Кладбище → 🌲 Проклятый лес (10 охот)\n💀 Катакомбы (25) → 🏰 Заброшенный замок (45)\n🌋 Пик Дракона (70) → 🌌 Бездна (100)"),
                ("Предметы:", "💍 Кольцо Жертвенности — спасает от смерти (одноразовое)\n💛 Кольцо Жадности — +20% душ на охоте (пассивное)\n🔵 Кольцо Стремительности — −5% шанс смерти\n🧪 Фляга Бодрости — восстанавливает 5 ⚡\n📜 Свиток Ярости — следующая охота ×2 душ"),
                ("Характеристики:", "💪 **Сила** — больше душ с охоты\n❤️ **Живучесть** — меньше шанс смерти\n🍀 **Удача** — больше шанс выжить и найти бонус"),
            ],
        },
        "voice": {
            "label": "🔊 Войс",
            "color": discord.Color.teal(),
            "title": "🔊 Приватные голосовые комнаты",
            "fields": [
                ("Как создать комнату?", "Зайдите в канал-хаб **«Создать комнату»** — бот автоматически создаст вашу личную комнату и отправит панель управления."),
                ("🔒 Закрыть / 🔓 Открыть", "Ограничить или разрешить вход для всех участников сервера."),
                ("✏️ Изменить имя", "Переименовать свою голосовую комнату."),
                ("👥 Лимит мест", "Установить максимальное число участников (0 = без лимита)."),
                ("✅ Пустить в канал", "Выдать конкретному участнику доступ к закрытой комнате."),
                ("⛔ Выгнать", "Запретить конкретному участнику заходить в вашу комнату."),
                ("Жизнь комнаты", "Комната удаляется автоматически, когда все участники её покидают."),
            ],
        },
        "admin": {
            "label": "👑 Админ",
            "color": discord.Color.dark_orange(),
            "title": "👑 Административные команды",
            "fields": [
                ("/verify", "Отправить в канал сообщение с кнопкой верификации. `Только администраторы`"),
                ("/giveaway <время> <победителей> <приз>", "Запустить розыгрыш с кнопкой участия. `Только администраторы`"),
                ("/change_balance <set/add/remove> <участник> <сумма>", "Изменить баланс **душ** игрока. `Только администраторы`"),
                ("/give_activity <участник> <кол-во>", "Начислить **Очки Активности** пользователю. `Только администраторы`"),
                ("/give_item <участник> <предмет> <кол-во>", "Выдать предмет в инвентарь игрока. `Только администраторы`"),
            ],
        },
    }

    @app_commands.command(name="help", description="📖 Список всех команд бота по категориям")
    @app_commands.checks.has_permissions(administrator=True)
    async def help_cmd(self, interaction: discord.Interaction) -> None:
        view = HelpView(self.HELP_PAGES, interaction.user.id)
        embed = view.build_embed("general")
        await interaction.response.send_message(embed=embed, view=view)

    @help_cmd.error
    async def help_cmd_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Команда `/help` доступна только администраторам.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Произошла ошибка: {error}", ephemeral=True)

    # ─────────────────────────────────────────────────────────────────────────────

    @app_commands.command(name="ping", description="Посмотреть задержку бота.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Пинг: {latency}ms")

    @ping.error
    async def ping_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        await interaction.response.send_message("Произошла ошибка при выполнении команды /ping.", ephemeral=True)

    @app_commands.command(name="userinfo", description="Узнать информацию о пользователе")
    @app_commands.describe(member="Выберите пользователя (оставьте пустым для себя)")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member | None = None) -> None:
        if member is None:
            member = interaction.user

        embed = discord.Embed(
            title="👤 User Information",
            color=discord.Color.blue(),
            timestamp=interaction.created_at
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Username", value=member.name, inline=True)
        embed.add_field(name="ID", value=f"`{member.id}`", inline=False)

        joined_at = member.joined_at.strftime("%d.%m.%Y") if member.joined_at else "Unknown"
        embed.add_field(name="📅 Joined at", value=joined_at, inline=False)

        if member.is_timed_out():
            timestamp = int(member.timed_out_until.timestamp())
            mute_value = f"🤐 **Да** (Снимется <t:{timestamp}:R>)\nТочное время: <t:{timestamp}:f>"
        else:
            mute_value = "✅ Нет"
        embed.add_field(name="Muted", value=mute_value, inline=False)

        try:
            async with self.bot.db.execute(
                "SELECT activity_points, total_activity_points FROM users WHERE id = ?", (member.id,)
            ) as cursor:
                row = await cursor.fetchone()

            current_ap = row[0] if row and row[0] else 0
            total_ap = row[1] if row and row[1] else 0
            ap_text = f"Текущий баланс: `{current_ap}`\nЗа всё время: `{total_ap}`"
        except Exception as e:
            print(f"Ошибка БД в userinfo: {e}")
            ap_text = "Данные недоступны"

        embed.add_field(name="▬▬▬▬▬▬▬▬▬▬\n🏆 Очки Активности", value=ap_text, inline=False)

        try:
            async with self.bot.db.execute(
                "SELECT char_name, level FROM users WHERE id = ?", (member.id,)
            ) as cursor:
                prof = await cursor.fetchone()

            if prof and prof[0]:
                embed.add_field(
                    name="🎮 Персонаж",
                    value=f"**{prof[0]}** — lvl: `{prof[1] if prof[1] else 1}`",
                    inline=False
                )
            else:
                embed.add_field(name="🎮 Персонаж", value="Нет персонажа", inline=False)
        except Exception as e:
            print(f"Ошибка БД в userinfo (профиль): {e}")
            embed.add_field(name="🎮 Персонаж", value="Данные недоступны", inline=False)

        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        roles_text = ", ".join(roles) if roles else "No roles"
        embed.add_field(name=f"🎭 Роли ({len(roles)})", value=roles_text, inline=False)

        embed.set_footer(
            text=f"Invoked by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.response.send_message(embed=embed)

    #verify command
    @app_commands.command(name="verify", description="Показать сообщение с кнопкой верификации")
    @app_commands.checks.has_permissions(administrator=True)
    async def verify(self, interaction: discord.Interaction) -> None:
        text = "Нажмите кнопку ниже, чтобы пройти верификацию и получить доступ к остальным каналам сервера."
        await interaction.response.send_message(text, view=VerifyView())

    @verify.error
    async def verify_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Эта команда доступна только администраторам!", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Произошла ошибка: {error}", ephemeral=True)
    
    #avatar command
    @app_commands.command(name="avatar", description="🖼️ Посмотреть аватар пользователя")
    @app_commands.describe(member="Пользователь (оставьте пустым, чтобы посмотреть свой)")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member | None = None) -> None:
        target = member or interaction.user
        embed = discord.Embed(title=f"Аватар: {target.display_name}", color=discord.Color.blurple())
        embed.set_image(url=target.display_avatar.url)        
        await interaction.response.send_message(embed=embed) 
    #serverinfo command
    @app_commands.command(name="serverinfo", description="📊 Информация о сервере")
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        embed = discord.Embed(title=f"Информация о сервере: {guild.name}", color=discord.Color.blue())
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            
        embed.add_field(name="👑 Владелец", value=f"<@{guild.owner_id}>", inline=True)
        embed.add_field(name="📅 Создан", value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=True)
        embed.add_field(name="👥 Участников", value=str(guild.member_count), inline=True)
        
        channels_text = f"📝 Текст: {len(guild.text_channels)}\n🔊 Голос: {len(guild.voice_channels)}"
        embed.add_field(name="💬 Каналы", value=channels_text, inline=True)
        embed.add_field(name="🎭 Ролей", value=str(len(guild.roles)), inline=True)
        
        boost_text = f"Уровень {guild.premium_tier} ({guild.premium_subscription_count} бустов)"
        embed.add_field(name="🚀 Буст", value=boost_text, inline=True)
        
        await interaction.response.send_message(embed=embed)

    #remind command    
    @app_commands.command(name="remind", description="⏳ Установить напоминание в чат")
    @app_commands.describe(duration="Время (например: 10m, 2h)", text="О чем напомнить?")
    async def remind(self, interaction: discord.Interaction, duration: str, text: str) -> None:
        seconds = parse_duration(duration)
        if not seconds:
            return await interaction.response.send_message("❌ Неверный формат времени! Используйте `10m` (минуты), `2h` (часы).", ephemeral=True)          
        end_time = int(interaction.created_at.timestamp()) + seconds       
        await interaction.response.send_message(f"✅ Напоминание установлено! Я позову вас <t:{end_time}:R>.\n📝 **Причина:** {text}")
        await asyncio.sleep(seconds)        
        await interaction.channel.send(f"🔔 {interaction.user.mention}, напоминание: **{text}**")
    #alarm command
    @app_commands.command(name="alarm", description="⏰ Завести будильник на точное время")
    @app_commands.describe(
        exact_time="Время в формате ЧЧ:ММ (например: 15:30)",
        text="О чем напомнить?",
        date="Дата ДД.ММ.ГГГГ (Оставьте пустым для 'сегодня')",
        tz_offset="Ваш пояс (отклонение от UTC). Например: 1 для UTC+1"
    )
    async def alarm(self, interaction: discord.Interaction, exact_time: str, text: str, date: str | None = None, tz_offset: int = 2) -> None:
        try:
            tz = timezone(timedelta(hours=tz_offset))
            is_auto_date = False
            
            if not date or date == "0":
                date = datetime.now(tz).strftime("%d.%m.%Y")
                is_auto_date = True
                
            dt_str = f"{date} {exact_time}"
            dt = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
            dt = dt.replace(tzinfo=tz)
            
            target_ts = int(dt.timestamp())
            current_ts = int(interaction.created_at.timestamp())
            seconds_to_wait = target_ts - current_ts
            
            if seconds_to_wait <= 0:
                if is_auto_date:
                    dt += timedelta(days=1)
                    target_ts = int(dt.timestamp())
                    seconds_to_wait = target_ts - current_ts
                else:
                    return await interaction.response.send_message("❌ Это время уже прошло! Укажите будущее время.", ephemeral=True)
                
            await interaction.response.send_message(f"✅ Будильник установлен!\n📝 **Причина:** {text}\n⏰ **Сработает:** <t:{target_ts}:F> (<t:{target_ts}:R>).")
            await asyncio.sleep(seconds_to_wait)
            await interaction.channel.send(f"⏰ {interaction.user.mention}, сработал будильник: **{text}**")
            
        except ValueError:
            await interaction.response.send_message("❌ Ошибка формата! Используйте время `ЧЧ:ММ` (например 09:05 или 15:30).", ephemeral=True)
    #afk command
    @app_commands.command(name="afk", description="💤 Уйти в AFK (вас нельзя будет тегать без причины)")
    @app_commands.describe(reason="Причина ухода")
    async def afk(self, interaction: discord.Interaction, reason: str = "Отошел") -> None:
        await self.bot.db.execute("CREATE TABLE IF NOT EXISTS afk (user_id INTEGER PRIMARY KEY, reason TEXT, time INTEGER)")        
        await self.bot.db.execute("INSERT OR REPLACE INTO afk (user_id, reason, time) VALUES (?, ?, ?)", (interaction.user.id, reason, int(time.time())))
        await self.bot.db.commit()        
        await interaction.response.send_message(f"💤 {interaction.user.mention} ушел в AFK. Причина: **{reason}**")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot: return        
        try:
            async with self.bot.db.execute("SELECT reason FROM afk WHERE user_id = ?", (message.author.id,)) as cursor:
                row = await cursor.fetchone()
            
            if row:
                await self.bot.db.execute("DELETE FROM afk WHERE user_id = ?", (message.author.id,))
                await self.bot.db.commit()
                msg = await message.channel.send(f"👋 С возвращением, {message.author.mention}! Ваш статус AFK снят.")
                await msg.delete(delay=5)
        except Exception:
            pass
            
        if message.mentions:
            for user in message.mentions:
                try:
                    async with self.bot.db.execute("SELECT reason, time FROM afk WHERE user_id = ?", (user.id,)) as cursor:
                        row = await cursor.fetchone()
                        
                    if row:
                        reason, afk_time = row
                        await message.channel.send(f"💤 **{user.display_name}** сейчас в AFK (<t:{afk_time}:R>): {reason}", delete_after=10)
                except Exception:
                    pass    

    #----------------------------------------------
    #               Fan commands
    #----------------------------------------------

    #roll command
    @app_commands.command(name="roll", description="🎲 Бросить кубик (получить случайное число)")
    @app_commands.describe(maximum="Максимальное число (по умолчанию 100)")
    async def roll(self, interaction: discord.Interaction, maximum: int = 100) -> None:
        if maximum < 2: maximum = 2
        result = random.randint(1, maximum)
        await interaction.response.send_message(f"🎲 {interaction.user.mention} бросает кубики и выбивает **{result}** (из {maximum})!")

    #flip command
    @app_commands.command(name="flip", description="🪙 Подкинуть монетку (Орел или Решка)")
    async def flip(self, interaction: discord.Interaction) -> None:
        result = random.choice(["🦅 Орел", "🪙 Решка"])
        await interaction.response.send_message(f"{interaction.user.mention} подкидывает монетку... Выпадает: **{result}**!")

    #----------------------------------------------
    #               giveaway commands
    #----------------------------------------------
    @app_commands.command(name="giveaway", description="🎁 Создать розыгрыш")
    @app_commands.describe(
        duration="Время (например: 10m, 2h, 1d)",
        winners="Количество победителей",
        prize="Что разыгрываем?"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def start_gw(self, interaction: discord.Interaction, duration: str, winners: int, prize: str):
        seconds = parse_duration(duration)
        if not seconds:
            return await interaction.response.send_message(
                "❌ Неверный формат времени! Используйте `10m` (минуты), `2h` (часы), `1d` (дни).",
                ephemeral=True
            )
        if winners < 1:
            return await interaction.response.send_message("❌ Должен быть хотя бы 1 победитель.", ephemeral=True)

        end_time = int(time.time()) + seconds

        embed = discord.Embed(
            title="🎁 РОЗЫГРЫШ! 🎁",
            description=(
                f"**Приз:** {prize}\n"
                f"**Победителей:** {winners}\n"
                f"**Итоги:** <t:{end_time}:R> (<t:{end_time}:f>)\n\n"
                "Жми кнопку ниже, чтобы забрать билет!"
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="Удачи всем участникам!")

        await interaction.response.send_message("✅ Розыгрыш успешно запущен!", ephemeral=True)

        msg = await interaction.channel.send(embed=embed, view=GiveawayView(self.bot))

        await self.bot.db.execute(
            "INSERT INTO giveaways (message_id, channel_id, end_time, prize, winners_count, is_active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (msg.id, interaction.channel.id, end_time, prize, winners)
        )
        await self.bot.db.commit()

    @tasks.loop(seconds=15)
    async def check_giveaways(self):
        if not self.bot.is_ready():
            return

        current_time = int(time.time())

        async with self.bot.db.execute(
            "SELECT message_id, channel_id, prize, winners_count FROM giveaways "
            "WHERE is_active = 1 AND end_time <= ?",
            (current_time,)
        ) as cursor:
            completed_giveaways = await cursor.fetchall()

        for row in completed_giveaways:
            msg_id, channel_id, prize, winners_count = row

            await self.bot.db.execute("UPDATE giveaways SET is_active = 0 WHERE message_id = ?", (msg_id,))
            await self.bot.db.commit()

            async with self.bot.db.execute(
                "SELECT user_id FROM giveaway_participants WHERE message_id = ?", (msg_id,)
            ) as p_cursor:
                participants = [r[0] for r in await p_cursor.fetchall()]

            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue

            try:
                msg = await channel.fetch_message(msg_id)
                embed = msg.embeds[0]
                embed.title = "🎊 РОЗЫГРЫШ ЗАВЕРШЕН 🎊"
                embed.description = f"**Приз:** {prize}\nУчастников было: `{len(participants)}`"
                embed.color = discord.Color.dark_gray()
                await msg.edit(embed=embed, view=None)
            except Exception:
                pass

            if not participants:
                await channel.send(f"⚠️ Розыгрыш на **{prize}** завершен, но никто не принял участие..")
                continue

            actual_count = min(winners_count, len(participants))
            winners = random.sample(participants, actual_count)
            winners_mentions = ", ".join(f"<@{w}>" for w in winners)

            await channel.send(
                f"🎉 Поздравляем {winners_mentions}! Вы выиграли: **{prize}**! "
                "Ожидайте, с вами свяжется администрация."
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))