import os
import re
import base64
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
STORAGE_CHAT_ID = int(os.getenv("STORAGE_CHAT_ID"))
WORKER_BASE_URL = os.getenv("WORKER_BASE_URL")

bot = Client("MergedBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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

        mp4s = re.findall(r'(https?://[^\s"\']+\.mp4)', html)
        if mp4s:
            return mp4s[0]

    except:
        pass
    return None

@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply(
        "**👋 Welcome to the MultiTool Bot!**\n\n"
        "**🔹 Media to Stream Link:**\n"
        "Send any Telegram media (video, doc, audio, photo).\n\n"
        "**🔹 Extract `.mp4` from Websites:**\n"
        "Use: `/extract <url>`\n\n"
        "Enjoy permanent hosting & link extraction!",
        quote=True
    )

@bot.on_message(filters.command("extract"))
async def extract_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("❗ Provide a URL!\nUsage: `/extract <url>`", quote=True)
    url = message.command[1]
    await message.reply("🔍 Extracting link ...")
    link = extract_video_link(url)
    if link:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("▶️ Watch", url=link),
            InlineKeyboardButton("📋 Copy", url=f"https://copylink.dev/?url={link}")
        ]])
        await message.reply(f"✅ Found:\n`{link}`", reply_markup=kb)
    else:
        await message.reply("❌ No `.mp4` found. Try a different page.")

@bot.on_message(filters.media)
async def handle_media(client, message: Message):
    try:
        sent = await message.forward(STORAGE_CHAT_ID)

        file_id = (
            sent.video.file_id if sent.video else
            sent.document.file_id if sent.document else
            sent.audio.file_id if sent.audio else
            sent.photo.file_id if sent.photo else None
        )

        if not file_id:
            return await message.reply("❌ Unsupported media type.")

        encoded = encode_file_id(file_id)
        stream_link = f"{WORKER_BASE_URL}{encoded}"

        stream_line = f"🔗 {stream_link}"
        fileid_line = f"🆔 {file_id}"

        buttons = [
            [
                InlineKeyboardButton("🔗 Copy Stream Link", callback_data="get_link"),
                InlineKeyboardButton("🆔 Copy File ID", callback_data="get_id")
            ],
            [InlineKeyboardButton("📺 Download Embed Code", callback_data="get_embed")]
        ]

        await message.reply(
            f"**✅ Permanent Streaming Link Ready!**\n\n{stream_line}\n{fileid_line}",
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True
        )

    except Exception as e:
        await message.reply(f"❌ Error: {e}")

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
            if stream_link:
                await cb.answer("📋 Stream link copied!", show_alert=True)
                await cb.message.reply(stream_link)
            else:
                await cb.message.reply("❌ Stream link not found.")

        elif cb.data == "get_id":
            if file_id:
                await cb.answer("📋 File ID copied!", show_alert=True)
                await cb.message.reply(file_id)
            else:
                await cb.message.reply("❌ File ID not found.")

        elif cb.data == "get_embed":
            if not stream_link:
                return await cb.message.reply("❌ Can't generate embed code, stream link missing.")

            await cb.answer("📥 Sending embed code file...", show_alert=False)

            embed_code = f"""<video controls id="video-id" style="height: auto; width: 100%;">
  <source src="{stream_link}" type="video/mp4">
</video>

<script src="https://cdn.fluidplayer.com/v3/current/fluidplayer.min.js"></script>
<script>
  var myFP = fluidPlayer('video-id', {{
    layoutControls: {{
      controlBar: {{
        autoHideTimeout: 3,
        animated: true,
        autoHide: true
      }},
      htmlOnPauseBlock: {{
        html: null,
        height: null,
        width: null
      }},
      autoPlay: false,
      mute: false,
      allowTheatre: false,
      playPauseAnimation: true,
      playbackRateEnabled: false,
      allowDownload: false,
      playButtonShowing: true,
      fillToContainer: true,
      posterImage: ""
    }},
    vastOptions: {{
      adList: [],
      adCTAText: false,
      adCTATextPosition: ""
    }}
  }});
</script>"""

            filename = f"embed_code_{cb.from_user.id}.txt"
            with open(filename, "w") as f:
                f.write(embed_code)

            await cb.message.reply_document(filename, caption="📁 Fluid Player Embed Code")
            os.remove(filename)

    except Exception as e:
        await cb.answer("❌ Callback error", show_alert=True)
        await cb.message.reply(f"⚠️ Error: {e}")

bot.run()
