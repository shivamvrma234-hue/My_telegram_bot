import os
import asyncio
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    ChatPermissions,
    ChatPrivileges,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from pyrogram.errors import UserAdminInvalid, PeerIdInvalid, RPCError

# --- Configuration (Read from Render Environment Variables) ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

app = Client("AdminBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Temporary In-Memory Storage for User Warnings
# Schema: {(chat_id, user_id): warning_count}
USER_WARNINGS = {}
MAX_WARNINGS = 3


# --- Helpers ---

async def extract_target_user(client: Client, message: Message):
    """Extract target user from reply or command argument (@username / User ID)."""
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user

    cmd_args = message.command
    if len(cmd_args) > 1:
        target = cmd_args[1]
        try:
            if target.isdigit():
                user = await client.get_users(int(target))
            else:
                user = await client.get_users(target)
            return user
        except Exception:
            return None
    return None


async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    """Check if the command invoker is an admin or creator."""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False


async def can_promote(client: Client, chat_id: int, user_id: int) -> bool:
    """Check if admin has rights to add/promote new admins."""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status == "creator":
            return True
        if member.status == "administrator":
            return getattr(member.privileges, "can_promote_members", False)
        return False
    except Exception:
        return False


# --- Basic & Info Commands ---

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    if message.chat.type.value == "private":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{(await client.get_me()).username}?startgroup=true")]
        ])
        await message.reply(
            "🛡️ **AdminBot is Active!**\n\n"
            "Add me to your group and make me an **Admin** with full permissions to manage your community.",
            reply_markup=kb
        )
    else:
        await message.reply("🛡️ **AdminBot is operational in this group!**")


@app.on_message(filters.command("help"))
async def help_cmd(client: Client, message: Message):
    help_text = (
        "<b>━━━ Moderation Commands ━━━</b>\n"
        "• <code>/ban</code> [user] — Ban a user (Reply or ID/@user)\n"
        "• <code>/unban</code> &lt;ID&gt; — Unban a user\n"
        "• <code>/mute</code> [user] — Mute a user\n"
        "• <code>/unmute</code> &lt;ID&gt; — Unmute a user\n"
        "• <code>/warn</code> [reason] — Warn a user (Auto-ban at 3/3)\n"
        "• <code>/warnings</code> [user] — Check user warnings\n"
        "• <code>/del</code> — Delete replied message\n"
        "• <code>/pin</code> — Pin replied message\n"
        "• <code>/unpin</code> — Unpin replied message\n\n"
        "<b>━━━ Group Management ━━━</b>\n"
        "• <code>/promote</code> [user] — Promote user to admin\n"
        "• <code>/demote</code> [user] — Remove admin privileges"
    )
    await message.reply(help_text)


# --- Moderation Core Commands ---

@app.on_message(filters.command("ban") & filters.group)
async def ban_user(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ You need admin permissions to ban users.")

    user = await extract_target_user(client, message)
    if not user:
        return await message.reply("⚠️ Reply to a user's message or specify `@username` / `User ID`.")

    try:
        await message.chat.ban_member(user.id)
        await message.reply(f"🚫 <b>User Banned:</b> {user.mention} (<code>{user.id}</code>)")
    except RPCError as e:
        await message.reply(f"❌ Failed to ban: <code>{e.MESSAGE}</code>")


@app.on_message(filters.command("unban") & filters.group)
async def unban_user(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ You need admin permissions to unban users.")

    user = await extract_target_user(client, message)
    if not user:
        return await message.reply("⚠️ Reply to a message or pass user ID: <code>/unban &lt;ID&gt;</code>")

    try:
        await message.chat.unban_member(user.id)
        await message.reply(f"✅ <b>User Unbanned:</b> {user.mention}")
    except RPCError as e:
        await message.reply(f"❌ Failed to unban: <code>{e.MESSAGE}</code>")


@app.on_message(filters.command("mute") & filters.group)
async def mute_user(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return

    user = await extract_target_user(client, message)
    if not user:
        return await message.reply("⚠️ Reply to a message or specify user to mute.")

    try:
        await message.chat.restrict_member(user.id, ChatPermissions())
        await message.reply(f"🔇 <b>User Muted:</b> {user.mention}")
    except RPCError as e:
        await message.reply(f"❌ Failed to mute: <code>{e.MESSAGE}</code>")


@app.on_message(filters.command("unmute") & filters.group)
async def unmute_user(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return

    user = await extract_target_user(client, message)
    if not user:
        return await message.reply("⚠️️ Reply to a message or specify user to unmute.")

    try:
        await message.chat.restrict_member(
            user.id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            )
        )
        await message.reply(f"🔊 <b>User Unmuted:</b> {user.mention}")
    except RPCError as e:
        await message.reply(f"❌ Failed to unmute: <code>{e.MESSAGE}</code>")


# --- Warning System ---

@app.on_message(filters.command("warn") & filters.group)
async def warn_user(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return

    user = await extract_target_user(client, message)
    if not user:
        return await message.reply("⚠️️ Reply to a message or specify user to warn.")

    key = (message.chat.id, user.id)
    USER_WARNINGS[key] = USER_WARNINGS.get(key, 0) + 1
    count = USER_WARNINGS[key]

    if count >= MAX_WARNINGS:
        try:
            await message.chat.ban_member(user.id)
            USER_WARNINGS[key] = 0
            await message.reply(f"🚫 <b>Auto-Ban Triggered:</b> {user.mention} reached maximum warnings ({MAX_WARNINGS}/{MAX_WARNINGS}).")
        except RPCError as e:
            await message.reply(f"❌ Warning added, but failed to auto-ban: <code>{e.MESSAGE}</code>")
    else:
        await message.reply(f"⚠️ <b>Warning Added:</b> {user.mention} ({count}/{MAX_WARNINGS})")


@app.on_message(filters.command("warnings") & filters.group)
async def view_warnings(client: Client, message: Message):
    user = await extract_target_user(client, message) or message.from_user
    key = (message.chat.id, user.id)
    count = USER_WARNINGS.get(key, 0)
    await message.reply(f"📊 <b>Warnings for</b> {user.mention}: {count}/{MAX_WARNINGS}")


# --- Delete & Pin Commands ---

@app.on_message(filters.command("del") & filters.group)
async def delete_msg(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return

    if message.reply_to_message:
        await message.reply_to_message.delete()
        await message.delete()
    else:
        await message.reply("⚠️ Reply to the message you want to delete.")


@app.on_message(filters.command("pin") & filters.group)
async def pin_msg(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return

    if message.reply_to_message:
        await message.reply_to_message.pin()
        await message.reply("📌 Message pinned successfully!")
    else:
        await message.reply("⚠️ Reply to a message to pin it.")


@app.on_message(filters.command("unpin") & filters.group)
async def unpin_msg(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return

    if message.reply_to_message:
        await message.reply_to_message.unpin()
        await message.reply("📌 Message unpinned.")
    else:
        await message.chat.unpin_all_messages()
        await message.reply("📌 All pinned messages cleared.")


# --- Admin Promotion & Demotion ---

@app.on_message(filters.command("promote") & filters.group)
async def promote_user(client: Client, message: Message):
    if not await can_promote(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ You do not have permission to promote admins.")

    user = await extract_target_user(client, message)
    if not user:
        return await message.reply("⚠️ Reply to a user or specify `@username` / `User ID` to promote.")

    try:
        await message.chat.promote_member(
            user.id,
            privileges=ChatPrivileges(
                can_delete_messages=True,
                can_restrict_members=True,
                can_invite_users=True,
                can_pin_messages=True,
                can_manage_video_chats=True
            )
        )
        await message.reply(f"⭐ <b>Promoted User:</b> {user.mention}")
    except RPCError as e:
        await message.reply(f"❌ Promotion failed: <code>{e.MESSAGE}</code>")


@app.on_message(filters.command("demote") & filters.group)
async def demote_user(client: Client, message: Message):
    if not await can_promote(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ You do not have permission to demote admins.")

    user = await extract_target_user(client, message)
    if not user:
        return await message.reply("⚠️ Reply to a user or specify `@username` / `User ID` to demote.")

    try:
        await message.chat.promote_member(
            user.id,
            privileges=ChatPrivileges(
                can_delete_messages=False,
                can_restrict_members=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_promote_members=False,
                can_change_info=False
            )
        )
        await message.reply(f"📉 <b>Demoted User:</b> {user.mention}")
    except RPCError as e:
        await message.reply(f"❌ Demotion failed: <code>{e.MESSAGE}</code>")


# --- Main Application Execution ---

if __name__ == "__main__":
    print("🤖 AdminBot worker service starting on Render...")
    app.run()
