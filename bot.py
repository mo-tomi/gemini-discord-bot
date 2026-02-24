import discord
from discord import app_commands
from groq import Groq
import asyncio
import os
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GUILD_ID = int(os.environ["GUILD_ID"])

# 自動返信するチャンネルIDのリスト
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

# ヘルスチェック用サーバー
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
intents.messages = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
groq_client = Groq(api_key=GROQ_API_KEY)

# チャンネルごとの最新メッセージIDを管理
latest_message: dict[int, int] = {}

async def generate_reply(message_content: str) -> str:
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"以下のメッセージに短く返信してください。\n\n「{message_content}」"}
        ],
        max_tokens=200,
    )
    return response.choices[0].message.content

async def delayed_reply(msg: discord.Message):
    """1分待って、その間新しいメッセージがなければ返信する"""
    await asyncio.sleep(60)

    # 1分後に最新メッセージが自分かどうか確認
    if latest_message.get(msg.channel.id) == msg.id:
        try:
            print(f"  自動返信: #{msg.channel.name} - {msg.author}: {msg.content[:50]}")
            reply_text = await generate_reply(msg.content)
            await msg.reply(reply_text)
            print(f"  → 返信しました")
        except Exception as e:
            print(f"エラー: {e}")

@client.event
async def on_message(msg: discord.Message):
    if msg.author.bot:
        return

    # 自動返信対象チャンネルの場合
    if msg.channel.id in WATCH_CHANNEL_IDS:
        latest_message[msg.channel.id] = msg.id
        asyncio.ensure_future(delayed_reply(msg))

# スラッシュコマンド /ai
@tree.command(name="ai", description="てちょうAIに話しかける")
@app_commands.describe(message="AIへのメッセージ")
async def ai_command(interaction: discord.Interaction, message: str):
    await interaction.response.defer()
    try:
        reply_text = await generate_reply(message)
        await interaction.followup.send(f"{reply_text}")
    except Exception as e:
        await interaction.followup.send(f"エラーが発生しました: {e}")

@client.event
async def on_ready():
    print(f"Bot起動: {client.user}")
    # スラッシュコマンドをサーバーに登録
    guild = discord.Object(id=GUILD_ID)
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)
    print("スラッシュコマンド登録完了")

client.run(DISCORD_TOKEN)
