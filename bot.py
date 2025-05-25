import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Temporary in-memory storage
shop_items = {}         # name -> {price, stock, message_id}
user_carts = {}         # user_id -> {item_name: quantity}


# =============== VIEWS ===============

class ShopView(View):
    def __init__(self, item_name):
        super().__init__(timeout=None)
        self.item_name = item_name

    async def update_cart_buttons(self, interaction):
        user_id = interaction.user.id
        cart = user_carts.get(user_id, {})
        quantity = cart.get(self.item_name, 0)

        # Update third button's label
        self.clear_items()
        self.add_item(AddToCartButton(self.item_name))
        self.add_item(RemoveFromCartButton(self.item_name))
        self.add_item(CartCountButton(quantity))

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

        # Stock check
        cart = user_carts.setdefault(user_id, {})
        current = cart.get(self.item_name, 0)

        if current >= item["stock"]:
            await interaction.response.send_message("❌ Not enough stock left.", ephemeral=True)
            return

        cart[self.item_name] = current + 1
        await interaction.response.edit_message(view=ShopView(self.item_name))


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
        await interaction.response.edit_message(view=ShopView(self.item_name))


class CartCountButton(Button):
    def __init__(self, quantity):
        super().__init__(label=f"In Cart: {quantity}", style=discord.ButtonStyle.primary, disabled=True)


# =============== SLASH COMMANDS ===============

@tree.command(name="setup", description="Show tutorial on how to use the bot")
async def setup_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛠️ Bot Setup Tutorial",
        description=(
            "**/add** — Create a shop item\n"
            "**/remove [name]** — Remove an item\n"
            "**/stock [name] [amount]** — Update stock\n"
            "\nClick 🛒 to add to cart, ❌ to remove, 🔵 to see quantity!"
        ),
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="add", description="Add a new shop item")
@app_commands.describe(name="Name of the item", price="Price", stock="Available stock")
async def add_item(interaction: discord.Interaction, name: str, price: int, stock: int):
    if name in shop_items:
        await interaction.response.send_message("❌ Item with this name already exists.", ephemeral=True)
        return

    embed = discord.Embed(
        title=name,
        description=f"💰 Price: ${price}\n📦 Stock: {stock}",
        color=discord.Color.orange()
    )

    view = ShopView(name)
    shop_msg = await interaction.channel.send(embed=embed, view=view)

    shop_items[name] = {
        "price": price,
        "stock": stock,
        "message_id": shop_msg.id
    }

    await interaction.response.send_message(f"✅ Added item `{name}` to shop.", ephemeral=True)


@tree.command(name="remove", description="Remove a shop item by name")
@app_commands.describe(name="Name of the item to remove")
async def remove_item(interaction: discord.Interaction, name: str):
    item = shop_items.get(name)
    if not item:
        await interaction.response.send_message("❌ Item not found.", ephemeral=True)
        return

    try:
        msg = await interaction.channel.fetch_message(item["message_id"])
        await msg.delete()
    except:
        pass  # Ignore if deleted

    del shop_items[name]
    await interaction.response.send_message(f"🗑️ Removed `{name}` from shop.", ephemeral=True)


@tree.command(name="stock", description="Update stock for a shop item")
@app_commands.describe(name="Item name", amount="New stock quantity")
async def stock_update(interaction: discord.Interaction, name: str, amount: int):
    item = shop_items.get(name)
    if not item:
        await interaction.response.send_message("❌ Item not found.", ephemeral=True)
        return

    item["stock"] = amount
    await interaction.response.send_message(f"✅ Updated stock of `{name}` to {amount}.", ephemeral=True)


# =============== BOT SETUP ===============

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")


bot.run("YOUR_BOT_TOKEN")
