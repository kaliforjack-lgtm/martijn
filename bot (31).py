import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
import os
from flask import Flask
from threading import Thread

# ── Keep-alive (fixes Railway sleeping) ───────────────────────────────────────
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── Bot setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ── Helpers ───────────────────────────────────────────────────────────────────

async def purge_channel(channel: discord.TextChannel, limit: int | None = None) -> int:
    deleted = 0
    try:
        msgs = await channel.purge(limit=limit, bulk=True)
        deleted += len(msgs)
    except discord.HTTPException:
        pass

    async for message in channel.history(limit=limit):
        try:
            await message.delete()
            deleted += 1
            await asyncio.sleep(0.5)
        except discord.HTTPException:
            pass

    return deleted

# ── Events ────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    await bot.tree.sync()
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

# ── Slash commands ────────────────────────────────────────────────────────────

@bot.tree.command(name="clean", description="Delete messages from a single channel.")
@app_commands.describe(
    channel="Target channel (defaults to current channel)",
    limit="Max messages to delete (omit for all)",
)
@app_commands.default_permissions(manage_messages=True)
async def clean(
    interaction: discord.Interaction,
    channel: discord.TextChannel | None = None,
    limit: int | None = None,
):
    target = channel or interaction.channel
    if not isinstance(target, discord.TextChannel):
        await interaction.response.send_message("❌ This only works in text channels.", ephemeral=True)
        return

    if not target.permissions_for(interaction.guild.me).manage_messages:
        await interaction.response.send_message("❌ I need **Manage Messages** in that channel.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    count = await purge_channel(target, limit=limit)
    log.info(f"{interaction.user} cleaned #{target.name} — {count} messages deleted.")
    await interaction.followup.send(f"✅ Deleted **{count}** message(s) from {target.mention}.", ephemeral=True)


@bot.tree.command(name="cleanall", description="Delete messages from EVERY text channel in the server.")
@app_commands.describe(limit="Max messages to delete per channel (omit for all)")
@app_commands.default_permissions(administrator=True)
async def cleanall(interaction: discord.Interaction, limit: int | None = None):
    guild = interaction.guild

    confirm_view = ConfirmView(timeout=30)
    await interaction.response.send_message(
        f"⚠️ **Are you sure?**\n"
        f"This will delete {'all' if limit is None else f'up to {limit}'} messages "
        f"in **every text channel** of **{guild.name}**.\n\nClick **Confirm** within 30 seconds.",
        view=confirm_view,
        ephemeral=True,
    )
    await confirm_view.wait()

    if not confirm_view.confirmed:
        await interaction.edit_original_response(content="❌ Cancelled.", view=None)
        return

    await interaction.edit_original_response(content="🧹 Cleaning all channels… this may take a while.", view=None)

    text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
    total = 0
    results = []

    for ch in text_channels:
        if not ch.permissions_for(guild.me).manage_messages:
            results.append(f"• #{ch.name} — ⛔ no permission")
            continue
        count = await purge_channel(ch, limit=limit)
        total += count
        results.append(f"• #{ch.name} — {count} deleted")

    summary = "\n".join(results)
    report = f"✅ **Clean complete — {total} total messages deleted.**\n\n{summary}"
    if len(report) > 2000:
        report = f"✅ **Clean complete — {total} total messages deleted.**"

    await interaction.edit_original_response(content=report)


@bot.tree.command(name="cleanchannel", description="Clone a channel to wipe ALL history instantly.")
@app_commands.describe(channel="Channel to nuke (defaults to current)")
@app_commands.default_permissions(administrator=True)
async def cleanchannel(
    interaction: discord.Interaction,
    channel: discord.TextChannel | None = None,
):
    target = channel or interaction.channel

    if not isinstance(target, discord.TextChannel):
        await interaction.response.send_message("❌ Text channels only.", ephemeral=True)
        return

    if not target.permissions_for(interaction.guild.me).manage_channels:
        await interaction.response.send_message("❌ I need **Manage Channels** permission.", ephemeral=True)
        return

    confirm_view = ConfirmView(timeout=30)
    await interaction.response.send_message(
        f"⚠️ This will **nuke** {target.mention} by cloning and deleting it. All history will be gone.\n"
        f"Confirm within 30 seconds.",
        view=confirm_view,
        ephemeral=True,
    )
    await confirm_view.wait()

    if not confirm_view.confirmed:
        await interaction.edit_original_response(content="❌ Cancelled.", view=None)
        return

    await interaction.edit_original_response(content="💣 Nuking channel…", view=None)

    new_ch = await target.clone(reason=f"Nuked by {interaction.user}")
    await new_ch.edit(position=target.position)
    await target.delete(reason=f"Nuked by {interaction.user}")
    await new_ch.send(f"💣 Channel nuked by {interaction.user.mention}. Fresh start!", delete_after=10)

@bot.tree.command(name="deletechannels", description="Delete ALL channels in the server.")
@app_commands.default_permissions(administrator=True)
async def deletechannels(interaction: discord.Interaction):
    guild = interaction.guild
 
    confirm_view = ConfirmView(timeout=30)
    await interaction.response.send_message(
        f"⚠️ **Are you sure?**\n"
        f"This will delete **every channel** in **{guild.name}**. This cannot be undone.\n\n"
        f"Click **Confirm** within 30 seconds.",
        view=confirm_view,
        ephemeral=True,
    )
    await confirm_view.wait()
 
    if not confirm_view.confirmed:
        await interaction.edit_original_response(content="❌ Cancelled.", view=None)
        return
 
    await interaction.edit_original_response(content="🗑️ Deleting all channels…", view=None)
 
    deleted = 0
    for channel in guild.channels:
        try:
            await channel.delete(reason=f"Deleted by {interaction.user}")
            deleted += 1
            await asyncio.sleep(0.5)
        except discord.HTTPException:
            pass
 
    log.info(f"{interaction.user} deleted all channels in {guild.name} — {deleted} channels removed.")

# ── Confirmation UI ───────────────────────────────────────────────────────────

class ConfirmView(discord.ui.View):
    def __init__(self, timeout: float = 30):
        super().__init__(timeout=timeout)
        self.confirmed = False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self):
        self.confirmed = False
        self.stop()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("Set the DISCORD_TOKEN environment variable.")
    bot.run(token)
