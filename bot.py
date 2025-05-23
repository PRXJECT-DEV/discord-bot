import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.members = True
intents.reactions = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Guild and Role IDs
GUILD_ID = 1375574037597650984
ROLE_ID_HARVESTER = 1375574147064664164

user_orders = {}  # user_id -> {"item": "Harvester", "quantity": X}

# ✅ Ready check
@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

# 🔁 Basic ping command
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# 📩 Reaction role setup
@bot.command()
@commands.has_permissions(administrator=True)
async def reactionrolesetup(ctx):
    guild = bot.get_guild(GUILD_ID)
    role = guild.get_role(ROLE_ID_HARVESTER)

    embed = discord.Embed(
        title="Choose your roles!",
        description=f"React with 🎃 to get the **{role.name}** role."
    )
    message = await ctx.send(embed=embed)
    await message.add_reaction("🎃")

# 🛒 Shop Command (ticket-based)
@bot.command()
async def shop(ctx):
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

# ✅ Reaction handler (both shop + roles)
@bot.event
async def on_raw_reaction_add(payload):
    if payload.guild_id != GUILD_ID or payload.member.bot:
        return

    emoji = str(payload.emoji)
    guild = bot.get_guild(payload.guild_id)
    member = payload.member

    # 🎃 Role handling
    if emoji == "🎃":
        role = guild.get_role(ROLE_ID_HARVESTER)
        if member and role:
            await member.add_roles(role)
            print(f"Added role {role.name} to {member.display_name}")
        return

    # 🔪 Shop handling
    if emoji == "🔪":
        existing = discord.utils.get(guild.channels, name=f"order-{member.name}")
        if existing:
            await existing.send(f"{member.mention}, you already have an open ticket.")
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        channel = await guild.create_text_channel(f"order-{member.name}", overwrites=overwrites)

        await channel.send(
            f"👋 Hi {member.mention}, you selected **Harvester**!\nHow many would you like to buy?"
        )
        user_orders[member.id] = {"item": "Harvester", "quantity": 0}

# 🔁 Reaction remove (only for role removal)
@bot.event
async def on_raw_reaction_remove(payload):
    if payload.guild_id != GUILD_ID:
        return

    emoji = str(payload.emoji)
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)

    if emoji == "🎃":
        role = guild.get_role(ROLE_ID_HARVESTER)
        if member and role:
            await member.remove_roles(role)
            print(f"Removed role {role.name} from {member.display_name}")

# 📦 Quantity handler
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.name.startswith("order-"):
        uid = message.author.id
        if uid in user_orders and user_orders[uid]["quantity"] == 0:
            try:
                qty = int(message.content)
                if qty <= 0:
                    await message.channel.send("❌ Please enter a valid quantity.")
                    return

                user_orders[uid]["quantity"] = qty
                await message.channel.send(
                    f"✅ Noted: `{qty}x {user_orders[uid]['item']}`.\nUse `!checkout` when ready!"
                )
            except ValueError:
                await message.channel.send("❌ Please enter a number.")
    await bot.process_commands(message)

# 💰 Checkout command
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

# Run bot
bot.run(os.getenv("BOT_TOKEN"))
