import os
from typing import Final

# LiteLLM otherwise downloads its price list at import; free models report zero cost anyway.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

__version__: Final[str] = "0.1.0"
