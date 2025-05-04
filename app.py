from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

import asyncio
import discord
from discord.ext import commands
from discord.ui import Button, View
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Конфигурация ---
# Вставь сюда настоящий токен
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
CATEGORY_ID = int(os.getenv("CATEGORY_ID"))
MOD_ROLE_ID = int(os.getenv("MOD_ROLE_ID"))
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
JSON_KEY_PATH = os.getenv("JSON_KEY_PATH")

# --- Подключение к Google Sheets ---
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEY_PATH, scope)
gs_client = gspread.authorize(creds)
sheet = gs_client.open(GOOGLE_SHEET_NAME).sheet1
archive = gs_client.open(GOOGLE_SHEET_NAME).worksheet("archive")


# === View с кнопкой закрытия заявки ===
class CloseTicketView(discord.ui.View):
    def __init__(self, open_time, author):
        super().__init__(timeout=None)
        self.open_time = open_time  # Время открытия тикета
        self.author = author  # Создатель тикета

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Ticket is closed. Archiving messages and deleting channel in 5 seconds...",
            ephemeral=True
        )

        channel = interaction.channel
        messages = [msg async for msg in channel.history(limit=100, oldest_first=True)]

        # Получаем дату и время закрытия
        close_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Сохраняем данные в sheet1
        sheet.append_row([
            channel.name,
            str(self.author),  # Кто создал
            str(self.open_time),
            str(interaction.user),  # Кто закрыл
            close_time
        ])

        # Архивируем сообщения
        for msg in messages:
            archive.append_row([
                channel.name,
                str(interaction.user),  # Кто закрыл
                msg.content or "[вложение/пусто]",
                self.open_time,  # Время открытия тикета
                close_time  # Время закрытия тикета
            ])

        await asyncio.sleep(5)
        await channel.delete()


# === View с кнопкой создания заявки ===
class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = bot.get_guild(GUILD_ID)
        author = interaction.user
        category = guild.get_channel(CATEGORY_ID)
        mod_role = guild.get_role(MOD_ROLE_ID)

        channel_name = f"ticket-{author.name}".replace(" ", "-").lower()

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            mod_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            author: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )

        open_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Сохраняем данные в sheet1
        sheet.append_row([
            channel.name,
            str(author),
            open_time,
            "",  # Кто закрыл (пока пусто)
            ""  # Когда закрыл (пока пусто)
        ])

        await channel.send(
            content=f"{author.mention}, Your ticket has been created. Wait for a moderator's response.",
            view=CloseTicketView(open_time, author)  # Передаем автора
        )

        await interaction.response.send_message(
            f"{author.mention}, Ticket created: {channel.mention}",
            ephemeral=True
        )


# === Команда для вывода кнопки создания заявки ===
@bot.command()
async def register(ctx):
    await ctx.send("Click the button below to create a Ticket:", view=TicketOpenView())


# === Подключение View после перезапуска бота ===
@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")


# === Запуск бота ===
bot.run(TOKEN)