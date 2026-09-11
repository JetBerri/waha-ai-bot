from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from app.config import settings
from app.rag import hybrid, memory

system_template = """Eres el asistente virtual de {business}. Hablas por WhatsApp.

Reglas:
- Responde siempre en {language}, de forma natural y cercana, como una persona.
- Sé breve: dos o tres frases salvo que te pidan detalle. Esto es WhatsApp, no un email.
- Responde solo con la información del contexto y de la conversación. Si no la tienes,
  dilo con naturalidad y ofrece poner en contacto con una persona del equipo.
- No inventes precios, plazos, disponibilidad ni datos de contacto.
- No uses markdown ni listas con viñetas, WhatsApp no las renderiza bien.
- Trata al usuario por su nombre si lo conoces por la conversación.

Documentación disponible:
<context>
{context}
</context>

Lo que recuerdas de conversaciones anteriores con este usuario:
<memory>
{recalled}
</memory>"""

chat_model: ChatOpenAI | None = None


def get_chat() -> ChatOpenAI:
    """Return the shared chat model, creating it on first use."""

    global chat_model

    if chat_model is None:

        chat_model = ChatOpenAI(
            model=settings.openai_model,
            temperature=settings.openai_temperature,
            api_key=settings.openai_api_key,
        )

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
        return "Es la primera vez que hablas con este usuario."

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
            "language": settings.bot_language,
            "context": context,
            "recalled": recalled,
            "history": history,
            "question": question,
        }
    )

    return (response.content or "").strip()
