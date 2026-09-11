import logfire
from app.agents.state import AgentState
from app.gateway import portkey_client, extract_cache_status


def generate_node(state: AgentState):
    """
    Synthesizes a response using both Documentation Context AND Conversation History.
    Uses the native Portkey client (not LangChain) so we can read the
    x-portkey-cache-status response header and surface Cache: Hit in the UI.
    """
    query = state["current_query"]

    history_str = ""
    for msg in state["messages"][:-1]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role}: {msg['content']}\n"

    user_msg = state["messages"][-1]["content"] if state["messages"] else ""

    if query == "CONVERSATIONAL":
        logfire.info("Generating conversational response using memory.")
        prompt = f"""
        You are a friendly and helpful Zyro Dynamics HR Assistant.
        Answer the user's latest message using the CONVERSATION HISTORY below.

        CONVERSATION HISTORY:
        {history_str}

        LATEST MESSAGE:
        "{user_msg}"
        """
    else:
        logfire.info("Generating technical RAG response.")
        max_context_chars = 25000
        full_context = ""

        for doc in state["documents"]:
            if len(full_context) + len(doc) < max_context_chars:
                full_context += doc + "\n\n"
            else:
                logfire.warning("Context truncated to fit Groq TPM limits.")
                break

        prompt = f"""
        You are a Senior HR Policy Advisor at Zyro Dynamics.
        Answer the question using the facts and details in the HR POLICY CONTEXT provided.
        Be precise, cite specific policy details (numbers, dates, amounts, document codes), and remain professional.

        CRITICAL GROUNDING & SAFETY RULES:
        1. Answer HR policy questions using the facts stated in the HR POLICY CONTEXT. If an employee asks about a policy for their role or grade (such as ESOP vesting, WFH eligibility, or notice period), explain the general company policy rules found in the context (e.g. ESOP eligibility for L5+ with 4-year vesting and 1-year cliff). For job application inquiries, guide applicants to check the official company website (www.zyrodynamics.com) or reach out to general HR (hr.helpdesk@zyrodynamics.com), followed by the standard onboarding process.
        2. STRICT REFUSAL FOR OUT-OF-SCOPE TOPICS: If the user asks about non-HR topics, competitors or external tools, product/sales comparisons (e.g. ZyroCRM vs Salesforce, Zoho policies, general coding, stock prices, or company financial revenue not in the documents), you MUST decline to answer.
           Polite Refusal: "I cannot answer this question as it is outside the scope of my knowledge. I am specifically designed to assist with Zyro Dynamics internal HR policies, such as leave, compensation, code of conduct, performance reviews, travel, and onboarding."

        HR POLICY CONTEXT:
        {full_context}

        CONVERSATION HISTORY:
        {history_str}

        USER QUESTION:
        "{user_msg}"
        """

    with logfire.span("✍️ LLM Synthesis"):
        try:
            response = portkey_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            content = response.choices[0].message.content
            cache_status = extract_cache_status(response)
            is_cache_hit = cache_status == "HIT"

            if is_cache_hit:
                logfire.info("⚡ Gateway Cache Hit — response served from Portkey cache.")
                plan_update = state["plan"] + ["Cache: Hit ⚡"]
                status = "Cache hit — instant response."
            else:
                logfire.info("✅ Response synthesised via LLM.")
                plan_update = state["plan"]
                status = "Response generated."

            return {
                "final_answer": content,
                "status": status,
                "plan": plan_update,
                "messages": [{"role": "assistant", "content": content}]
            }

        except Exception as e:
            logfire.error(f"LLM Generation failed: {e}")
            raise e