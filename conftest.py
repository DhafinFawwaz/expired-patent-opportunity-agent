import os

# LiteLLM fetches a remote model-cost map on import unless told to use its bundled copy.
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
for _name in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"):
    os.environ.pop(_name, None)
