import os
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
from discord.utils import get

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

shop_items = {}  # {item_name: {price, stock, image, message_id, channel_id}}
user_carts = {}  # {user_id: {item_name: quantity}}

tutorial_msg_id = None
checkout_msg_id = None

# --- Views & Buttons ---

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
            await interaction.response.send_message("This is not your shop message.", ephemeral=True)
            return

        await interaction.response.defer()
        async with self.lock:
            cart = user_carts.setdefault(self.user_id, {})
            item = shop_items.get(self.item_name)
            if not item:
                await interaction.followup.send("❌ Item not found.", ephemeral=True)
                return

            current_qty = cart.get(self.item_name, 0)
            # If adding would exceed stock, set to stock
            if current_qty + 1 > item["stock"]:
                cart[self.item_name] = item["stock"]
            else:
                cart[self.item_name] = current_qty + 1

            await update_shop_message(item, interaction)
            await interaction.followup.send(f"Added 1 {self.item_name} to your cart.", ephemeral=True)


class RemoveFromCartButton(Button):
    def __init__(self, item_name, user_id):
        super().__init__(label="❌ Remove from Cart", style=discord.ButtonStyle.danger)
        self.item_name = item_name
        self.user_id = user_id
        self.lock = asyncio.Lock()

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your shop message.", ephemeral=True)
            return

        await interaction.response.defer()
        async with self.lock:
            cart = user_carts.setdefault(self.user_id, {})
            current_qty = cart.get(self.item_name, 0)
            if current_qty > 0:
                new_qty = current_qty - 1
                # If new quantity is greater than current stock, reset to stock or 0
                item = shop_items.get(self.item_name)
                if item and new_qty > item["stock"]:
                    new_qty = item["stock"]
                if new_qty <= 0:
                    cart.pop(self.item_name, None)
                else:
                    cart[self.item_name] = new_qty

            item = shop_items.get(self.item_name)
            if item:
                await update_shop_message(item, interaction)
            await interaction.followup.send(f"Removed 1 {self.item_name} from your cart.", ephemeral=True)


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
                await interaction.followup.send("⚠️ 'Tickets' category not found on this server.", ephemeral=True)
                return

            cart = user_carts.get(user.id, {})
            filtered_cart = {k: v for k, v in cart.items() if v > 0}
            if not filtered_cart:
                await interaction.followup.send("🛒 Your cart is empty!", ephemeral=True)
                return

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
                    # Clamp quantity to stock if stock changed
                    if qty > item["stock"]:
                        qty = item["stock"]
                        user_carts[user.id][item_name] = qty
                        if qty == 0:
                            del user_carts[user.id][item_name]

                    cost = item["price"] * qty
                    total += cost
                    desc += f"**{item_name}** — x{qty} (${item['price']} each) = `${cost}`\n"

            embed = discord.Embed(
                title=f"🛒 Order from {user.display_name}",
                description=desc + f"\n**Total:** `${total}`",
                color=discord.Color.green()
            )

            view = View(timeout=None)
            view.add_item(ContinueCheckoutButton())
            view.add_item(CancelCheckoutButton())

            await channel.send(content=f"{user.mention} <@{guild.owner_id}>", embed=embed, view=view)
            await interaction.followup.send(f"✅ Checkout ticket created! Check {channel.mention}", ephemeral=True)


class ContinueCheckoutButton(Button):
    def __init__(self):
        super().__init__(label="✅ Continue", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="✅ Thank you! Please wait shortly for an admin to look at your request.", view=None)


class CancelCheckoutButton(Button):
    def __init__(self):
        super().__init__(label="🔙 Back", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("🕒 Canceling and deleting ticket in 5 seconds...", ephemeral=True)
        await asyncio.sleep(5)
        await interaction.channel.delete()


# 🔁 Helper function to update shop message
async def update_shop_message(item, interaction):
    try:
        channel = bot.get_channel(item["channel_id"])
        msg = await channel.fetch_message(item["message_id"])

        embed = discord.Embed(
            title=msg.embeds[0].title if msg.embeds else item["message_id"],
            description=f"💰 Price: ${item['price']}\n📦 Stock: {item['stock']}",
            color=discord.Color.orange()
        )
        if item['image'].lower() != "none":
            embed.set_image(url=item['image'])

        view = ShopView(item_name=item["message_id"], user_id=interaction.user.id)
        await msg.edit(embed=embed, view=view)
    except Exception as e:
        print(f"[Update Error] {e}")


# --- Slash commands ---

@tree.command(name="setup", description="Show shop setup guide")
async def setup(interaction: discord.Interaction):
    global tutorial_msg_id

    channel = interaction.channel
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
            "`/add <name> <image or none> <price> <stock>`\n"
            "`/remove <name>`\n"
            "`/stock <name> <amount>`\n"
            "`/setcheckout`"
        ),
        color=discord.Color.blue()
    )
    msg = await channel.send(embed=embed)
    tutorial_msg_id = msg.id
    await interaction.response.send_message("Setup guide posted!", ephemeral=True)


@tree.command(name="setcheckout", description="Post the checkout button")
async def setcheckout(interaction: discord.Interaction):
    global checkout_msg_id

    channel = interaction.channel
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
    await interaction.response.send_message("Checkout message posted!", ephemeral=True)


@tree.command(name="add", description="Add a shop item")
@app_commands.describe(name="Name of the item", image="Image URL or 'none'", price="Price of the item", stock="Stock amount")
async def add(interaction: discord.Interaction, name: str, image: str, price: int, stock: int):
    if name in shop_items:
        await interaction.response.send_message("❌ Item already exists.", ephemeral=True)
        return

    embed = discord.Embed(
        title=name,
        description=f"💰 Price: ${price}\n📦 Stock: {stock}",
        color=discord.Color.orange()
    )
    if image.lower() != "none":
        embed.set_image(url=image)

    msg = await interaction.channel.send(embed=embed)
    view = ShopView(name, interaction.user.id)
    await msg.edit(view=view)

    shop_items[name] = {
        "price": price,
        "stock": stock,
        "image": image,
        "message_id": msg.id,
        "channel_id": msg.channel.id
    }
    await interaction.response.send_message(f"✅ Added item '{name}' to shop.", ephemeral=True)


@tree.command(name="remove", description="Remove a shop item")
@app_commands.describe(name="Name of the item")
async def remove(interaction: discord.Interaction, name: str):
    item = shop_items.get(name)
    if not item:
        await interaction.response.send_message("❌ Item not found.", ephemeral=True)
        return

    try:
        channel = bot.get_channel(item["channel_id"])
        msg = await channel.fetch_message(item["message_id"])
        await msg.delete()
    except:
        pass

    del shop_items[name]
    await interaction.response.send_message(f"✅ Removed item '{name}' from shop.", ephemeral=True)


@tree.command(name="stock", description="Update stock of an item")
@app_commands.describe(name="Name of the item", amount="New stock amount")
async def stock(interaction: discord.Interaction, name: str, amount: int):
    item = shop_items.get(name)
    if not item:
        await interaction.response.send_message("❌ Item not found.", ephemeral=True)
        return

    item["stock"] = amount

    # Adjust cart quantities if over stock
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
        await interaction.response.send_message("⚠️ Failed to update item display.", ephemeral=True)
        return

    await interaction.response.send_message(f"✅ Stock for '{name}' updated to {amount}.", ephemeral=True)


# --- Bot Events ---

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await tree.sync()  # Sync slash commands on startup


bot.run(os.getenv("BOT_TOKEN"))
