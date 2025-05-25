import os
import asyncio
import discord
from discord.ext import commands
from discord.ui import Button, View
from discord.utils import get

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

OWNER_NAME = "Trx.255"

shop_items = {}
user_carts = {}
tutorial_msg_id = None

# ========== VIEWS ==========

class ShopView(View):
    def __init__(self, item_name, user_id=None):
        super().__init__(timeout=None)
        self.item_name = item_name
        self.user_id = user_id
        self.add_buttons()

    def add_buttons(self):
        self.clear_items()
        self.add_item(AddToCartButton(self.item_name))
        self.add_item(RemoveFromCartButton(self.item_name))
        quantity = 0
        if self.user_id:
            cart = user_carts.get(self.user_id, {})
            quantity = cart.get(self.item_name, 0)
        self.add_item(CartCountButton(quantity))

    async def update_cart_buttons(self, interaction):
        self.user_id = interaction.user.id
        self.add_buttons()
        await interaction.response.edit_message(view=self)

    async def interaction_check(self, interaction):
        await self.update_cart_buttons(interaction)
        return True

class AddToCartButton(Button):
    def __init__(self, item_name):
        super().__init__(label="🛒 Add to Cart", style=discord.ButtonStyle.success)
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        item = shop_items.get(self.item_name)

        if not item:
            await interaction.response.send_message("❌ Item not found.", ephemeral=True)
            return

        cart = user_carts.setdefault(user_id, {})
        current = cart.get(self.item_name, 0)

        if current >= item["stock"]:
            await interaction.response.send_message("❌ Not enough stock left.", ephemeral=True)
            return

        cart[self.item_name] = current + 1
        view = ShopView(self.item_name, user_id=user_id)
        await interaction.response.edit_message(view=view)

class RemoveFromCartButton(Button):
    def __init__(self, item_name):
        super().__init__(label="❌ Remove from Cart", style=discord.ButtonStyle.danger)
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        cart = user_carts.get(user_id, {})
        if self.item_name in cart:
            cart[self.item_name] = max(0, cart[self.item_name] - 1)
            if cart[self.item_name] == 0:
                del cart[self.item_name]
        view = ShopView(self.item_name, user_id=user_id)
        await interaction.response.edit_message(view=view)

class CartCountButton(Button):
    def __init__(self, quantity):
        super().__init__(label=f"In Cart: {quantity}", style=discord.ButtonStyle.primary, disabled=True)

class CheckoutButton(Button):
    def __init__(self):
        super().__init__(label="✅ Click Here To Checkout", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user
        category = get(guild.categories, name="Tickets")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.owner: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }

        channel = await guild.create_text_channel(
            name=f"ticket-{user.name}",
            overwrites=overwrites,
            category=category,
            reason="Checkout Ticket"
        )

        cart = user_carts.get(user.id, {})
        if not cart:
            await channel.send(f"{user.mention}, your cart is empty!")
        else:
            total = 0
            description = ""
            for item_name, qty in cart.items():
                item = shop_items.get(item_name)
                if item:
                    cost = item["price"] * qty
                    total += cost
                    description += f"**{item_name}** — x{qty} (${item['price']} each) = `${cost}`\n"

            embed = discord.Embed(
                title=f"🛒 Order from {user.display_name}",
                description=description + f"\n**Total:** `${total}`",
                color=discord.Color.green()
            )

            close_view = View()
            close_view.add_item(CloseTicketButton(owner_name=OWNER_NAME))

            await channel.send(content=f"{user.mention} <@{guild.owner_id}>", embed=embed, view=close_view)

        await interaction.response.send_message("✅ Your checkout ticket has been created.", ephemeral=True)

class CloseTicketButton(Button):
    def __init__(self, owner_name):
        super().__init__(label="🔒 Close Ticket", style=discord.ButtonStyle.danger)
        self.owner_name = owner_name

    async def callback(self, interaction: discord.Interaction):
        user_tag = f"{interaction.user.name}.{interaction.user.discriminator}"
        if user_tag != self.owner_name:
            await interaction.response.send_message("❌ Only the owner can close tickets.", ephemeral=True)
            return
        await interaction.response.send_message("🕒 Ticket will close in 5 seconds...", ephemeral=True)
        await asyncio.sleep(5)
        await interaction.channel.delete()

# ========== COMMANDS ==========

def is_owner(ctx):
    return f"{ctx.author.name}.{ctx.author.discriminator}" == OWNER_NAME

@bot.command(name="setup")
@commands.check(is_owner)
async def setup_command(ctx):
    global tutorial_msg_id
    if tutorial_msg_id:
        try:
            old_msg = await ctx.channel.fetch_message(tutorial_msg_id)
            await old_msg.delete()
        except:
            pass

    embed = discord.Embed(
        title="🛠️ Shop Bot Setup Guide",
        description=(
            "**Commands:**\n"
            "`!add <name> <image or 'none'> <price> <stock>`\n"
            "`!remove <name>`\n"
            "`!stock <name> <amount>`\n"
            "`!viewcart`\n"
            "`!setcheckout`"
        ),
        color=discord.Color.blue()
    )
    msg = await ctx.send(embed=embed)
    tutorial_msg_id = msg.id

@bot.command(name="add")
@commands.check(is_owner)
async def add_item(ctx, name: str, image: str, price: int, stock: int):
    if name in shop_items:
        await ctx.send("❌ Item with this name already exists.", ephemeral=True)
        return

    embed = discord.Embed(
        title=name,
        description=f"💰 Price: ${price}\n📦 Stock: {stock}",
        color=discord.Color.orange()
    )
    if image.lower() != "none":
        embed.set_image(url=image)

    view = ShopView(name)
    msg = await ctx.send(embed=embed, view=view)

    shop_items[name] = {
        "price": price,
        "stock": stock,
        "image": image,
        "message_id": msg.id,
        "channel_id": msg.channel.id
    }

    await ctx.send(f"✅ Added item `{name}` to shop.", ephemeral=True)

@bot.command(name="remove")
@commands.check(is_owner)
async def remove_item(ctx, name: str):
    item = shop_items.get(name)
    if not item:
        await ctx.send("❌ Item not found.", ephemeral=True)
        return

    try:
        channel = bot.get_channel(item["channel_id"])
        msg = await channel.fetch_message(item["message_id"])
        await msg.delete()
    except:
        pass

    del shop_items[name]
    await ctx.send(f"🗑️ Removed `{name}` from shop.", ephemeral=True)

@bot.command(name="stock")
@commands.check(is_owner)
async def stock_update(ctx, name: str, amount: int):
    item = shop_items.get(name)
    if not item:
        await ctx.send("❌ Item not found.", ephemeral=True)
        return

    item["stock"] = amount
    for cart in user_carts.values():
        if name in cart and cart[name] > amount:
            cart[name] = 0

    try:
        channel = bot.get_channel(item["channel_id"])
        msg = await channel.fetch_message(item["message_id"])
        embed = discord.Embed(
            title=name,
            description=f"💰 Price: ${item['price']}\n📦 Stock: {amount}",
            color=discord.Color.orange()
        )
        if item["image"].lower() != "none":
            embed.set_image(url=item["image"])
        await msg.edit(embed=embed)
    except:
        await ctx.send("⚠️ Failed to update item display.", ephemeral=True)
        return

    await ctx.send(f"✅ Stock of `{name}` updated to {amount}.", ephemeral=True)

@bot.command(name="viewcart")
async def view_cart(ctx):
    user_id = ctx.author.id
    cart = user_carts.get(user_id, {})
    if not cart:
        await ctx.send("🛒 Your cart is empty.", ephemeral=True)
        return

    total = 0
    description = ""
    for item_name, qty in cart.items():
        item = shop_items.get(item_name)
        if item:
            cost = item["price"] * qty
            total += cost
            description += f"**{item_name}** — x{qty} (${item['price']} each) = `${cost}`\n"

    if not description:
        await ctx.send("🛒 Your cart is empty or all items were removed from the shop.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"🛒 {ctx.author.display_name}'s Cart",
        description=description + f"\n**Total:** `${total}`",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed, ephemeral=True)

@bot.command(name="setcheckout")
@commands.check(is_owner)
async def set_checkout(ctx):
    embed = discord.Embed(
        title="🛒 Ready to Checkout?",
        description="When you're finished with your cart, click below to open a private ticket.",
        color=discord.Color.green()
    )
    view = View()
    view.add_item(CheckoutButton())
    await ctx.send(embed=embed, view=view, ephemeral=True)

# ========== ERROR HANDLING ==========

@setup_command.error
@add_item.error
@remove_item.error
@stock_update.error
@set_checkout.error
async def owner_only_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Only the owner can use this command.", ephemeral=True)

# ========== BOT START ==========

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

bot.run(os.getenv("BOT_TOKEN"))
