import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Guild and Role IDs
GUILD_ID = 1375574037597650984
ROLE_ID_HARVESTER = 1375574147064664164

user_orders = {}  # Track ongoing orders


# 🎮 UI View
class HarvesterView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(HarvesterRoleButton())
        self.add_item(BuyHarvesterButton())


class HarvesterRoleButton(Button):
    def __init__(self):
        super().__init__(label="🎃 Get Harvester Role", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(ROLE_ID_HARVESTER)
        if role in interaction.user.roles:
            await interaction.response.send_message("❌ You already have the role!", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ Role added!", ephemeral=True)


class BuyHarvesterButton(Button):
    def __init__(self):
        super().__init__(label="🔪 Buy Harvester", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild

        # Prevent multiple tickets
        existing = discord.utils.get(guild.channels, name=f"order-{user.name.lower()}")
        if existing:
            await interaction.response.send_message("❌ You already have an open ticket!", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        ticket = await guild.create_text_channel(f"order-{user.name}", overwrites=overwrites)
        await ticket.send(f"👋 Hello {user.mention}, how many **Harvester** would you like to buy?")
        user_orders[user.id] = {"item": "Harvester", "quantity": 0}

        await interaction.response.send_message("✅ Ticket created!", ephemeral=True)


# ✅ Bot startup
@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    bot.add_view(HarvesterView())  # Register persistent buttons


# 🛍️ Shop command
@bot.command()
async def shop(ctx):
    embed = discord.Embed(
        title="🎃 Harvester Panel",
        description="Choose an option below:",
        color=discord.Color.orange()
    )
    embed.add_field(name="🔪 Harvester", value="$10 each")
    embed.set_footer(text="Click a button to continue")

    # Send one embed only
    await ctx.send(embed=embed, view=HarvesterView())


# 📥 Handle ticket number input
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.name.startswith("order-"):
        user_id = message.author.id
        if user_id in user_orders and user_orders[user_id]["quantity"] == 0:
            try:
                qty = int(message.content)
                if qty <= 0:
                    await message.channel.send("❌ Enter a valid number.")
                    return

                user_orders[user_id]["quantity"] = qty
                total = qty * 10

                await message.channel.send(
                    f"✅ Order confirmed: `{qty}x Harvester` for `${total}`.\nThanks!"
                )
                await message.channel.send("⏳ Closing this ticket in **10 seconds**...")

                await asyncio.sleep(10)
                await message.channel.delete()
                del user_orders[user_id]
            except ValueError:
                await message.channel.send("❌ Please enter a number.")
    await bot.process_commands(message)


# 🔐 Run the bot
bot.run(os.getenv("BOT_TOKEN"))
