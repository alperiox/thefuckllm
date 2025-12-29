"""Configuration management for thefuckllm."""

import os
import tomllib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

import tomli_w
from platformdirs import user_config_dir


class ProviderType(str, Enum):
    """Supported LLM providers."""

    LOCAL = "local"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"


# Environment variable names for API keys
API_KEY_ENV_VARS = {
    ProviderType.OPENAI: "OPENAI_API_KEY",
    ProviderType.ANTHROPIC: "ANTHROPIC_API_KEY",
    ProviderType.GEMINI: "GEMINI_API_KEY",
    ProviderType.OPENROUTER: "OPENROUTER_API_KEY",
}

# Default models per provider
DEFAULT_MODELS = {
    ProviderType.LOCAL: "q8_0",
    ProviderType.OPENAI: "gpt-4o-mini",
    ProviderType.ANTHROPIC: "claude-sonnet-4-20250514",  # Claude 4 Sonnet
    ProviderType.GEMINI: "gemini-1.5-flash",
    ProviderType.OPENROUTER: "openrouter/openai/gpt-4o-mini",
}

# Static aliases for convenience - these are always available
# Map short names to LiteLLM model identifiers
# See: https://docs.litellm.ai/docs/providers/anthropic
MODEL_ALIASES = {
    # OpenAI aliases
    "4o": "gpt-4o",
    "4o-mini": "gpt-4o-mini",
    "gpt4": "gpt-4",
    "gpt4o": "gpt-4o",
    "turbo": "gpt-4-turbo",
    "3.5": "gpt-3.5-turbo",
    # Anthropic aliases - Claude 4 series
    "sonnet": "claude-sonnet-4-20250514",
    "sonnet-4": "claude-sonnet-4-20250514",
    "claude-sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-20250514",
    "opus-4": "claude-opus-4-20250514",
    "claude-opus": "claude-opus-4-20250514",
    # Anthropic aliases - Claude 3.5/3.7 series
    "sonnet-3.5": "claude-3-5-sonnet-20240620",
    "sonnet-3.7": "claude-3-7-sonnet-20250219",
    "haiku": "claude-3-haiku-20240307",
    "claude-haiku": "claude-3-haiku-20240307",
    "opus-3": "claude-3-opus-20240229",
    # Gemini aliases
    "gemini": "gemini-1.5-flash",
    "gemini-flash": "gemini-1.5-flash",
    "gemini-pro": "gemini-1.5-pro",
    "gemini-2": "gemini-2.0-flash-exp",
    "flash": "gemini-1.5-flash",
    # Local aliases
    "q4": "q4_k_m",
    "q8": "q8_0",
}


def resolve_model_alias(model: str) -> str:
    """Resolve a model alias to its full name."""
    return MODEL_ALIASES.get(model.lower(), model)


def get_available_models(provider: ProviderType) -> list[str]:
    """Get available models for a provider dynamically from LiteLLM."""
    if provider == ProviderType.LOCAL:
        return ["q4_k_m", "q8_0"]

    try:
        import litellm

        all_models = list(litellm.model_cost.keys())

        if provider == ProviderType.OPENAI:
            # Filter for OpenAI models (gpt-*, o1-*)
            models = [
                m for m in all_models
                if (m.startswith("gpt-") or m.startswith("o1"))
                and not m.startswith("gpt-4o-transcribe")
                and "audio" not in m
                and "realtime" not in m
            ]
            # Dedupe and sort, prefer shorter names
            seen = set()
            result = []
            for m in sorted(models, key=len):
                base = m.split("-")[0:3]  # gpt-4o-mini
                key = "-".join(base)
                if key not in seen:
                    seen.add(key)
                    result.append(m)
            return sorted(result)[:15]

        elif provider == ProviderType.ANTHROPIC:
            # Filter for Claude models (direct API, not bedrock/vertex)
            models = [
                m for m in all_models
                if m.startswith("claude")
                and not m.startswith("claude-instant")
                and ":" not in m  # Exclude versioned bedrock models
            ]
            return sorted(set(models))[:15]

        elif provider == ProviderType.GEMINI:
            # Filter for Gemini models
            models = [
                m for m in all_models
                if m.startswith("gemini")
                and "vision" not in m
            ]
            return sorted(set(models))[:15]

        elif provider == ProviderType.OPENROUTER:
            # OpenRouter models have openrouter/ prefix
            models = [m for m in all_models if m.startswith("openrouter/")]
            return sorted(models)[:15]

    except ImportError:
        pass

    # Fallback static lists if LiteLLM not available
    fallback = {
        ProviderType.OPENAI: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o1-mini"],
        ProviderType.ANTHROPIC: ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-3-5-sonnet-latest"],
        ProviderType.GEMINI: ["gemini/gemini-1.5-flash", "gemini/gemini-1.5-pro"],
        ProviderType.OPENROUTER: ["openrouter/openai/gpt-4o-mini"],
    }
    return fallback.get(provider, [])


@dataclass
class ProviderConfig:
    """Configuration for a specific provider."""

    default_model: str | None = None


@dataclass
class Config:
    """Main configuration class."""

    active_provider: ProviderType = ProviderType.LOCAL
    active_model: str | None = None  # None = use provider default
    local_quantization: Literal["q4_k_m", "q8_0"] = "q8_0"
    providers: dict[str, ProviderConfig] = field(default_factory=dict)

    @classmethod
    def config_dir(cls) -> Path:
        """Get the config directory path."""
        return Path(user_config_dir("thefuckllm"))

    @classmethod
    def config_path(cls) -> Path:
        """Get the config file path."""
        return cls.config_dir() / "config.toml"

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from file, or return defaults."""
        config_path = cls.config_path()

        if not config_path.exists():
            return cls()

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            return cls()

        # Parse general settings
        general = data.get("general", {})
        active_provider_str = general.get("active_provider", "local")
        try:
            active_provider = ProviderType(active_provider_str)
        except ValueError:
            active_provider = ProviderType.LOCAL

        active_model = general.get("active_model") or None
        local_quantization = general.get("local_quantization", "q8_0")
        if local_quantization not in ("q4_k_m", "q8_0"):
            local_quantization = "q8_0"

        # Parse provider configs
        providers = {}
        providers_data = data.get("providers", {})
        for provider_name, provider_data in providers_data.items():
            providers[provider_name] = ProviderConfig(
                default_model=provider_data.get("default_model")
            )

        return cls(
            active_provider=active_provider,
            active_model=active_model,
            local_quantization=local_quantization,
            providers=providers,
        )

    def save(self) -> None:
        """Save configuration to file."""
        config_path = self.config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "general": {
                "active_provider": self.active_provider.value,
                "active_model": self.active_model or "",
                "local_quantization": self.local_quantization,
            },
            "providers": {},
        }

        for provider_name, provider_config in self.providers.items():
            data["providers"][provider_name] = {
                "default_model": provider_config.default_model or "",
            }

        with open(config_path, "wb") as f:
            tomli_w.dump(data, f)

    def get_active_model(self) -> str:
        """Get the active model, falling back to provider default.

        Also resolves model aliases to full names.
        """
        model = None

        if self.active_model:
            model = self.active_model
        else:
            # Check provider-specific config
            provider_config = self.providers.get(self.active_provider.value)
            if provider_config and provider_config.default_model:
                model = provider_config.default_model
            else:
                # Fall back to global defaults
                model = DEFAULT_MODELS.get(self.active_provider, "q8_0")

        # Resolve aliases to full model names
        return resolve_model_alias(model)

    def get_api_key(self, provider: ProviderType | None = None) -> str | None:
        """Get API key from environment for the given provider."""
        if provider is None:
            provider = self.active_provider

        if provider == ProviderType.LOCAL:
            return None

        env_var = API_KEY_ENV_VARS.get(provider)
        if env_var:
            return os.environ.get(env_var)
        return None

    def has_api_key(self, provider: ProviderType) -> bool:
        """Check if API key is available for a provider."""
        return self.get_api_key(provider) is not None


# Singleton instance
_config: Config | None = None


def get_config() -> Config:
    """Get the singleton config instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config() -> Config:
    """Reload configuration from file."""
    global _config
    _config = Config.load()
    return _config
