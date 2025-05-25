import os
import discord
from discord.ext import commands
from discord.ui import Button, View

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# In-memory storage
shop_items = {}         # name -> {price, stock, message_id, image, channel_id}
user_carts = {}         # user_id -> {item_name: quantity}
tutorial_msg_id = None  # Store the ID of the current tutorial message


# =============== VIEWS ===============

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


# =============== PREFIX COMMANDS ===============

@bot.command(name="setup")
async def setup_command(ctx):
    global tutorial_msg_id

    # Delete old tutorial if it exists
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
            "`!add <name> <image or 'none'> <price> <stock>` — Add a shop item\n"
            "`!remove <name>` — Remove an item from the shop\n"
            "`!stock <name> <amount>` — Update an item's stock\n"
            "`!viewcart` — View your cart total and items\n"
            "\n🛒 Use buttons to add/remove items to your cart!"
        ),
        color=discord.Color.blue()
    )
    msg = await ctx.send(embed=embed)
    tutorial_msg_id = msg.id


@bot.command(name="add")
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
async def stock_update(ctx, name: str, amount: int):
    item = shop_items.get(name)
    if not item:
        await ctx.send("❌ Item not found.", ephemeral=True)
        return

    item["stock"] = amount

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
        await ctx.send("⚠️ Failed to update embed.", ephemeral=True)
        return

    await ctx.send(f"✅ Updated stock of `{name}` to {amount}.", ephemeral=True)


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

    embed = discord.Embed(
        title=f"🛒 {ctx.author.display_name}'s Cart",
        description=description + f"\n**Total:** `${total}`",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed, ephemeral=True)


# =============== BOT SETUP ===============

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")


bot.run(os.getenv("BOT_TOKEN"))
