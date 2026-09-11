from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from app.config import settings
from app.rag import hybrid, memory

system_template = """You are the virtual assistant of {business}, talking over WhatsApp.

LANGUAGE: Always reply in the same language the user writes in. Detect it from their
message and mirror it, including regional variants. Never switch languages on your own,
never apologise for the language, and never mention this rule. If the language is truly
unclear, use {fallback_language}.

Rules:
- Sound like a person, warm and natural, never like a form letter.
- Be brief. Two or three sentences unless detail is asked for. This is WhatsApp, not email.
- Answer only from the context and the conversation below. When you do not know
  something, say so plainly and offer to put them through to a human on the team.
- Never invent prices, deadlines, availability, stock or contact details.
- No markdown, no bullet lists, no headings. WhatsApp renders them badly.
- Use the person's name if the conversation has revealed it.

Reference documentation:
<context>
{context}
</context>

What you remember from earlier conversations with this contact:
<memory>
{recalled}
</memory>"""

chat_model: ChatOpenAI | None = None


def get_chat() -> ChatOpenAI:
    """Return the shared chat model, creating it on first use."""

    global chat_model

    if chat_model is None:

        options = {
            "model": settings.openai_model,
            "api_key": settings.openai_api_key,
        }

        # Only send temperature when configured, newer models can reject it.
        if settings.openai_temperature is not None:
            options["temperature"] = settings.openai_temperature

        chat_model = ChatOpenAI(**options)

    return chat_model


def build_history(turns: list[dict]) -> list:
    """Convert stored turns into the message objects langchain expects."""

    history = []

    for turn in turns:

        role = turn.get("role", "user")
        content = turn.get("content", "")

        if not content:
            continue

        history.append(AIMessage(content=content) if role == "assistant" else HumanMessage(content=content))

    return history


def format_recalled(documents: list) -> str:
    """Render semantically recalled memories as plain lines."""

    if not documents:
        return "No earlier conversations with this contact."

    return "\n".join(f"- {document.page_content}" for document in documents)


async def answer(chat_id: str, question: str) -> str:
    """Answer one question using hybrid retrieval plus this user's own memory."""

    context = await hybrid.build_context(question)
    recalled = format_recalled(await memory.recall(chat_id, question))
    history = build_history(await memory.recent(chat_id))

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_template),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ]
    )

    chain = prompt | get_chat()

    response = await chain.ainvoke(
        {
            "business": settings.business_name,
            "fallback_language": settings.fallback_language,
            "context": context,
            "recalled": recalled,
            "history": history,
            "question": question,
        }
    )

    return (response.content or "").strip()
