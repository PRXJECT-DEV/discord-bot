import os
import discord
from discord.ext import commands
from discord import app_commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Optional: limit to a test guild for instant slash updates
GUILD_ID = 1375574037597650984  # replace with your guild/server ID

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))  # Fast for testing
        print(f"Synced {len(synced)} commands to guild {GUILD_ID}")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    print(f"Logged in as {bot.user}")

# Slash command: /setup
@bot.tree.command(name="setup", description="Show how to use the bot.")
async def setup_command(interaction: discord.Interaction):
    await interaction.response.send_message("Thanks for using this bot! Here's how to get started.", ephemeral=True)

# Run the bot
bot.run(os.getenv("BOT_TOKEN"))
