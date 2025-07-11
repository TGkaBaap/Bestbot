import os
import re
import base64
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

print("✅ MarsStreamBot launched...")

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
STORAGE_CHAT_ID = int(os.getenv("STORAGE_CHAT_ID"))
WORKER_BASE_URL = os.getenv("WORKER_BASE_URL")
IMG_BB_API_KEY = os.getenv("IMG_BB_API_KEY")

bot = Client("MarsStreamBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def encode_file_id(file_id):
    return base64.urlsafe_b64encode(file_id.encode()).decode()

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

        mp4s = re.findall(r'(https?://[^\s"\']+\\.mp4)', html)
        if mp4s:
            return mp4s[0]
    except:
        pass
    return None

@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply(
        "**👋 Welcome to MARS Stream & Extract Bot!**\n\n"
        "📤 *Send video/audio/document to get stream link.*\n"
        "📷 *Send image to upload to imgbb.*\n"
        "🔍 *Use `/extract <url>` to grab .mp4 links.*\n\n"
        "_👑 Admin: @VipNiox_",
        quote=True
    )

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
        await message.reply("❌ No `.mp4` found.")

@bot.on_message(filters.media)
async def handle_media(client, message: Message):
    if message.chat.id == STORAGE_CHAT_ID:
        return

    try:
        if message.photo:
            path = await message.download()
            with open(path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode()
            os.remove(path)
            res = requests.post("https://api.imgbb.com/1/upload", data={
                "key": IMG_BB_API_KEY,
                "image": encoded
            })
            if res.ok and res.json().get("success"):
                url = res.json()["data"]["url"]
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("📷 View Image", url=url)]])
                return await message.reply(f"✅ Uploaded to imgbb:\n{url}", reply_markup=kb)
            else:
                return await message.reply("❌ imgbb upload failed.")

        sent = await message.forward(STORAGE_CHAT_ID)
        file_id = (
            sent.video.file_id if sent.video else
            sent.document.file_id if sent.document else
            sent.audio.file_id if sent.audio else None
        )
        if not file_id:
            return await message.reply("❌ Unsupported media type.")

        encoded_id = encode_file_id(file_id)
        stream_link = f"{WORKER_BASE_URL}{encoded_id}"

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

@bot.on_callback_query()
async def callback_handler(client, cb):
    try:
        msg = cb.message
        if not msg.reply_markup:
            return await cb.answer("⛔ Already used", show_alert=True)

        lines = msg.text.splitlines()
        stream_line = next((l for l in lines if l.startswith("🔗 ")), None)
        fileid_line = next((l for l in lines if l.startswith("🆔 ")), None)
        stream_link = stream_line.replace("🔗 ", "") if stream_line else None
        file_id = fileid_line.replace("🆔 ", "") if fileid_line else None

        await cb.message.edit_reply_markup(reply_markup=None)

        if cb.data == "get_link":
            if stream_link:
                await cb.message.reply(stream_link)
            return

        elif cb.data == "get_id":
            if file_id:
                await cb.message.reply(file_id)
            return

        elif cb.data == "get_embed" and stream_link:
            embed_code = f"""<video controls id="video-id" style="height: auto; width: 100%;">
  <source src="{stream_link}" type="video/mp4">
</video>
<script src="https://cdn.fluidplayer.com/v3/current/fluidplayer.min.js"></script>
<script>fluidPlayer('video-id');</script>"""
            fname = f"embed_code_{cb.from_user.id}.txt"
            with open(fname, "w") as f:
                f.write(embed_code)
            await cb.message.reply_document(fname, caption="📁 Embed Code")
            os.remove(fname)
            return

    except Exception as e:
        await cb.message.reply(f"⚠️ Callback Error: {e}")

if __name__ == "__main__":
    bot.run()
