import logfire
from langchain_openai import ChatOpenAI
from nemoguardrails import RailsConfig, LLMRails

from app.config import settings
from app.guardrails.colang_rules import COLANG_CONTENT, YAML_CONTENT, RAIL_INDICATORS


_rails: LLMRails | None = None


from app.gateway.client import get_langchain_llm


def initialize_rails() -> None:
    """
    Build the NeMo LLMRails singleton at app startup.
    Uses Portkey gateway LLM for intent classification at the gate.
    """
    global _rails

    guard_llm = get_langchain_llm("guardrails")

    config = RailsConfig.from_content(
        colang_content=COLANG_CONTENT,
        yaml_content=YAML_CONTENT
    )

    _rails = LLMRails(config, llm=guard_llm)
    logfire.info("🛡️ NeMo Guardrails initialised with Gateway LLM.")
    
    


def guard(message: str) -> tuple[bool, str | None]:
    """
    Run a user message through the NeMo rails gate.

    Returns:
        (True,  rail_response) — a rail fired; return this response immediately,
                                skip the RAG pipeline entirely.
        (False, None)          — message is clean; proceed to LangGraph.
    """
    if _rails is None:
        logfire.warning("⚠️ Guardrails not initialised — skipping gate.")
        return False, None

    with logfire.span("🛡️ Guardrails Check"):
        result = _rails.generate(messages=[{"role": "user", "content": message}])

        # NeMo returns {'role': 'assistant', 'content': '...'} — extract text
        content = result.get("content", "") if isinstance(result, dict) else str(result)
        normalized = content.replace("’", "'").replace("‘", "'").lower()

        is_refusal = any(
            phrase in normalized
            for phrase in (
                "can't help with that",
                "cannot help with that",
                "cannot answer this question",
                "outside the scope",
                "outside of my",
                "i'm sorry, but i can't",
                "i am sorry, but i cannot",
                "consistent guidelines",
                "only help with company hr policies",
                "specifically designed to assist with zyro dynamics",
                "can only provide information",
                "only provide information about zyro dynamics",
                "don't have access to zoho",
                "do not have access to zoho",
            )
        )

        fired = is_refusal or any(indicator.lower() in normalized for indicator in RAIL_INDICATORS)

        if fired:
            logfire.info(f"🛡️ Guardrails fired | query='{message[:80]}'")
            if is_refusal:
                return True, (
                    "I cannot answer this question as it is outside the scope of my knowledge. "
                    "I am specifically designed to assist with Zyro Dynamics internal HR policies, "
                    "such as leave, compensation, code of conduct, performance reviews, travel, and onboarding."
                )
            return True, content

        logfire.info("✅ Guardrails passed.")
        return False, None
