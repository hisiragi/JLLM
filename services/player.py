import asyncio
import io
import logging

from dataclasses import dataclass

import discord

from config import (
    DEFAULT_SPEAKER,
    DEFAULT_SPEED,
    MAX_QUEUE_SIZE,
)
from services.voicevox import VoicevoxClient


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpeechItem:
    text: str
    speaker_id: int
    speed: float


class SpeechPlayer:
    def __init__(
        self,
        voice_client: discord.VoiceClient,
        voicevox: VoicevoxClient,
        text_channel_id: int,
    ):
        self.voice_client = voice_client
        self.voicevox = voicevox
        self.text_channel_id = text_channel_id

        self.speaker_id = DEFAULT_SPEAKER
        self.speed = DEFAULT_SPEED

        self.queue: asyncio.Queue[SpeechItem] = (
            asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        )

        self.closed = False
        self.worker = asyncio.create_task(
            self._run()
        )

    def enqueue(self, text: str) -> bool:
        if self.closed:
            return False

        item = SpeechItem(
            text=text,
            speaker_id=self.speaker_id,
            speed=self.speed,
        )

        try:
            self.queue.put_nowait(item)
            return True

        except asyncio.QueueFull:
            logger.warning(
                "読み上げキューが満杯。メッセージを破棄"
            )
            return False

    async def _run(self):
        while True:
            item = await self.queue.get()

            try:
                if not self.voice_client.is_connected():
                    break

                audio = await self.voicevox.synthesize(
                    text=item.text,
                    speaker_id=item.speaker_id,
                    speed=item.speed,
                )

                if not self.voice_client.is_connected():
                    break

                await self._play(audio)

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception(
                    "メッセージの読み上げに失敗"
                )

            finally:
                self.queue.task_done()

    async def _play(self, audio: bytes):
        loop = asyncio.get_running_loop()
        finished = loop.create_future()

        source = discord.FFmpegPCMAudio(
            io.BytesIO(audio),
            pipe=True,
        )

        started = False

        def on_finished(error: Exception | None):
            if finished.done():
                return

            if error is not None:
                finished.set_exception(error)
            else:
                finished.set_result(None)

        def after(error: Exception | None):
            loop.call_soon_threadsafe(
                on_finished,
                error,
            )

        try:
            self.voice_client.play(
                source,
                after=after,
            )

            started = True

            await asyncio.wait_for(
                finished,
                timeout=120,
            )

        except (asyncio.TimeoutError, asyncio.CancelledError):
            if started:
                self.voice_client.stop()

            raise

        finally:
            if not started:
                source.cleanup()

    async def close(self):
        if self.closed:
            return

        self.closed = True

        self.worker.cancel()

        if self.voice_client.is_playing():
            self.voice_client.stop()

        await asyncio.gather(
            self.worker,
            return_exceptions=True,
        )

        if self.voice_client.is_connected():
            await self.voice_client.disconnect(
                force=True
            )
