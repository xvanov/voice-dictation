import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


def load_dotenv() -> None:
    """Load repo-root .env if present (no-op when python-dotenv is missing)."""
    try:
        from dotenv import load_dotenv as _load
    except ImportError:
        return
    repo_root = Path(__file__).resolve().parents[1]
    _load(repo_root / ".env", override=False)


load_dotenv()


@dataclass
class AzureConfig:
    endpoint: str = field(
        default_factory=lambda: _env(
            "AZURE_FOUNDRY_ENDPOINT",
            "AZURE_OPENAI_ENDPOINT",
        )
    )
    api_key: str = field(
        default_factory=lambda: _env(
            "AZURE_FOUNDRY_API_KEY",
            "AZURE_OPENAI_API_KEY",
        )
    )
    api_version: str = field(
        default_factory=lambda: _env(
            "AZURE_FOUNDRY_API_VERSION",
            "AZURE_OPENAI_API_VERSION",
            default="2024-05-01-preview",
        )
    )
    deployment: str = field(
        default_factory=lambda: _env(
            "AZURE_FOUNDRY_DEPLOYMENT",
            "AZURE_OPENAI_DEPLOYMENT",
            default="deepseek-r1",
        )
    )

    def is_configured(self) -> bool:
        return bool(self.endpoint and self.api_key)

    def chat_url(self) -> str:
        base = self.endpoint.rstrip("/")
        return f"{base}/v1/chat/completions?api-version={self.api_version}"
