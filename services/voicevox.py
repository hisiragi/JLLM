import asyncio

import aiohttp


class VoicevoxError(Exception):
    pass


class VoicevoxClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=90)
        )

    async def close(self):
        await self.session.close()

    async def speakers(self) -> list[dict]:
        try:
            async with self.session.get(
                f"{self.base_url}/speakers"
            ) as response:
                response.raise_for_status()
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise VoicevoxError(
                "話者一覧を取得する際にError"
            ) from exc

    async def synthesize(
        self,
        text: str,
        speaker_id: int,
        speed: float = 1.0,
    ) -> bytes:
        try:
            async with self.session.post(
                f"{self.base_url}/audio_query",
                params={
                    "text": text,
                    "speaker": speaker_id,
                },
            ) as response:
                response.raise_for_status()
                query = await response.json()

            query["speedScale"] = speed

            async with self.session.post(
                f"{self.base_url}/synthesis",
                params={"speaker": speaker_id},
                json=query,
            ) as response:
                response.raise_for_status()
                return await response.read()

        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise VoicevoxError(
                "音声合成でError"
            ) from exc
