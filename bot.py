import os
import re
import base64
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# Load environment variables
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
STORAGE_CHAT_ID = int(os.getenv("STORAGE_CHAT_ID"))
WORKER_BASE_URL = os.getenv("WORKER_BASE_URL")
IMG_BB_API_KEY = os.getenv("IMG_BB_API_KEY")

# Initialize bot
bot = Client("MarsStreamBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Encode file ID
def encode_file_id(file_id):
    return base64.urlsafe_b64encode(file_id.encode()).decode()

# Extract video link from webpage
def extract_video_link(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        vid = soup.find("video")
        if vid:
            src = vid.find("source") or vid
            link = src.get("src") or src.get("data-src")
            if link and ".mp4" in link:
                return link

        meta = soup.find("meta", property="og:video")
        if meta:
            link = meta.get("content")
            if link and link.endswith(".mp4"):
                return link

        mp4s = re.findall(r'(https?://[^\s"\']+\.mp4)', html)
        if mp4s:
            return mp4s[0]
    except:
        pass
    return None

# /start command
@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply(
        "**👋 Welcome to MARS Stream & Extract Bot!**\n\n"
        "📤 *Send any video, audio, document to get a permanent stream link.*\n"
        "📷 *Send photo to get imgbb upload link.*\n"
        "🔎 *Use `/extract <url>` to get `.mp4` links from websites.*\n\n"
        "_👑 Admin: @VipNiox_",
        quote=True
    )

# /extract command
@bot.on_message(filters.command("extract"))
async def extract_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("❗ Usage: `/extract <url>`", quote=True)
    url = message.command[1]
    await message.reply("🔍 Extracting link ...")
    link = extract_video_link(url)
    if link:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("▶️ Watch", url=link)]])
        await message.reply(f"✅ Found:\n`{link}`", reply_markup=kb)
    else:
        await message.reply("❌ No `.mp4` found. Try a different link.")

# Media handler: stream or imgbb
@bot.on_message(filters.media)
async def handle_media(client, message: Message):
    try:
        # 🖼️ Handle image: upload to imgbb
        if message.photo:
            path = await message.download()
            with open(path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
            upload_url = "https://api.imgbb.com/1/upload"
            res = requests.post(upload_url, data={
                "key": IMG_BB_API_KEY,
                "image": image_data
            })
            os.remove(path)
            if res.status_code == 200 and res.json().get("success"):
                image_url = res.json()["data"]["url"]
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("📷 View Image", url=image_url)]])
                return await message.reply(f"✅ Uploaded to imgbb:\n{image_url}", reply_markup=kb)
            else:
                return await message.reply("❌ Failed to upload image to imgbb.")

        # 🎞️ Video/audio/doc: stream link logic
        sent = await message.forward(STORAGE_CHAT_ID)
        file_id = (
            sent.video.file_id if sent.video else
            sent.document.file_id if sent.document else
            sent.audio.file_id if sent.audio else None
        )
        if not file_id:
            return await message.reply("❌ Unsupported media type.")

        encoded = encode_file_id(file_id)
        stream_link = f"{WORKER_BASE_URL}{encoded}"

        buttons = [
            [
                InlineKeyboardButton("🔗 Copy Stream Link", callback_data="get_link"),
                InlineKeyboardButton("🆔 Copy File ID", callback_data="get_id")
            ],
            [InlineKeyboardButton("📺 Download Embed Code", callback_data="get_embed")]
        ]

        await message.reply(
            f"**✅ Permanent Streaming Link Ready!**\n\n🔗 {stream_link}\n🆔 {file_id}",
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True
        )

    except Exception as e:
        await message.reply(f"❌ Error: {e}")

# Callback button handler
@bot.on_callback_query()
async def callback_handler(client, cb):
    try:
        msg = cb.message
        lines = msg.text.splitlines()
        stream_line = next((l for l in lines if l.startswith("🔗 ")), None)
        fileid_line = next((l for l in lines if l.startswith("🆔 ")), None)
        stream_link = stream_line.replace("🔗 ", "") if stream_line else None
        file_id = fileid_line.replace("🆔 ", "") if fileid_line else None

        if cb.data == "get_link":
            await cb.answer("📋 Stream link copied!", show_alert=True)
            await cb.message.reply(stream_link or "❌ Not found.")

        elif cb.data == "get_id":
            await cb.answer("📋 File ID copied!", show_alert=True)
            await cb.message.reply(file_id or "❌ Not found.")

        elif cb.data == "get_embed" and stream_link:
            await cb.answer("📥 Sending embed code...", show_alert=False)
            embed_code = f"""<video controls id="video-id" style="height: auto; width: 100%;">
  <source src="{stream_link}" type="video/mp4">
</video>
<script src="https://cdn.fluidplayer.com/v3/current/fluidplayer.min.js"></script>
<script>fluidPlayer('video-id');</script>"""
            filename = f"embed_code_{cb.from_user.id}.txt"
            with open(filename, "w") as f:
                f.write(embed_code)
            await cb.message.reply_document(filename, caption="📁 Embed Code")
            os.remove(filename)

    except Exception as e:
        await cb.answer("❌ Callback error", show_alert=True)
        await cb.message.reply(f"⚠️ Error: {e}")

# Run bot
try:
    bot.run()
except Exception as e:
    print(f"Bot crashed: {e}")
