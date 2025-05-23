import discord
from discord.ext import commands
import os
import asyncio

intents = discord.Intents.default()
intents.members = True
intents.reactions = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# IDs (replace with your actual IDs)
GUILD_ID = 1375574037597650984
ROLE_ID_HARVESTER = 1375574147064664164

# Track user orders and open tickets
user_orders = {}  # user_id -> {"item": str, "quantity": int}
open_tickets = set()  # user_ids currently with open ticket

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def reactionrolesetup(ctx):
    """Setup reaction role message"""
    guild = bot.get_guild(GUILD_ID)
    role = guild.get_role(ROLE_ID_HARVESTER)
    embed = discord.Embed(
        title="Choose your roles!",
        description=f"React with 🎃 to get the **{role.name}** role."
    )
    message = await ctx.send(embed=embed)
    await message.add_reaction("🎃")

@bot.command()
async def shop(ctx):
    """Send shop embed with reactions"""
    embed = discord.Embed(
        title="🛒 MM2 Item Shop",
        description="React below to start your order!",
        color=discord.Color.green()
    )
    embed.add_field(name="🔪 Harvester", value="`$10 each`", inline=False)
    embed.set_image(url="https://your-image-url.com/harvester.png")
    embed.set_footer(text="React with an item to order")

    message = await ctx.send(embed=embed)
    await message.add_reaction("🔪")

@bot.event
async def on_raw_reaction_add(payload):
    # Ignore reactions outside the guild or from bots
    if payload.guild_id != GUILD_ID or payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    emoji = str(payload.emoji)

    # Reaction role: 🎃
    if emoji == "🎃":
        role = guild.get_role(ROLE_ID_HARVESTER)
        if role not in member.roles:
            await member.add_roles(role)
            print(f"Added role {role.name} to {member.display_name}")
        return

    # Shop reaction: 🔪
    if emoji == "🔪":
        if member.id in open_tickets:
            # Already has ticket open, ignore
            return

        # Create ticket channel with permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        ticket_channel = await guild.create_text_channel(f"order-{member.name}", overwrites=overwrites)

        open_tickets.add(member.id)
        user_orders[member.id] = {"item": "Harvester", "quantity": 0}

        await ticket_channel.send(
            f"👋 Hi {member.mention}, you selected **Harvester**!\nHow many would you like to buy?"
        )

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.guild_id != GUILD_ID:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    emoji = str(payload.emoji)

    # Remove role when reaction is removed
    if emoji == "🎃":
        role = guild.get_role(ROLE_ID_HARVESTER)
        if role in member.roles:
            await member.remove_roles(role)
            print(f"Removed role {role.name} from {member.display_name}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = message.author.id

    # Check if message is in a ticket channel and quantity not yet set
    if message.channel.name.startswith("order-") and uid in user_orders and user_orders[uid]["quantity"] == 0:
        try:
            qty = int(message.content)
            if qty <= 0:
                await message.channel.send("❌ Quantity must be at least 1.")
                return

            user_orders[uid]["quantity"] = qty
            await message.channel.send(
                f"✅ Noted: `{qty}x Harvester`. Closing this ticket shortly."
            )

            # Wait a bit before closing to let user see confirmation
            await asyncio.sleep(3)

            # Delete the ticket channel
            await message.channel.delete()

            # Cleanup
            open_tickets.discard(uid)
            user_orders.pop(uid, None)

        except ValueError:
            await message.channel.send("❌ Please enter a valid number.")

    await bot.process_commands(message)

@bot.command()
async def checkout(ctx):
    uid = ctx.author.id
    if uid not in user_orders or user_orders[uid]["quantity"] == 0:
        await ctx.send("❌ No valid order found. Use `!shop` to start.")
        return

    item = user_orders[uid]["item"]
    qty = user_orders[uid]["quantity"]
    price_each = 10
    total = qty * price_each

    embed = discord.Embed(title="🧾 Order Summary", color=discord.Color.blue())
    embed.add_field(name="Item", value=item)
    embed.add_field(name="Quantity", value=str(qty))
    embed.add_field(name="Total", value=f"${total}")
    embed.set_footer(text="Pay via PayPal after confirming.")

    await ctx.send(embed=embed)

bot.run(os.getenv("BOT_TOKEN"))
