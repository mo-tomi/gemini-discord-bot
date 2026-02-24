import discord
from google import genai
from google.genai import types
import asyncio
import os
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GUILD_ID = int(os.environ["GUILD_ID"])
CHECK_INTERVAL = 3600
REPLY_THRESHOLD_HOURS = 24

WATCH_CHANNEL_IDS = [
    1300764527109079071,
]

SYSTEM_PROMPT = """あなたは「手帳持ちの集い」というDiscordサーバーのサポートBotです。
以下のルールを必ず守ってください：
・返信は短く、1〜3文以内にまとめる
・どんなにネガティブな内容でも、ポジティブで中立な視点で返す
・共感を示しつつ、押しつけがましくならない
・断定や否定はせず、当たり障りのない温かい言葉を選ぶ
・絵文字は使わない"""

# ヘルスチェック用サーバー（先に起動する）
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

health_server = HTTPServer(("0.0.0.0", 8000), HealthHandler)
threading.Thread(target=health_server.serve_forever, daemon=True).start()
print("ヘルスチェックサーバー起動: port 8000")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

client = discord.Client(intents=intents)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

async def generate_reply(message_content: str) -> str:
    response = gemini_client.models.generate_content(
        model="gemini-2.0-flash-lite",  # 無料枠が多いモデルに変更
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        contents=f"以下のメッセージに短く返信してください。\n\n「{message_content}」"
    )
    return response.text

async def check_unanswered_messages():
    await client.wait_until_ready()
    guild = client.get_guild(GUILD_ID)

    while not client.is_closed():
        print(f"[{datetime.now()}] 未返信メッセージをチェック中...")
        threshold_time = datetime.now(timezone.utc) - timedelta(hours=REPLY_THRESHOLD_HOURS)

        for channel in guild.text_channels:
            if channel.id not in WATCH_CHANNEL_IDS:
                continue

            try:
                async for msg in channel.history(limit=50, after=threshold_time, oldest_first=True):
                    if msg.author.bot:
                        continue

                    has_reply = False
                    async for reply in channel.history(limit=20, after=msg):
                        if reply.reference and reply.reference.message_id == msg.id:
                            has_reply = True
                            break

                    if not has_reply and msg.content:
                        print(f"  未返信: #{channel.name} - {msg.author}: {msg.content[:50]}")
                        reply_text = await generate_reply(msg.content)
                        await msg.reply(reply_text)
                        print(f"  → 返信しました")
                        await asyncio.sleep(5)

            except discord.Forbidden:
                continue
            except Exception as e:
                print(f"エラー: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

@client.event
async def on_ready():
    print(f"Bot起動: {client.user}")
    client.loop.create_task(check_unanswered_messages())

client.run(DISCORD_TOKEN)
