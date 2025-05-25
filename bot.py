import discord
from discord.ext import commands
from discord import app_commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Sync command tree to the guild
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

# Example slash command: /setup
@bot.tree.command(name="setup", description="Set up the bot with a short tutorial.")
async def setup_command(interaction: discord.Interaction):
    await interaction.response.send_message("Welcome to the bot! Here's how to use it...", ephemeral=True)

# Example slash command: /add
@bot.tree.command(name="add", description="Create a new shop prompt.")
@app_commands.describe(
    name="Name of the product",
    price="Price of the item (e.g. 0.69)",
    stock="Stock count for the item"
)
async def add_command(interaction: discord.Interaction, name: str, price: float, stock: int):
    embed = discord.Embed(
        title=name,
        description=f"Price: ${price:.2f}\nStock: {stock}",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Requested by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)
