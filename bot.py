import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.members = True        # To manage roles and members
intents.reactions = True      # To track reactions added/removed
intents.message_content = True  # To read commands in messages

bot = commands.Bot(command_prefix="!", intents=intents)

# Replace these with your actual IDs (as integers)
GUILD_ID = 1375574037597650984          # Your Discord server ID here
ROLE_ID_HARVESTER = 1375574147064664164  # The role ID for the "Harvester" role

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def reactionrolesetup(ctx):
    """Sends the reaction role message"""
    guild = bot.get_guild(GUILD_ID)
    role = guild.get_role(ROLE_ID_HARVESTER)

    embed = discord.Embed(
        title="Choose your roles!",
        description=f"React with 🎃 to get the **{role.name}** role."
    )
    message = await ctx.send(embed=embed)
    await message.add_reaction("🎃")

    # Optionally save message.id for persistence (not covered here)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.guild_id != GUILD_ID:
        return

    if str(payload.emoji) == "🎃":
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(ROLE_ID_HARVESTER)
        member = guild.get_member(payload.user_id)
        if member and role:
            await member.add_roles(role)
            print(f"Added role {role.name} to {member.display_name}")

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.guild_id != GUILD_ID:
        return

    if str(payload.emoji) == "🎃":
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(ROLE_ID_HARVESTER)
        member = guild.get_member(payload.user_id)
        if member and role:
            await member.remove_roles(role)
            print(f"Removed role {role.name} from {member.display_name}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

bot.run(os.getenv("BOT_TOKEN"))
