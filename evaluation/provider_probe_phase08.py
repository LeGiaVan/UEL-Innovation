from app.agent.llm import LlmMessage, LlmRequest, load_llm
from app.core.config import Settings

try:
    response = load_llm(Settings()).complete(
        LlmRequest(purpose="generate", messages=[LlmMessage(role="user", content="Say hello.")])
    )
    print("provider: ok; response nonempty:", bool(response.text.strip()))
except Exception as exc:
    message = str(exc).casefold()
    category = next(
        (x for x in ("401", "403", "429", "timeout", "connect", "503", "404") if x in message),
        "other",
    )
    print("provider failure:", type(exc).__name__, "category:", category)
