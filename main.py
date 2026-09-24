import discord
from discord.ext import commands

from config import DISCORD_TOKEN, VOICEVOX_URL
from cogs.reader import ReaderCog
from services.voicevox import VoicevoxClient


class VoiceBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

        self.voicevox: VoicevoxClient | None = None

    async def setup_hook(self):
        print("Discord認証完了・初期化開始", flush=True)

        self.voicevox = VoicevoxClient(VOICEVOX_URL)

        await self.add_cog(
            ReaderCog(self, self.voicevox)
        )

        print("コマンド同期開始", flush=True)

        #await self.tree.sync()

        print("コマンド同期完了", flush=True)

    async def on_ready(self):
        print(
            f"Bot起動完了: {self.user}",
            flush=True,
        )

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise SystemExit(
            ".env に DISCORD_TOKEN を設定してください。"
        )

    bot = VoiceBot()
    bot.run(DISCORD_TOKEN)
