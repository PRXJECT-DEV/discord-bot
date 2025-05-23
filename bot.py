import discord
from discord.ext import commands
from discord.ui import Button, View
import os

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

GUILD_ID = 1375574037597650984
ROLE_ID_HARVESTER = 1375574147064664164

user_orders = {}  # Tracks current user orders


class ShopView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="🎃 Get Harvester Role", custom_id="get_role"))
        self.add_item(Button(label="🔪 Buy Harvester", custom_id="buy_item"))


@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    bot.add_view(ShopView())  # Register persistent view
    print("Persistent view loaded.")


@bot.command()
@commands.has_permissions(administrator=True)
async def shop(ctx):
    """Sends the embed with buttons"""
    embed = discord.Embed(
        title="🎃 Harvester Access Panel",
        description="Click a button below to get the role or buy an item.",
        color=discord.Color.orange()
    )
    embed.add_field(name="🔪 Harvester", value="`$10 each`")
    embed.set_footer(text="Buttons powered by Discord UI")

    await ctx.send(embed=embed, view=ShopView())


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.guild or interaction.user.bot:
        return

    guild = interaction.guild
    user = interaction.user
    custom_id = interaction.data.get("custom_id")

    if custom_id == "get_role":
        role = guild.get_role(ROLE_ID_HARVESTER)
        if role in user.roles:
            await interaction.response.send_message("❌ You already have the role!", ephemeral=True)
        else:
            await user.add_roles(role)
            await interaction.response.send_message("✅ Role granted!", ephemeral=True)

    elif custom_id == "buy_item":
        # Avoid dupes
        existing = discord.utils.get(guild.channels, name=f"order-{user.name.lower()}")
        if existing:
            await interaction.response.send_message("❌ You already have a ticket open!", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        ticket_channel = await guild.create_text_channel(f"order-{user.name}", overwrites=overwrites)
        await ticket_channel.send(f"👋 {user.mention}, how many **Harvester** would you like to buy?")
        user_orders[user.id] = {"item": "Harvester", "quantity": 0}
        await interaction.response.send_message("✅ Ticket created!", ephemeral=True)


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
                total = qty * 10
                await message.channel.send(
                    f"✅ Order placed for `{qty}x Harvester`.\nTotal: `${total}`\nThank you!"
                )

                # Clean up
                del user_orders[uid]
                await message.channel.send("⏳ Closing ticket in 5 seconds...")
                await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=5))
                await message.channel.delete()

            except ValueError:
                await message.channel.send("❌ Please enter a number.")

    await bot.process_commands(message)


bot.run(os.getenv("BOT_TOKEN"))
