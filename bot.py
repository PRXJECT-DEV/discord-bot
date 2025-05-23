import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.members = True
intents.reactions = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

GUILD_ID = 1375574037597650984
ROLE_ID_HARVESTER = 1375574147064664164
user_orders = {}  # user_id -> {"item": str, "quantity": int}

# Track ticket channels to prevent duplicates
open_tickets = {}

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def shop(ctx):
    guild = bot.get_guild(GUILD_ID)
    role = guild.get_role(ROLE_ID_HARVESTER)

    embed = discord.Embed(
        title="🛒 MM2 Item Shop",
        description="React to start your order or claim a role!",
        color=discord.Color.green()
    )
    embed.add_field(name="🔪 Harvester", value="`$10 each`", inline=False)
    embed.add_field(name="🎃 Role", value=f"Get the **{role.name}** role", inline=False)
    embed.set_footer(text="React below")

    message = await ctx.send(embed=embed)
    await message.add_reaction("🎃")
    await message.add_reaction("🔪")

@bot.event
async def on_raw_reaction_add(payload):
    if payload.guild_id != GUILD_ID or payload.user_id == bot.user.id:
        return

    emoji = str(payload.emoji)
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)

    # 🎃 Role assign
    if emoji == "🎃":
        role = guild.get_role(ROLE_ID_HARVESTER)
        if role and member:
            await member.add_roles(role)
            print(f"Added role {role.name} to {member.display_name}")
        return

    # 🔪 Shop order ticket
    if emoji == "🔪":
        if member.id in open_tickets:
            return  # Already has an open ticket

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        channel = await guild.create_text_channel(f"order-{member.name}", overwrites=overwrites)
        open_tickets[member.id] = channel.id
        user_orders[member.id] = {"item": "Harvester", "quantity": 0}

        await channel.send(
            f"Hi {member.mention}, you selected **Harvester**!\nPlease type how many you'd like to order below."
        )

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
                    await message.channel.send("❌ Please enter a number greater than 0.")
                    return

                user_orders[uid]["quantity"] = qty
                await message.channel.send(f"✅ Quantity set: `{qty}x Harvester`. Use `!checkout` to continue.")

                # Close ticket after setting quantity
                del open_tickets[uid]
                await message.channel.send("✅ Closing ticket...")
                await message.channel.delete()

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
    total = qty * 10

    embed = discord.Embed(title="🧾 Order Summary", color=discord.Color.blue())
    embed.add_field(name="Item", value=item)
    embed.add_field(name="Quantity", value=str(qty))
    embed.add_field(name="Total", value=f"${total}")
    embed.set_footer(text="Pay via PayPal after confirming.")

    await ctx.send(embed=embed)

bot.run(os.getenv("BOT_TOKEN"))
