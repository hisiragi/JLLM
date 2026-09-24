import re
import logging

import discord

from discord import app_commands
from discord.ext import commands

from config import MAX_MESSAGE_LENGTH
from services.player import SpeechPlayer
from services.voicevox import (
    VoicevoxClient,
    VoicevoxError,
)


logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"https?://\S+")


def prepare_text(content: str) -> str:
    content = URL_PATTERN.sub(
        "URL省略",
        content,
    )

    content = " ".join(content.split())

    if len(content) > MAX_MESSAGE_LENGTH:
        content = (
            content[:MAX_MESSAGE_LENGTH]
            + "、以下略"
        )

    return content


class ReaderCog(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        voicevox: VoicevoxClient,
    ):
        self.bot = bot
        self.voicevox = voicevox

        self.players: dict[int, SpeechPlayer] = {}

    async def shutdown(self):
        players = list(self.players.values())
        self.players.clear()

        for player in players:
            await player.close()

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message,
    ):
        if message.guild is None:
            return

        if message.author.bot:
            return

        player = self.players.get(
            message.guild.id
        )

        if player is None:
            return

        if message.channel.id != player.text_channel_id:
            return

        if not player.voice_client.is_connected():
            return

        text = prepare_text(
            message.clean_content
        )

        if not text:
            return

        player.enqueue(text)

    @app_commands.command(
        name="join",
        description="ボイスチャンネルに参加して読み上げを開始します",
    )
    @app_commands.guild_only()
    async def join(
        self,
        interaction: discord.Interaction,
    ):
        guild = interaction.guild

        if guild is None:
            return

        member = interaction.user

        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "サーバー内で実行してください。",
                ephemeral=True,
            )
            return

        if member.voice is None or member.voice.channel is None:
            await interaction.response.send_message(
                "先にボイスチャンネルに参加してください。",
                ephemeral=True,
            )
            return

        channel = member.voice.channel

        await interaction.response.defer(
            ephemeral=True,
        )

        player = self.players.get(guild.id)

        try:
            if player is not None:
                voice_client = player.voice_client

                if voice_client.is_connected():
                    if voice_client.channel != channel:
                        await voice_client.move_to(channel)

                    player.text_channel_id = (
                        interaction.channel_id
                    )

                    await interaction.followup.send(
                        "読み上げチャンネルを設定しました。",
                        ephemeral=True,
                    )
                    return

                self.players.pop(guild.id, None)
                await player.close()

            voice_client = guild.voice_client

            if voice_client is not None:
                if voice_client.is_connected():
                    await voice_client.move_to(channel)
                else:
                    await voice_client.disconnect(force=True)
                    voice_client = await channel.connect()
            else:
                voice_client = await channel.connect()

            player = SpeechPlayer(
                voice_client=voice_client,
                voicevox=self.voicevox,
                text_channel_id=interaction.channel_id,
            )

            self.players[guild.id] = player

            await interaction.followup.send(
                (
                    f"{channel.mention} に参加しました。\n"
                    "このテキストチャンネルの投稿を読み上げます。"
                ),
                ephemeral=True,
            )

        except (discord.DiscordException, OSError):
            logger.exception(
                "ボイスチャンネルへの参加に失敗しました。"
            )

            await interaction.followup.send(
                "参加できませんでした。Botの接続・発言権限を確認してください。",
                ephemeral=True,
            )

    @app_commands.command(
        name="leave",
        description="読み上げを停止して退出します",
    )
    @app_commands.guild_only()
    async def leave(
        self,
        interaction: discord.Interaction,
    ):
        guild = interaction.guild

        if guild is None:
            return

        player = self.players.pop(
            guild.id,
            None,
        )

        if player is None:
            await interaction.response.send_message(
                "現在、読み上げを行っていません。",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True,
        )

        await player.close()

        await interaction.followup.send(
            "読み上げを停止して退出しました。",
            ephemeral=True,
        )

    @app_commands.command(
        name="speakers",
        description="利用可能なVOICEVOXの話者を表示します",
    )
    @app_commands.guild_only()
    async def speakers(
        self,
        interaction: discord.Interaction,
    ):
        await interaction.response.defer(
            ephemeral=True,
        )

        try:
            speakers = await self.voicevox.speakers()

        except VoicevoxError:
            await interaction.followup.send(
                "VOICEVOXから話者一覧を取得できませんでした。",
                ephemeral=True,
            )
            return

        lines = []

        for speaker in speakers:
            for style in speaker["styles"]:
                lines.append(
                    f'{style["id"]}: '
                    f'{speaker["name"]} '
                    f'（{style["name"]}）'
                )

        if not lines:
            await interaction.followup.send(
                "利用可能な話者がありません。",
                ephemeral=True,
            )
            return

        result = "\n".join(lines[:25])

        if len(lines) > 25:
            result += "\nほかにも話者があります。"

        await interaction.followup.send(
            result[:1900],
            ephemeral=True,
        )

    @app_commands.command(
        name="speaker",
        description="読み上げに使う話者を変更します",
    )
    @app_commands.describe(
        speaker_id="話者一覧に表示されるスタイルID",
    )
    @app_commands.guild_only()
    async def speaker(
        self,
        interaction: discord.Interaction,
        speaker_id: int,
    ):
        guild = interaction.guild

        if guild is None:
            return

        player = self.players.get(
            guild.id
        )

        if player is None:
            await interaction.response.send_message(
                "先に /join で読み上げを開始してください。",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True,
        )

        try:
            speakers = await self.voicevox.speakers()

        except VoicevoxError:
            await interaction.followup.send(
                "VOICEVOXに接続できませんでした。",
                ephemeral=True,
            )
            return

        selected = None

        for speaker in speakers:
            for style in speaker["styles"]:
                if style["id"] == speaker_id:
                    selected = (
                        f'{speaker["name"]}'
                        f'（{style["name"]}）'
                    )
                    break

            if selected is not None:
                break

        if selected is None:
            await interaction.followup.send(
                "指定された話者IDは存在しません。",
                ephemeral=True,
            )
            return

        player.speaker_id = speaker_id

        await interaction.followup.send(
            f"話者を {selected} に変更しました。",
            ephemeral=True,
        )

    @app_commands.command(
        name="speed",
        description="読み上げ速度を変更します",
    )
    @app_commands.describe(
        value="読み上げ速度（0.5～2.0）",
    )
    @app_commands.guild_only()
    async def speed(
        self,
        interaction: discord.Interaction,
        value: app_commands.Range[float, 0.5, 2.0],
    ):
        guild = interaction.guild

        if guild is None:
            return

        player = self.players.get(
            guild.id
        )

        if player is None:
            await interaction.response.send_message(
                "先に /join で読み上げを開始してください。",
                ephemeral=True,
            )
            return

        player.speed = float(value)

        await interaction.response.send_message(
            f"読み上げ速度を {value:.2f} 倍に変更しました。",
            ephemeral=True,
        )
