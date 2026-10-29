import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = (
    AsyncOpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1",
                timeout=20.0, max_retries=0)
    if GROQ_API_KEY and GROQ_API_KEY.strip() else None
)


async def close_client():
    if client is not None:
        await client.close()
