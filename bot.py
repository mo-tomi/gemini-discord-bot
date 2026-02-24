import discord
import google.generativeai as genai
import asyncio
import os
from datetime import datetime, timezone, timedelta

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GUILD_ID = int(os.environ["GUILD_ID"])
CHECK_INTERVAL = 3600
REPLY_THRESHOLD_HOURS = 24

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

client = discord.Client(intents=intents)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="""あなたは「手帳持ちの集い」というDiscordサーバーのサポートBotです。
障害者手帳を持つ方々のコミュニティで、温かく寄り添う返信をしてください。
・共感を大切に、押しつけがましくならないように
・長文は避け、シンプルに
・困っていそうなら管理者への相談を促す"""
)

async def generate_reply(message_content: str, channel_name: str) -> str:
    prompt = f"チャンネル「{channel_name}」に以下のメッセージが投稿されましたが、まだ誰も返信していません。温かく返信してください。\n\n「{message_content}」"
    response = model.generate_content(prompt)
    return response.text

async def check_unanswered_messages():
    await client.wait_until_ready()
    guild = client.get_guild(GUILD_ID)

    while not client.is_closed():
        print(f"[{datetime.now()}] 未返信メッセージをチェック中...")
        threshold_time = datetime.now(timezone.utc) - timedelta(hours=REPLY_THRESHOLD_HOURS)

        for channel in guild.text_channels:
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
                        reply_text = await generate_reply(msg.content, channel.name)
                        await msg.reply(reply_text)
                        print(f"  → 返信しました")
                        await asyncio.sleep(2)

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
