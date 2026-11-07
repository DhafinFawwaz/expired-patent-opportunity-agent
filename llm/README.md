# freellm

Personal library that sends LangChain / LiteLLM calls to the **best free LLM you can reach right now**:

- **Many providers, many keys.** OpenRouter, Groq, Cerebras, Gemini, Mistral, NVIDIA NIM, Cohere, SambaNova, Hugging Face, Cloudflare, OpenCode Zen, Kilo, Z.ai, Ollama Cloud, plus OVHcloud and LLM7, which work **with no key**. Several keys per provider are supported. A model offered by several providers becomes one group spread over every provider and key that serves it.
- **Ranked by quality.** Ratings come from the public [LMArena text leaderboard](https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset), fetched without a key and cached for 24 h. They are then adjusted by what freellm has seen on your machine: success rate, recent rate limits, bad keys and latency.
- **Best first, automatic fallback.** freellm is built on the [LiteLLM Router](https://docs.litellm.ai/docs/routing). Each ranked model is a priority level (`order`). If a call hits a rate limit, an outage or a bad key, the router moves to the next model, and the failing deployment is benched for 60 s.
- **Live catalog.** The list of free models comes from each provider's own `/models` endpoint, cached for 12 h. OpenRouter free models are detected by price (0). Seed lists are used when a provider can't be listed.
- **Drop-in for LangChain.** You get a normal `BaseChatModel` (`ChatLiteLLMRouter`), so `invoke`, `stream`, `ainvoke`, `bind_tools`, `with_structured_output` and LangGraph all work.

> Free tiers change often. Rate limits and model lists in `providers.yaml` are as documented on 2026-11-07. The live `/models` discovery and the fallback chain are there so that stale entries degrade gracefully instead of breaking.

## 1. Install

```bash
cd llm
uv sync                      # creates llm/.venv
uv run freellm models        # works immediately: keyless OVH + LLM7 models
```

Use it from another project, such as `../example`:

```bash
uv add --editable ../llm     # or: pip install -e ../llm
```

## 2. Add free keys (optional, recommended)

Keys go in **`llm/.env`**. It already exists with every variable empty and is git-ignored. Fill in only the keys you have.

```bash
uv run freellm keys          # which providers are set up + signup links
uv run freellm keys --steps  # step-by-step for each provider
```

Best value for the effort, in order:

| # | Provider | Put key in | Get it here | Effort |
|---|---|---|---|---|
| 1 | Groq | `GROQ_API_KEY` | https://console.groq.com/keys | email, no card |
| 2 | Google AI Studio | `GEMINI_API_KEY` | https://aistudio.google.com/app/apikey | Google login, no card |
| 3 | OpenRouter | `OPENROUTER_API_KEY` | https://openrouter.ai/settings/keys | login, no card (50 free req/day; a one-time $10 top-up raises it to 1000) |
| 4 | Cerebras | `CEREBRAS_API_KEY` | https://cloud.cerebras.ai/ → API Keys | email, no card |
| 5 | NVIDIA NIM | `NVIDIA_API_KEY` | https://build.nvidia.com/settings/api-keys | phone verification |
| 6 | Mistral | `MISTRAL_API_KEY` | https://console.mistral.ai/api-keys | pick the free "Experiment" plan, phone verification |
| 7 | LLM7.io | `LLM7_API_KEY` | https://token.llm7.io | optional; raises limits over keyless |
| … | Cohere, SambaNova, HF, Cloudflare, OpenCode Zen, Kilo, Z.ai, Ollama | see `freellm keys` | | |

**Several keys or accounts for one provider:**

```dotenv
GROQ_API_KEY=gsk_first
GROQ_API_KEY_2=gsk_second
# or: GROQ_API_KEY=gsk_first,gsk_second
```

Real environment variables override `.env`. Set `FREELLM_HOME=/some/dir` to keep `.env` and `.cache/` somewhere else.

## 3. Use it

```python
from freellm import get_chat_model, complete

llm = get_chat_model()  # best free model first, falls back automatically
print(llm.invoke("Explain BM25 in one line").content)

complete("Summarise: ...")  # str -> str
```

Pick a group or a specific model:

```python
get_chat_model("free")  # everything, ranked by quality (default)
get_chat_model("free-tools")  # skips models known NOT to support tool calling
get_chat_model("free-vision")  # models known to accept images
get_chat_model("free-fast")  # ranked by observed latency
get_chat_model("gpt-oss-120b")  # one model, spread over all providers/keys serving it
get_chat_model("groq/openai/gpt-oss-120b")  # one exact provider deployment
```

Tools, structured output and LangGraph:

```python
from langchain_core.tools import tool
from pydantic import BaseModel


@tool
def add(a: int, b: int) -> int:
    "Add two integers."
    return a + b


get_chat_model("free-tools").bind_tools([add]).invoke("add 2 and 3").tool_calls


class Answer(BaseModel):
    city: str


get_chat_model("free-tools").with_structured_output(Answer, method="function_calling").invoke(
    "Capital of France?"
)

from langgraph.prebuilt import create_react_agent  # if you use LangGraph

agent = create_react_agent(get_chat_model("free-tools"), [add])
```

More control:

```python
from freellm import FreeLLM

fl = FreeLLM(
    providers=["groq", "gemini", "openrouter"],  # restrict (default: all usable)
    exclude_models=["gpt-oss-20b"],
    preference="balanced",  # quality | balanced | speed
    top_n=25,  # how far the free* groups fall back
    rating_overrides={"glm-5.3-flash": 1600},  # force your own ranking
)
for m in fl.ranked(tools=True)[:5]:
    print(m.canonical, m.rating, m.providers)
resp = fl.completion([{"role": "user", "content": "hi"}])
print(FreeLLM.served_by(resp))  # provider:model:keyhash
```

## CLI

```
freellm keys [--steps]      provider/key status, signup links and steps
freellm init                create llm/.env (already done)
freellm models [--tools] [--vision] [--pref speed] [--refresh] [--all] [--json]
freellm ping [-n 5]         probe the top models; results feed the ranking
freellm chat "prompt" [-m MODEL]
freellm stats [--reset]
```

## How ranking works

1. **Discover.** For every provider with a key, or with keyless access, freellm reads `GET {api_base}/models` and keeps the free chat models. Non-chat models such as embedding, TTS, whisper, image and guard models are dropped.
2. **Group.** Ids are normalised into token sets. For example, `openai/gpt-oss-120b`, `gpt-oss-120b` and `gpt-oss:120b` become one model, and `Meta-Llama-3_3-70B-Instruct` matches `Llama 3.3 70B Instruct`.
3. **Rate.** Each model gets its LMArena text Elo. Models that aren't on the leaderboard get 1250, which places them below known mid-tier models.
4. **Adjust.** The rating is adjusted using `.cache/stats.json`, which the LiteLLM callbacks record on every call:
   - up to −200 for a poor success rate;
   - −150 for a rate limit in the last 10 minutes;
   - −1000 for a key that failed authentication;
   - with `preference="balanced"` or `"speed"`, a latency penalty.
5. **Route.** Each model becomes one LiteLLM `order` level. All keys and providers for that model share the level, so load is spread across them. On failure the router retries once on another key at the same level, then falls back to the next level.

## Files

```
llm/
  .env                  your keys (git-ignored, all empty by default)
  .env.example          template (committed)
  providers.local.yaml  optional: your own providers/overrides (git-ignored)
  .cache/               discovery, leaderboard and stats cache (git-ignored)
  src/freellm/
    providers.yaml      provider catalog: base URLs, key env vars, signup steps, free filters
    catalog.py          provider loading + /models discovery
    ranking.py          LMArena fetch, id matching, scoring
    stats.py            health stats (LiteLLM callback)
    router.py           FreeLLM: ranking -> LiteLLM Router -> LangChain model
    _anon.py            strips the auth header for keyless providers
    cli.py              `freellm` command
  tests/                offline tests (mocked); `uv run pytest -m live` for real keyless calls
```

## Known limits

- Only the keyless providers (OVH, LLM7) and the keyless model lists (OpenRouter, the LMArena dataset) were tested end to end. Keyed providers are configured from their docs and will be confirmed once you add keys; `freellm ping` shows which ones work.
- Tool-calling support is only known for providers that report it (OpenRouter, LLM7). For others it's assumed, and `free-tools` skips only models known not to support it.
- LLM7's keyless tier isn't documented and may disappear. OVH anonymous allows 2 requests per minute.
- Free tiers can log or train on your prompts (Gemini free tier, Mistral Experiment, OpenRouter for some models). Don't send secrets.
