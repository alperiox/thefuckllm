"""Model management and lazy loading."""

import os
from functools import lru_cache
from typing import Literal

from huggingface_hub import hf_hub_download
from llama_cpp import Llama
from platformdirs import user_cache_dir

ModelQuantization = Literal["q4_k_m", "q8_0"]

CACHE_DIR = user_cache_dir("thefuckllm")
MODEL_FILES = {
    "q4_k_m": "qwen2.5-coder-3b-instruct-q4_k_m.gguf",
    "q8_0": "qwen2.5-coder-3b-instruct-q8_0.gguf",
}


def ensure_model(quantization: ModelQuantization = "q8_0") -> str:
    """Download model if needed, return path."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    filename = MODEL_FILES[quantization]
    model_path = os.path.join(CACHE_DIR, filename)

    if not os.path.exists(model_path):
        print(f"Downloading {filename}...")
        hf_hub_download(
            repo_id="Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
            filename=filename,
            local_dir=CACHE_DIR,
        )
    return model_path


@lru_cache(maxsize=1)
def get_llm(quantization: ModelQuantization = "q8_0") -> Llama:
    """Get cached LLM instance (singleton pattern)."""
    model_path = ensure_model(quantization)
    return Llama(
        model_path=model_path,
        n_ctx=32768,
        n_gpu_layers=-1,
        verbose=False,
    )


def clear_model_cache() -> None:
    """Clear the cached model to free memory."""
    get_llm.cache_clear()
