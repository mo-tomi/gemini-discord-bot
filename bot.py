import discord
from discord import app_commands
from openai import OpenAI
import asyncio
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
GUILD_ID = int(os.environ["GUILD_ID"])

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

deepseek_client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

async def generate_reply(message_content: str) -> str:
    response = deepseek_client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"以下のメッセージに短く返信してください。\n\n「{message_content}」"}
        ],
        max_tokens=200,
    )
    return response.choices[0].message.content

pending_tasks: dict[int, asyncio.Task] = {}

async def delayed_reply(msg: discord.Message):
    await asyncio.sleep(60)
    try:
        print(f"  自動返信: #{msg.channel.name} - {msg.author}: {msg.content[:50]}")
        reply_text = await generate_reply(msg.content)
        await msg.reply(reply_text)
        print(f"  → 返信しました")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"エラー: {e}")

@client.event
async def on_message(msg: discord.Message):
    if msg.author.bot:
        return
    if msg.channel.id in WATCH_CHANNEL_IDS:
        if msg.channel.id in pending_tasks:
            pending_tasks[msg.channel.id].cancel()
        pending_tasks[msg.channel.id] = asyncio.ensure_future(delayed_reply(msg))

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
    guild = discord.Object(id=GUILD_ID)
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)
    print("スラッシュコマンド登録完了")

client.run(DISCORD_TOKEN)
