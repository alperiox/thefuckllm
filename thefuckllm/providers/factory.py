"""Factory for creating LLM providers."""

from ..config import ProviderType, get_config
from .base import LLMProvider
from .litellm_provider import LiteLLMProvider
from .local import LocalProvider


class ProviderFactory:
    """Factory for creating LLM providers with smart caching."""

    _instance: LLMProvider | None = None
    _current_provider: ProviderType | None = None
    _current_model: str | None = None

    @classmethod
    def get_provider(cls, force_reload: bool = False) -> LLMProvider:
        """Get the current provider instance (smart loading).

        Only creates a new provider if:
        - No provider exists yet
        - force_reload is True
        - The active provider or model has changed
        """
        config = get_config()

        # Check if we need a new provider
        needs_reload = (
            cls._instance is None
            or force_reload
            or cls._current_provider != config.active_provider
            or cls._current_model != config.get_active_model()
        )

        if needs_reload:
            # Unload previous provider if exists
            if cls._instance is not None:
                cls._instance.unload()

            # Create new provider
            cls._instance = cls._create_provider(config)
            cls._current_provider = config.active_provider
            cls._current_model = config.get_active_model()

        return cls._instance

    @classmethod
    def _create_provider(cls, config) -> LLMProvider:
        """Create a new provider based on config."""
        if config.active_provider == ProviderType.LOCAL:
            return LocalProvider(quantization=config.local_quantization)
        else:
            # Use LiteLLM for all remote providers
            model = config.get_active_model()
            api_key = config.get_api_key()

            return LiteLLMProvider(
                model=model,
                api_key=api_key,
            )

    @classmethod
    def clear(cls) -> None:
        """Clear the cached provider."""
        if cls._instance:
            cls._instance.unload()
        cls._instance = None
        cls._current_provider = None
        cls._current_model = None

    @classmethod
    def preload(cls) -> None:
        """Preload the provider (useful for background server)."""
        provider = cls.get_provider()
        provider.load()


def get_provider(force_reload: bool = False) -> LLMProvider:
    """Convenience function to get the current provider."""
    return ProviderFactory.get_provider(force_reload)
