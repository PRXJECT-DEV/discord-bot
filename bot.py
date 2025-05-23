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
user_orders = {}
open_tickets = {}  # user_id -> channel_id
shop_message_origin = {}  # user_id -> channel_id

@bot.event
async def on_ready():
    print(f"✅ Bot online as {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
@commands.has_permissions(administrator=True)
async def reactionrolesetup(ctx):
    guild = bot.get_guild(GUILD_ID)
    role = guild.get_role(ROLE_ID_HARVESTER)

    embed = discord.Embed(
        title="🎃 Role Selection",
        description=f"React with 🎃 to get the **{role.name}** role."
    )
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎃")

@bot.command()
async def shop(ctx):
    embed = discord.Embed(
        title="🛒 MM2 Item Shop",
        description="React below to order:",
        color=discord.Color.green()
    )
    embed.add_field(name="🔪 Harvester", value="`$10 each`", inline=False)
    embed.set_footer(text="React to start your order")

    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🔪")
    shop_message_origin[ctx.author.id] = ctx.channel.id  # Save where the user clicked

@bot.event
async def on_raw_reaction_add(payload):
    if payload.guild_id != GUILD_ID or payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    emoji = str(payload.emoji)

    # 🎃 Role assignment
    if emoji == "🎃":
        role = guild.get_role(ROLE_ID_HARVESTER)
        if role not in member.roles:
            await member.add_roles(role)
            print(f"✅ Added {role.name} to {member.name}")
        return

    # 🔪 Shop item reaction
    if emoji == "🔪":
        if member.id in open_tickets:
            return  # Already has a ticket

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        ticket_channel = await guild.create_text_channel(f"order-{member.name}", overwrites=overwrites)
        open_tickets[member.id] = ticket_channel.id
        user_orders[member.id] = {"item": "Harvester", "quantity": 0}

        await ticket_channel.send(
            f"👋 Hi {member.mention}, you selected **Harvester**!\nHow many would you like to buy?"
        )

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = message.author.id
    if message.channel.name.startswith("order-") and uid in user_orders and user_orders[uid]["quantity"] == 0:
        try:
            qty = int(message.content)
            if qty <= 0:
                await message.channel.send("❌ Quantity must be at least 1.")
                return

            user_orders[uid]["quantity"] = qty
            await message.channel.send(
                f"✅ Noted: `{qty}x Harvester`. Ticket will close now. Use `!checkout` in this channel."
            )

            # Save origin channel
            origin_channel = shop_message_origin.get(uid)
            if origin_channel:
                try:
                    channel = bot.get_channel(origin_channel)
                    await channel.send(f"📦 {message.author.mention}, your Harvester order for `{qty}` has been noted.")
                except:
                    pass

            # Close ticket after short delay
            await message.channel.send("🔒 Closing this ticket in 3 seconds...")
            await discord.utils.sleep_until(discord.utils.utcnow() + discord.timedelta(seconds=3))

            # Delete ticket channel
            ticket_channel = message.channel
            await ticket_channel.delete()

            # Cleanup
            del open_tickets[uid]

        except ValueError:
            await message.channel.send("❌ Please enter a number.")
    await bot.process_commands(message)

@bot.command()
async def checkout(ctx):
    uid = ctx.author.id
    if uid not in user_orders or user_orders[uid]["quantity"] == 0:
        await ctx.send("❌ No valid order found. Use `!shop` to start.")
        return

    order = user_orders[uid]
    total = order["quantity"] * 10

    embed = discord.Embed(title="🧾 Order Summary", color=discord.Color.blurple())
    embed.add_field(name="Item", value=order["item"], inline=True)
    embed.add_field(name="Quantity", value=str(order["quantity"]), inline=True)
    embed.add_field(name="Total", value=f"${total}", inline=True)
    embed.set_footer(text="Use PayPal or message staff to complete payment.")

    await ctx.send(embed=embed)

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.guild_id != GUILD_ID:
        return
    if str(payload.emoji) == "🎃":
        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        role = guild.get_role(ROLE_ID_HARVESTER)
        if member and role:
            await member.remove_roles(role)
            print(f"❌ Removed {role.name} from {member.name}")

bot.run(os.getenv("BOT_TOKEN"))
