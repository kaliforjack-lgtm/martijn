import discord
from discord import app_commands, Embed, Color, Interaction, Button
from discord.ext import commands
from discord.ui import View, button
import asyncio
import io
import os
import datetime

TOKEN = os.environ["BOT_TOKEN"]
GUILD_ID = 1437134165106622486

ROLE = {
    "middleman": 1499791087881945098,
}

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
GUILD = discord.Object(id=GUILD_ID)

def has_role(member: discord.Member, role_ids: list) -> bool:
    return any(r.id in role_ids for r in member.roles)

# -------- Mercy View --------
class MercyView(View):
    def __init__(self, target: discord.Member, author: discord.Member):
        super().__init__(timeout=60.0)
        self.target = target
        self.author = author

    @button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message(
                "❌ Only the targeted user can respond.", ephemeral=True
            )

        embed = Embed(
            title="✅ Accepted",
            description=f"{self.target.mention} accepted.",
            color=Color.green(),
            timestamp=datetime.datetime.now()
        )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message(
                "❌ Only the targeted user can respond.", ephemeral=True
            )

        embed = Embed(
            title="❌ Declined",
            description=f"{self.target.mention} declined.",
            color=Color.red(),
            timestamp=datetime.datetime.now()
        )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

# -------- Command --------
@bot.command(name="mercy")
async def mercy(ctx, user: discord.Member = None):
    if user is None:
        return await ctx.send("❌ Mention a user.")

    embed = Embed(
        title="⚠️ Notification",
        description=(
            f"{user.mention}, do you accept?\n"
            "⏳ You have 1 minute."
        ),
        color=Color.red()
    )

    view = MercyView(target=user, author=ctx.author)
    await ctx.send(embed=embed, view=view)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run(TOKEN)
