import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from openai import AsyncOpenAI

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL")
VLLM_API_KEY = os.environ.get("VLLM_API_KEY")


def build_specialist_client(base_url: str, api_key: str) -> AsyncOpenAI:
    return AsyncOpenAI(base_url=base_url, api_key=api_key)


class FrontierExtractor:
    def __init__(self, model_name: str, temperature: float = 0.1, max_tokens: int = 4096):
        self._client = ChatAnthropic(
            model=model_name,
            temperature=temperature,
            max_tokens_to_sample=max_tokens,
            max_retries=0
        )
