import os, base64, requests, re
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bs4 import BeautifulSoup

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
STORAGE_CHAT_ID = int(os.getenv("STORAGE_CHAT_ID"))
WORKER_BASE_URL = os.getenv("WORKER_BASE_URL")
IMG_BB_API_KEY = os.getenv("IMG_BB_API_KEY")

bot = Client("AllInOneBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
print("✅ Bot Started...")

# 🧠 Cache to prevent re-processing media group or message
processed_messages = set()

def encode_file_id(file_id):
    return base64.urlsafe_b64encode(file_id.encode()).decode()

def extract_video_link(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        html = r.text
        soup = BeautifulSoup(html, "html.parser")

        vid = soup.find("video")
        if vid:
            src = vid.find("source") or vid
            link = src.get("src") or src.get("data-src")
            if link and ".mp4" in link:
                return link

        meta = soup.find("meta", property="og:video")
        if meta and meta.get("content", "").endswith(".mp4"):
            return meta["content"]

        mp4s = re.findall(r'(https?://[^\s"\']+\.mp4)', html)
        if mp4s:
            return mp4s[0]
    except:
        pass
    return None

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply("👋 Welcome to All in One Bot!\n\n🎥 Send *Video* to get Stream Link\n🖼 Send *Photo* to upload to imgbb\n🔍 Use `/extract <url>` to extract direct .mp4\n\n👑 Admin: @VipNiox", quote=True)

@bot.on_message(filters.command("extract"))
async def extract_handler(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ Use `/extract <url>`", quote=True)
    url = message.command[1]
    await message.reply("🔍 Extracting link...")
    link = extract_video_link(url)
    if link:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("▶️ Watch", url=link)]])
        await message.reply(f"✅ Found:\n{link}", reply_markup=btn)
    else:
        await message.reply("❌ No direct .mp4 found.")

@bot.on_message(filters.media)
async def handle_media(client, message: Message):
    # Prevent loops or duplicate processing
    if message.chat.id == STORAGE_CHAT_ID or message.forward_from_chat:
        return
    if message.media_group_id and message.media_group_id in processed_messages:
        return
    if message.id in processed_messages:
        return

    processed_messages.add(message.id)
    if message.media_group_id:
        processed_messages.add(message.media_group_id)

    if hasattr(message, 'photo') and message.photo:
        # Upload to imgbb
        path = await message.download()
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        os.remove(path)
        r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMG_BB_API_KEY, "image": encoded})
        if r.ok and r.json().get("success"):
            url = r.json()["data"]["url"]
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("📷 View", url=url)]])
            return await message.reply(f"✅ Uploaded:\n{url}", reply_markup=kb)
        return await message.reply("❌ Failed to upload to imgbb.")

    try:
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
            [InlineKeyboardButton("📺 Embed Code", callback_data="get_embed")]
        ]

        await message.reply(
            f"✅ *Link Ready!*\n\n🔗 {stream_link}\n🆔 {file_id}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@bot.on_callback_query()
async def callback_handler(client, cb):
    msg = cb.message
    if not msg.reply_markup:
        return await cb.answer("⛔ Already clicked", show_alert=True)
    await cb.message.edit_reply_markup(None)

    lines = msg.text.splitlines()
    stream = next((x for x in lines if x.startswith("🔗 ")), None)
    fileid = next((x for x in lines if x.startswith("🆔 ")), None)

    stream_link = stream.replace("🔗 ", "") if stream else None
    file_id = fileid.replace("🆔 ", "") if fileid else None

    if cb.data == "get_link" and stream_link:
        await cb.message.reply(stream_link)
    elif cb.data == "get_id" and file_id:
        await cb.message.reply(file_id)
    elif cb.data == "get_embed" and stream_link:
        code = f"""<video controls id="video-id" style="width:100%;">
<source src="{stream_link}" type="video/mp4">
</video>
<script src="https://cdn.fluidplayer.com/v3/current/fluidplayer.min.js"></script>
<script>fluidPlayer("video-id");</script>"""
        fname = f"embed_{cb.from_user.id}.txt"
        with open(fname, "w") as f:
            f.write(code)
        await cb.message.reply_document(fname, caption="📁 Embed Code")
        os.remove(fname)

bot.run()
