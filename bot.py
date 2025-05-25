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

shop_items = {}  # {item_name: {price, stock, image, message_id, channel_id}}
user_carts = {}  # {user_id: {item_name: quantity}}

tutorial_msg_id = None
checkout_msg_id = None

class ShopView(View):
    def __init__(self, item_name, user_id):
        super().__init__(timeout=None)
        self.item_name = item_name
        self.user_id = user_id
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        self.add_item(AddToCartButton(self.item_name, self.user_id))
        self.add_item(RemoveFromCartButton(self.item_name, self.user_id))
        qty = user_carts.get(self.user_id, {}).get(self.item_name, 0)
        self.add_item(CartCountButton(qty))

class AddToCartButton(Button):
    def __init__(self, item_name, user_id):
        super().__init__(label="🛒 Add to Cart", style=discord.ButtonStyle.success)
        self.item_name = item_name
        self.user_id = user_id
        self.lock = asyncio.Lock()

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your shop message.", ephemeral=True)

        await interaction.response.defer()
        async with self.lock:
            cart = user_carts.setdefault(self.user_id, {})
            item = shop_items.get(self.item_name)
            if not item:
                return

            current_qty = cart.get(self.item_name, 0)
            if current_qty >= item["stock"]:
                return

            cart[self.item_name] = current_qty + 1
            await update_shop_message(item, interaction)

class RemoveFromCartButton(Button):
    def __init__(self, item_name, user_id):
        super().__init__(label="❌ Remove from Cart", style=discord.ButtonStyle.danger)
        self.item_name = item_name
        self.user_id = user_id
        self.lock = asyncio.Lock()

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your shop message.", ephemeral=True)

        await interaction.response.defer()
        async with self.lock:
            cart = user_carts.setdefault(self.user_id, {})
            current_qty = cart.get(self.item_name, 0)
            if current_qty > 0:
                cart[self.item_name] = current_qty - 1
                if cart[self.item_name] == 0:
                    del cart[self.item_name]

            item = shop_items.get(self.item_name)
            if item:
                await update_shop_message(item, interaction)

class CartCountButton(Button):
    def __init__(self, quantity):
        super().__init__(label=f"In Cart: {quantity}", style=discord.ButtonStyle.primary, disabled=True)

class CheckoutButton(Button):
    def __init__(self):
        super().__init__(label="✅ Click Here To Checkout", style=discord.ButtonStyle.success)
        self.lock = asyncio.Lock()

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with self.lock:
            user = interaction.user
            guild = interaction.guild

            category = get(guild.categories, name="Tickets")
            if category is None:
                return await interaction.followup.send("⚠️ 'Tickets' category not found on this server.", ephemeral=True)

            cart = user_carts.get(user.id, {})
            filtered_cart = {k: v for k, v in cart.items() if v > 0}
            if not filtered_cart:
                return await interaction.followup.send("🛒 Your cart is empty!", ephemeral=True)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                guild.owner: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            }

            channel = await guild.create_text_channel(
                name=f"ticket-{user.name}",
                overwrites=overwrites,
                category=category,
                reason="User checkout ticket"
            )

            total = 0
            desc = ""
            for item_name, qty in filtered_cart.items():
                item = shop_items.get(item_name)
                if item:
                    cost = item["price"] * qty
                    total += cost
                    desc += f"**{item_name}** — x{qty} (${item['price']} each) = `${cost}`\n"

            embed = discord.Embed(
                title=f"🛒 Order from {user.display_name}",
                description=desc + f"\n**Total:** `${total}`",
                color=discord.Color.green()
            )

            close_view = View(timeout=None)
            close_view.add_item(CloseTicketButton())

            await channel.send(content=f"{user.mention} <@{guild.owner_id}>", embed=embed, view=close_view)
            await interaction.followup.send(f"✅ Checkout ticket created! Check {channel.mention}", ephemeral=True)

class CloseTicketButton(Button):
    def __init__(self):
        super().__init__(label="🔒 Close Ticket", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("🕒 Closing ticket in 5 seconds...", ephemeral=True)
        await asyncio.sleep(5)
        await interaction.channel.delete()

# 🔁 Helper function to update shop message
async def update_shop_message(item, interaction):
    try:
        channel = bot.get_channel(item["channel_id"])
        msg = await channel.fetch_message(item["message_id"])

        embed = discord.Embed(
            title=interaction.message.embeds[0].title,
            description=f"💰 Price: ${item['price']}\n📦 Stock: {item['stock']}",
            color=discord.Color.orange()
        )
        if item['image'].lower() != "none":
            embed.set_image(url=item['image'])

        view = ShopView(item_name=item["message_id"], user_id=interaction.user.id)
        await msg.edit(embed=embed, view=view)
    except Exception as e:
        print(f"[Update Error] {e}")

@bot.command(name="setup")
async def setup(ctx):
    await ctx.message.delete()
    global tutorial_msg_id

    channel = ctx.channel
    if tutorial_msg_id:
        try:
            old_msg = await channel.fetch_message(tutorial_msg_id)
            await old_msg.delete()
        except:
            pass

    embed = discord.Embed(
        title="🛠️ Shop Bot Setup Guide",
        description=(
            "**Commands:**\n"
            "`!add <name> <image or none> <price> <stock>`\n"
            "`!remove <name>`\n"
            "`!stock <name> <amount>`\n"
            "`!viewcart`\n"
            "`!setcheckout`"
        ),
        color=discord.Color.blue()
    )
    msg = await channel.send(embed=embed)
    tutorial_msg_id = msg.id

@bot.command(name="setcheckout")
async def setcheckout(ctx):
    await ctx.message.delete()
    global checkout_msg_id

    channel = ctx.channel
    if checkout_msg_id:
        try:
            old_msg = await channel.fetch_message(checkout_msg_id)
            await old_msg.delete()
        except:
            pass

    embed = discord.Embed(
        title="🛒 Ready to Checkout?",
        description="Click the button below to open a private checkout ticket.",
        color=discord.Color.green()
    )
    view = View(timeout=None)
    view.add_item(CheckoutButton())
    msg = await channel.send(embed=embed, view=view)
    checkout_msg_id = msg.id

@bot.command(name="add")
async def add(ctx, name: str, image: str, price: int, stock: int):
    await ctx.message.delete()

    if name in shop_items:
        return await ctx.send("❌ Item already exists.", delete_after=5)

    embed = discord.Embed(
        title=name,
        description=f"💰 Price: ${price}\n📦 Stock: {stock}",
        color=discord.Color.orange()
    )
    if image.lower() != "none":
        embed.set_image(url=image)

    msg = await ctx.send(embed=embed)
    view = ShopView(name, ctx.author.id)
    await msg.edit(view=view)

    shop_items[name] = {
        "price": price,
        "stock": stock,
        "image": image,
        "message_id": msg.id,
        "channel_id": msg.channel.id
    }

@bot.command(name="remove")
async def remove(ctx, name: str):
    await ctx.message.delete()
    item = shop_items.get(name)
    if not item:
        return await ctx.send("❌ Item not found.", delete_after=5)

    try:
        channel = bot.get_channel(item["channel_id"])
        msg = await channel.fetch_message(item["message_id"])
        await msg.delete()
    except:
        pass

    del shop_items[name]

@bot.command(name="stock")
async def stock(ctx, name: str, amount: int):
    await ctx.message.delete()
    item = shop_items.get(name)
    if not item:
        return await ctx.send("❌ Item not found.", delete_after=5)

    item["stock"] = amount

    for cart in user_carts.values():
        if name in cart and cart[name] > amount:
            cart[name] = amount
            if cart[name] == 0:
                del cart[name]

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
        await ctx.send("⚠️ Failed to update item display.", delete_after=5)

@bot.command(name="viewcart")
async def viewcart(ctx):
    await ctx.message.delete()

    cart = user_carts.get(ctx.author.id, {})
    filtered_cart = {k: v for k, v in cart.items() if v > 0}

    if not filtered_cart:
        return await ctx.send("🛒 Your cart is empty.", delete_after=5)

    total = 0
    desc = ""
    for item_name, qty in filtered_cart.items():
        item = shop_items.get(item_name)
        if item:
            cost = item["price"] * qty
            total += cost
            desc += f"**{item_name}** — x{qty} (${item['price']} each) = `${cost}`\n"

    embed = discord.Embed(
        title=f"🛒 {ctx.author.display_name}'s Cart",
        description=desc + f"\n**Total:** `${total}`",
        color=discord.Color.gold()
    )

    await ctx.send(embed=embed, delete_after=15)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

bot.run(os.getenv("BOT_TOKEN"))
