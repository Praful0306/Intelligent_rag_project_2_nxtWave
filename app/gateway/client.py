import logfire
from portkey_ai import Portkey, createHeaders, PORTKEY_GATEWAY_URL
from langchain_openai import ChatOpenAI

from app.config import settings


# Production gateway config:
#   - Fallback: primary @rag/llama-3.3-70b-versatile → @brag/llama-3.1-8b-instant on failure
#   - Cache: semantic mode (requires Portkey Enterprise — silently falls back to simple on free/starter)
#   - Retry: 2 attempts on rate limit / server error before triggering the fallback target
GATEWAY_CONFIG = {
    "strategy": {"mode": "fallback"},
    "cache": {"mode": "simple"},
    "retry": {
        "attempts": 2,
        "on_status_codes": [429, 503]
    },
    "targets": [
        {"override_params": {"model": f"@{settings.GROQ_SLUG}/{settings.GROQ_MODEL}"}},
        {"override_params": {"model": f"@{settings.GROQ_SLUG_2}/qwen/qwen3.8-27b"}},
    ]
}

from openai import OpenAI

if settings.PORTKEY_API_KEY:
    _raw_portkey = Portkey(api_key=settings.PORTKEY_API_KEY)

    class PortkeyClientWrapper:
        def __init__(self, raw_client, default_model: str, fallback_model: str):
            self._client = raw_client
            self.default_model = default_model
            self.fallback_model = fallback_model

        class _Chat:
            def __init__(self, parent):
                self.completions = parent._Completions(parent)

        class _Completions:
            def __init__(self, parent):
                self.parent = parent

            def create(self, **kwargs):
                if "model" not in kwargs or not kwargs["model"]:
                    kwargs["model"] = self.parent.default_model
                if "max_tokens" not in kwargs:
                    kwargs["max_tokens"] = 800
                try:
                    return self.parent._client.chat.completions.create(**kwargs)
                except Exception as e:
                    logfire.warning(f"⚠️ Primary model {kwargs.get('model')} failed ({e}). Falling back to {self.parent.fallback_model}...")
                    kwargs["model"] = self.parent.fallback_model
                    return self.parent._client.chat.completions.create(**kwargs)

        @property
        def chat(self):
            return self._Chat(self)

    portkey_client = PortkeyClientWrapper(
        _raw_portkey,
        default_model=f"@{settings.GROQ_SLUG}/{settings.GROQ_MODEL}",
        fallback_model=f"@{settings.GROQ_SLUG}/qwen/qwen3.8-27b"
    )
else:
    class DirectGroqCompletions:
        def __init__(self, openai_client: OpenAI, default_model: str):
            self._client = openai_client
            self.default_model = default_model

        def create(self, **kwargs):
            if "model" not in kwargs or not kwargs["model"] or str(kwargs["model"]).startswith("@"):
                kwargs["model"] = self.default_model
            return self._client.chat.completions.create(**kwargs)

    class DirectGroqChat:
        def __init__(self, completions: DirectGroqCompletions):
            self.completions = completions

    class DirectGroqClient:
        def __init__(self, api_key: str, default_model: str):
            self._client = OpenAI(api_key=api_key or "missing", base_url="https://api.groq.com/openai/v1")
            self.chat = DirectGroqChat(DirectGroqCompletions(self._client, default_model))

    portkey_client = DirectGroqClient(
        api_key=settings.GROQ_API_KEY,
        default_model=settings.GROQ_MODEL
    )


def get_langchain_llm(feature: str = "rag"):
    """
    Returns a Portkey-backed ChatOpenAI with automatic fallback to qwen/qwen3.8-27b,
    or falls back to direct Groq when PORTKEY_API_KEY is absent.
    """
    if settings.PORTKEY_API_KEY:
        primary = ChatOpenAI(
            api_key=settings.PORTKEY_API_KEY,
            base_url=PORTKEY_GATEWAY_URL,
            model=f"@{settings.GROQ_SLUG}/{settings.GROQ_MODEL}",
            max_tokens=800,
            temperature=0,
            default_headers=createHeaders(
                api_key=settings.PORTKEY_API_KEY,
                metadata={
                    "feature": feature,
                    "_user": "rag-system",
                    "environment": "production"
                }
            )
        )
        fallback = ChatOpenAI(
            api_key=settings.PORTKEY_API_KEY,
            base_url=PORTKEY_GATEWAY_URL,
            model=f"@{settings.GROQ_SLUG}/qwen/qwen3.8-27b",
            max_tokens=800,
            temperature=0,
            default_headers=createHeaders(
                api_key=settings.PORTKEY_API_KEY,
                metadata={
                    "feature": f"{feature}_fallback",
                    "_user": "rag-system",
                    "environment": "production"
                }
            )
        )
        return primary.with_fallbacks([fallback])
    else:
        return ChatOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            model=settings.GROQ_MODEL,
            max_tokens=800,
            temperature=0
        )

def extract_cache_status(response) -> str:
    """
    Pull x-portkey-cache-status from the Portkey native client response headers.
    Tries multiple attribute paths defensively — returns 'MISS' if not found.
    """
    for attr in ("_raw_response", "_response", "_http_response"):
        raw = getattr(response, attr, None)
        if raw is not None:
            status = getattr(raw, "headers", {}).get("x-portkey-cache-status", "")
            if status:
                return status.upper()
    return "MISS"