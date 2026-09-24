import os

from dotenv import load_dotenv


load_dotenv()


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")

VOICEVOX_URL = os.getenv(
    "VOICEVOX_URL",
    "http://127.0.0.1:50021",
).rstrip("/")

DEFAULT_SPEAKER = int(
    os.getenv("DEFAULT_SPEAKER", "3")
)

DEFAULT_SPEED = 1.0

MAX_MESSAGE_LENGTH = 200
MAX_QUEUE_SIZE = 30
