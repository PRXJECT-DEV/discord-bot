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

GUILD_ID = 1375574037597650984
ROLE_ID_HARVESTER = 1375574147064664164

user_orders = {}  # temp user -> current ticket order
user_totals = {}  # persistent user_id -> total Harvester count


# 🎮 UI Buttons
class HarvesterView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(HarvesterBuyButton())
        self.add_item(HarvesterRemoveAllButton())


class HarvesterBuyButton(Button):
    def __init__(self):
        super().__init__(label="🔪 Buy Harvester", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild

        # Prevent duplicate ticket
        existing = discord.utils.get(guild.channels, name=f"order-{user.name.lower()}")
        if existing:
            await interaction.response.send_message("❌ You already have an open ticket.", ephemeral=True)
            return

        # Create private ticket channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        ticket = await guild.create_text_channel(f"order-{user.name}", overwrites=overwrites)
        await ticket.send(f"👋 Hi {user.mention}, how many **Harvester** would you like to buy?")
        user_orders[user.id] = {"channel": ticket.id, "quantity": 0}
        await interaction.response.send_message("✅ Ticket created!", ephemeral=True)


class HarvesterRemoveAllButton(Button):
    def __init__(self):
        super().__init__(label="🗑️ Remove All Harvesters", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        user_totals[user.id] = 0

        # Reset nickname
        try:
            await user.edit(nick=None)
        except discord.Forbidden:
            await interaction.response.send_message("⚠️ I couldn't reset your nickname (check permissions).", ephemeral=True)
            return

        await interaction.response.send_message("🧹 Removed all Harvester stacks!", ephemeral=True)


# 📥 Handle ticket input
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = message.author.id
    if message.channel.name.startswith("order-") and uid in user_orders:
        if user_orders[uid]["quantity"] == 0:
            try:
                qty = int(message.content)
                if qty <= 0:
                    await message.channel.send("❌ Enter a valid number.")
                    return

                # Update user's total
                previous = user_totals.get(uid, 0)
                new_total = previous + qty
                user_totals[uid] = new_total

                # Try updating nickname
                new_nick = f"{message.author.name} | Harvester x{new_total}"
                try:
                    await message.author.edit(nick=new_nick)
                except discord.Forbidden:
                    await message.channel.send("⚠️ I couldn't change your nickname (check permissions).")

                await message.channel.send(f"✅ Order saved: `{qty}x Harvester`. You now have **Harvester x{new_total}**.")
                await message.channel.send("⏳ Closing this ticket in 10 seconds...")

                await asyncio.sleep(10)
                await message.channel.delete()
                del user_orders[uid]
            except ValueError:
                await message.channel.send("❌ Please enter a valid number.")
    await bot.process_commands(message)


# 📦 !shop Command
@bot.command()
async def shop(ctx):
    embed = discord.Embed(
        title="🎃 Harvester Panel",
        description="Buy or manage your Harvester stack.",
        color=discord.Color.orange()
    )
    embed.add_field(name="🔪 Harvester", value="$10 each (stackable)")
    embed.set_footer(text="Click a button to continue")

    await ctx.send(embed=embed, view=HarvesterView())


# ✅ Bot is Ready
@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    bot.add_view(HarvesterView())  # Persistent buttons


# 🔐 Run bot
bot.run(os.getenv("BOT_TOKEN"))
