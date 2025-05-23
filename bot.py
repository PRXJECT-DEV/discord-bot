import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.members = True
intents.reactions = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

GUILD_ID = 1375574037597650984  # Your server ID
ROLE_ID_HARVESTER = 1375574147064664164  # Harvester role ID

user_orders = {}  # user_id -> {"item": str, "quantity": int}
open_tickets = set()
processed_reactions = set()

@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def shop(ctx):
    guild = bot.get_guild(GUILD_ID)
    role = guild.get_role(ROLE_ID_HARVESTER)
    
    embed = discord.Embed(
        title="🛒 MM2 Item Shop",
        description="React with 🎃 to get the **Harvester** role.\nReact with 🔪 to order the Harvester!",
        color=discord.Color.green()
    )
    embed.add_field(name="🔪 Harvester", value="`$10 each`", inline=False)
    embed.set_image(url="https://your-image-url.com/harvester.png")  # Replace with your image URL
    embed.set_footer(text="React below to get role or order!")
    
    message = await ctx.send(embed=embed)
    await message.add_reaction("🎃")
    await message.add_reaction("🔪")

@bot.event
async def on_raw_reaction_add(payload):
    key = (payload.message_id, payload.user_id, str(payload.emoji))
    if key in processed_reactions:
        return
    processed_reactions.add(key)

    if payload.guild_id != GUILD_ID:
        return
    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    emoji = str(payload.emoji)
    if not member:
        return

    # Get the channel and message to check if it's the shop message
    channel = guild.get_channel(payload.channel_id)
    try:
        message = await channel.fetch_message(payload.message_id)
    except:
        return

    # Confirm this is the shop message by checking embed title
    if not message.embeds:
        return
    embed = message.embeds[0]
    if embed.title != "🛒 MM2 Item Shop":
        return

    if emoji == "🎃":
        # Give Harvester role
        role = guild.get_role(ROLE_ID_HARVESTER)
        if role not in member.roles:
            await member.add_roles(role)
            await member.send(f"You have been given the **{role.name}** role!")
        return

    if emoji == "🔪":
        # Open order ticket if not already open
        if member.id in open_tickets:
            existing_channel = discord.utils.get(guild.text_channels, name=f"order-{member.name}")
            if existing_channel:
                await existing_channel.send(f"{member.mention}, you already have an open ticket.")
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        ticket_channel = await guild.create_text_channel(f"order-{member.name}", overwrites=overwrites)
        open_tickets.add(member.id)
        user_orders[member.id] = {"item": "Harvester", "quantity": 0}

        await ticket_channel.send(
            f"👋 Hi {member.mention}, you selected **Harvester**!\nPlease type the quantity you'd like to buy."
        )
        return

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.guild_id != GUILD_ID:
        return
    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    emoji = str(payload.emoji)

    if not member:
        return

    if emoji == "🎃":
        role = guild.get_role(ROLE_ID_HARVESTER)
        if role in member.roles:
            await member.remove_roles(role)
            try:
                await member.send(f"The **{role.name}** role has been removed from you.")
            except:
                pass

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.name.startswith("order-"):
        user_id = message.author.id
        if user_id not in user_orders:
            return
        if user_orders[user_id]["quantity"] != 0:
            return

        try:
            qty = int(message.content)
            if qty <= 0:
                await message.channel.send("❌ Please enter a positive number for quantity.")
                return

            user_orders[user_id]["quantity"] = qty
            await message.channel.send(
                f"✅ Got it! You ordered `{qty}x {user_orders[user_id]['item']}`.\nUse `!checkout` anywhere to see your order summary."
            )
            open_tickets.discard(user_id)
            await message.channel.send("Closing your ticket now...")
            await message.channel.delete()
        except ValueError:
            await message.channel.send("❌ Please enter a valid number.")

    await bot.process_commands(message)

@bot.command()
async def checkout(ctx):
    uid = ctx.author.id
    if uid not in user_orders or user_orders[uid]["quantity"] == 0:
        await ctx.send("❌ No active order found. Use `!shop` and react to start ordering.")
        return

    item = user_orders[uid]["item"]
    qty = user_orders[uid]["quantity"]
    price_each = 10
    total = qty * price_each

    embed = discord.Embed(title="🧾 Order Summary", color=discord.Color.blue())
    embed.add_field(name="Item", value=item)
    embed.add_field(name="Quantity", value=str(qty))
    embed.add_field(name="Total Price", value=f"${total}")
    embed.set_footer(text="Thank you for your order!")

    await ctx.send(embed=embed)

bot.run(os.getenv("BOT_TOKEN"))
