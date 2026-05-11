import os
import asyncio
import io
import discord
from discord.ext import commands
from discord import app_commands

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
OWNER_ROLE_ID          = 1501625586055909417
VOUCHER_ADMIN_ROLE_ID  = 1502479901893066772

APP_TICKET_CATEGORY_ID = 1502465878413807747
TRANSCRIPT_CHANNEL_ID  = 1502466244740124764
VOUCH_LOG_CHANNEL_ID   = 1502466039802499304

TARGET_ROLE_ID         = 1502465772138532975   # for /dm command

FOOTER      = "Powered by Brxxks Middleman Service"
FOOTER_HELP = "Powered by Brxxks Helper Bot"

# ─────────────────────────────────────────────
#  BOT SETUP
# ─────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
#  VOUCH STORAGE  (in-memory)
#  vouches[user_id] = list of voucher_ids
# ─────────────────────────────────────────────
vouches: dict[int, list[int]] = {}

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def has_any_role(member: discord.Member, *role_ids: int) -> bool:
    return any(r.id in role_ids for r in member.roles)

def app_overwrites(guild: discord.Guild, opener: discord.Member) -> dict:
    admin_role = guild.get_role(VOUCHER_ADMIN_ROLE_ID)
    owner_role = guild.get_role(OWNER_ROLE_ID)
    ow = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        opener: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    if admin_role:
        ow[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    if owner_role:
        ow[owner_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    return ow

async def make_transcript(channel: discord.TextChannel) -> io.BytesIO:
    lines = []
    async for msg in channel.history(limit=None, oldest_first=True):
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        lines.append(f"[{ts}] {msg.author} ({msg.author.id}): {msg.content}")
        for e in msg.embeds:
            if e.title:       lines.append(f"  [EMBED TITLE] {e.title}")
            if e.description: lines.append(f"  [EMBED DESC]  {e.description}")
            for f in e.fields:
                lines.append(f"  [{f.name}] {f.value}")
    return io.BytesIO("\n".join(lines).encode())

# ─────────────────────────────────────────────
#  APPLICATION TICKET VIEWS
# ─────────────────────────────────────────────
class AppView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open a Ticket", style=discord.ButtonStyle.primary,
                       emoji="📋", custom_id="v:app_open")
    async def open_ticket(self, interaction: discord.Interaction, btn: discord.ui.Button):
        guild = interaction.guild
        cat   = guild.get_channel(APP_TICKET_CATEGORY_ID)
        if cat is None:
            await interaction.response.send_message(
                "❌ Ticket category not found.", ephemeral=True)
            return

        # Check for existing open ticket
        for ch in cat.channels:
            if ch.topic == str(interaction.user.id):
                await interaction.response.send_message(
                    f"You already have an open ticket: {ch.mention}", ephemeral=True)
                return

        ch = await guild.create_text_channel(
            name=f"app-{interaction.user.name}",
            category=cat,
            overwrites=app_overwrites(guild, interaction.user),
            topic=str(interaction.user.id),
        )
        embed = discord.Embed(color=0x2b2d31, title="📋 Application Ticket")
        embed.description = (
            f"{interaction.user.mention}, thank you for reaching out!\n\n"
            "A staff member will be with you shortly.\n\n"
            "If you have any questions, please let a staff member know."
        )
        embed.set_footer(text=FOOTER_HELP)
        await ch.send(
            content=f"<@&{VOUCHER_ADMIN_ROLE_ID}>",
            embed=embed,
            view=CloseOnlyView()
        )
        await interaction.response.send_message(
            f"✅ Ticket created: {ch.mention}", ephemeral=True)


class CloseOnlyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger,
                       emoji="🔒", custom_id="v:app_close")
    async def close(self, interaction: discord.Interaction, btn: discord.ui.Button):
        if not has_any_role(interaction.user, OWNER_ROLE_ID, VOUCHER_ADMIN_ROLE_ID):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        ch  = interaction.channel
        buf = await make_transcript(ch)

        tr_ch = interaction.guild.get_channel(TRANSCRIPT_CHANNEL_ID)
        if tr_ch:
            embed = discord.Embed(color=0x2b2d31, title="📄 Ticket Transcript")
            embed.description = (
                f"**Channel:** `{ch.name}`\n"
                f"**Closed by:** {interaction.user.mention}"
            )
            embed.set_footer(text=FOOTER_HELP)
            await tr_ch.send(
                embed=embed,
                file=discord.File(buf, filename=f"transcript-{ch.name}.txt")
            )

        await interaction.response.send_message("🔒 Closing ticket in 5 seconds…")
        await asyncio.sleep(5)
        await ch.delete()


# ─────────────────────────────────────────────
#  /setup_applications  — Owner only
# ─────────────────────────────────────────────
@bot.tree.command(name="setup_applications", description="Post the Applications embed + button.")
async def setup_applications(interaction: discord.Interaction):
    if not has_any_role(interaction.user, OWNER_ROLE_ID):
        await interaction.response.send_message(
            "❌ Only the Owner can use this command.", ephemeral=True)
        return

    embed = discord.Embed(color=0x2b2d31, title="📋 Applications")
    embed.description = (
        "Welcome to our application information portal!\n\n"
        "This is your hub for learning about opportunities and getting support in our community.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    embed.add_field(
        name="🛡️ Apply for Moderator",
        value=(
            "Interested in becoming a moderator? We're looking for dedicated members to help "
            "keep our community safe and organized. Moderators help manage discussions, enforce "
            "rules, and assist fellow members. If you believe you have what it takes, reach out to leadership!"
        ),
        inline=False
    )
    embed.add_field(
        name="🤝 Apply for Middleman",
        value=(
            "Want to become a trusted middleman? Middlemen facilitate trades and transactions "
            "between users, ensuring safety and fairness. This role requires exceptional judgment, "
            "reliability, and community reputation. Submit your application through the leadership team if interested!"
        ),
        inline=False
    )
    embed.add_field(
        name="❓ Need Help?",
        value=(
            "If you need assistance with anything—whether it's account issues, questions about "
            "rules, or general support—don't hesitate to reach out. Our support team is here to "
            "help and ready to answer your questions!\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        inline=False
    )
    embed.set_footer(text=FOOTER_HELP)
    await interaction.channel.send(embed=embed, view=AppView())
    await interaction.response.send_message("✅ Done!", ephemeral=True)


# ─────────────────────────────────────────────
#  VOUCH SYSTEM
# ─────────────────────────────────────────────
@bot.tree.command(name="vouch", description="Vouch for a user.")
@app_commands.describe(user="The user you want to vouch for.", reason="Reason for vouching (optional).")
async def vouch(interaction: discord.Interaction, user: discord.Member, reason: str = None):
    if user.id == interaction.user.id:
        await interaction.response.send_message(
            "❌ You can't vouch for yourself.", ephemeral=True)
        return
    if user.bot:
        await interaction.response.send_message(
            "❌ You can't vouch for a bot.", ephemeral=True)
        return

    vouches.setdefault(user.id, [])
    if interaction.user.id in vouches[user.id]:
        await interaction.response.send_message(
            f"❌ You've already vouched for {user.mention}.", ephemeral=True)
        return

    vouches[user.id].append(interaction.user.id)
    count = len(vouches[user.id])

    embed = discord.Embed(color=0x57f287, title="✅ Vouch Recorded")
    embed.description = (
        f"{interaction.user.mention} vouched for {user.mention}!\n"
        f"They now have **{count}** vouch{'es' if count != 1 else ''}."
    )
    if reason:
        embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(
        text=f"{FOOTER_HELP} • Today at {discord.utils.utcnow().strftime('%I:%M %p')}")
    await interaction.response.send_message(embed=embed)

    log_ch = interaction.guild.get_channel(VOUCH_LOG_CHANNEL_ID)
    if log_ch:
        log_embed = discord.Embed(color=0x57f287, title="📋 New Vouch")
        log_embed.add_field(name="Vouched User",
                            value=f"{user.mention} (`{user.id}`)", inline=False)
        log_embed.add_field(name="Vouched By",
                            value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        log_embed.add_field(name="Total Vouches", value=str(count), inline=False)
        if reason:
            log_embed.add_field(name="Reason", value=reason, inline=False)
        log_embed.set_footer(
            text=f"{FOOTER_HELP} • Today at {discord.utils.utcnow().strftime('%I:%M %p')}")
        await log_ch.send(embed=log_embed)


@bot.tree.command(name="vouch_add", description="Manually add vouches to a user. (Voucher Admin only)")
@app_commands.describe(user="Target user.", amount="Number of vouches to add.")
async def vouch_add(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not has_any_role(interaction.user, VOUCHER_ADMIN_ROLE_ID):
        await interaction.response.send_message("❌ No permission.", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message(
            "❌ Amount must be greater than 0.", ephemeral=True)
        return

    embed = discord.Embed(color=0x57f287, title="✅ Vouches Added")
    embed.description = f"Added **{amount}** vouch{'es' if amount != 1 else ''} to {user.mention}."
    embed.set_footer(
        text=f"{FOOTER_HELP} • Today at {discord.utils.utcnow().strftime('%I:%M %p')}")
    await interaction.response.send_message(embed=embed)

    log_ch = interaction.guild.get_channel(VOUCH_LOG_CHANNEL_ID)
    if log_ch:
        log_embed = discord.Embed(color=0x57f287, title="📋 Manual Vouches Added")
        log_embed.add_field(name="User",
                            value=f"{user.mention} (`{user.id}`)", inline=False)
        log_embed.add_field(name="Added By",
                            value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        log_embed.add_field(name="Amount Added", value=str(amount), inline=False)
        log_embed.set_footer(
            text=f"{FOOTER_HELP} • Today at {discord.utils.utcnow().strftime('%I:%M %p')}")
        await log_ch.send(embed=log_embed)


@bot.tree.command(name="vouchcount", description="Check vouch count for a user.")
@app_commands.describe(user="The user to check (leave blank to check yourself).")
async def vouchcount(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    count  = len(vouches.get(target.id, []))

    embed = discord.Embed(color=0x2b2d31, title="🔢 Vouch Count")
    embed.description = f"{target.mention} has **{count}** vouch{'es' if count != 1 else ''}."
    if target.avatar:
        embed.set_thumbnail(url=target.avatar.url)
    embed.set_footer(
        text=f"{FOOTER_HELP} • Today at {discord.utils.utcnow().strftime('%I:%M %p')}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="vouchlb", description="Top 10 most vouched users.")
async def vouchlb(interaction: discord.Interaction):
    if not vouches:
        await interaction.response.send_message(
            "No vouches recorded yet.", ephemeral=True)
        return

    sorted_vouches = sorted(
        vouches.items(), key=lambda x: len(x[1]), reverse=True)[:10]

    medals = ["🥇", "🥈", "🥉"]
    lines  = []
    for i, (uid, vlist) in enumerate(sorted_vouches):
        count  = len(vlist)
        prefix = medals[i] if i < 3 else f"**{i + 1}.**"
        member = interaction.guild.get_member(uid)
        name   = member.mention if member else f"<@{uid}>"
        lines.append(f"{prefix} {name} — **{count}** vouch{'es' if count != 1 else ''}")

    total_users = len(vouches)
    embed = discord.Embed(color=0x2b2d31, title="🏆 Vouch Leaderboard — Top 10")
    embed.description = "\n".join(lines)
    embed.set_footer(
        text=f"{total_users} user{'s' if total_users != 1 else ''} with vouches "
             f"• Today at {discord.utils.utcnow().strftime('%I:%M %p')}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="remove_vouches", description="Remove vouches from a user. (Owner only)")
@app_commands.describe(
    user="Target user.",
    amount="Number of vouches to remove. Leave blank to remove all.")
async def remove_vouches(
        interaction: discord.Interaction, user: discord.Member, amount: int = None):
    if not has_any_role(interaction.user, OWNER_ROLE_ID):
        await interaction.response.send_message(
            "❌ Only the Owner can use this command.", ephemeral=True)
        return

    current = vouches.get(user.id, [])
    if not current:
        await interaction.response.send_message(
            f"❌ {user.mention} has no vouches to remove.", ephemeral=True)
        return

    before = len(current)
    if amount is None or amount >= before:
        vouches[user.id] = []
        removed = before
    else:
        vouches[user.id] = current[:-amount]
        removed = amount

    after = len(vouches[user.id])
    embed = discord.Embed(color=0xed4245, title="🗑️ Vouches Removed")
    embed.description = (
        f"Removed **{removed}** vouch{'es' if removed != 1 else ''} from {user.mention}.\n"
        f"They now have **{after}** vouch{'es' if after != 1 else ''}."
    )
    embed.set_footer(
        text=f"{FOOTER_HELP} • Today at {discord.utils.utcnow().strftime('%I:%M %p')}")
    await interaction.response.send_message(embed=embed)


# ─────────────────────────────────────────────#  /dm COMMAND  (from original bot)
# ─────────────────────────────────────────────
async def send_dms(members, message, channel, invoker):
    success = 0
    failed  = 0
    for member in members:
        if member.bot:
            continue
        try:
            await member.send(message)
            success += 1
        except (discord.Forbidden, discord.HTTPException):
            failed += 1
        await asyncio.sleep(1)

    try:
        await channel.send(
            f"{invoker.mention} ✅ DM blast done — **{success}** sent, **{failed}** failed (DMs closed).",
            delete_after=30
        )
    except Exception:
        pass


@bot.tree.command(name="dm", description="Send a DM to all members with the target role.")
@app_commands.describe(message="The message to send.")
async def dm(interaction: discord.Interaction, message: str):
    if not has_any_role(interaction.user, OWNER_ROLE_ID):
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.", ephemeral=True)
        return

    target_role = interaction.guild.get_role(TARGET_ROLE_ID)
    if target_role is None:
        await interaction.response.send_message("❌ Target role not found.", ephemeral=True)
        return

    members = list(target_role.members)
    await interaction.response.send_message(
        f"📨 Sending DMs to **{len(members)}** members in the background… I'll notify you here when done.",
        ephemeral=True
    )
    asyncio.create_task(send_dms(members, message, interaction.channel, interaction.user))


# ─────────────────────────────────────────────
#  STARTUP
# ─────────────────────────────────────────────
@bot.event
async def on_ready():
    bot.add_view(AppView())
    bot.add_view(CloseOnlyView())
    try:
        synced = await bot.tree.sync()
        print(f"✅ Logged in as {bot.user} — synced {len(synced)} command(s).")
    except Exception as e:
        print(f"❌ Failed to sync: {e}")


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN environment variable is not set.")
    bot.run(TOKEN)
