import os
from dataclasses import dataclass, field


@dataclass
class AzureConfig:
    endpoint: str = field(
        default_factory=lambda: os.environ.get(
            "AZURE_FOUNDRY_ENDPOINT",
            "",
        )
    )
    api_key: str = field(
        default_factory=lambda: os.environ.get("AZURE_FOUNDRY_API_KEY", "")
    )
    api_version: str = field(
        default_factory=lambda: os.environ.get(
            "AZURE_FOUNDRY_API_VERSION", "2024-05-01-preview"
        )
    )
    deployment: str = field(
        default_factory=lambda: os.environ.get(
            "AZURE_FOUNDRY_DEPLOYMENT", "deepseek-r1"
        )
    )

    def is_configured(self) -> bool:
        return bool(self.endpoint and self.api_key)

    def chat_url(self) -> str:
        base = self.endpoint.rstrip("/")
        return f"{base}/v1/chat/completions?api-version={self.api_version}"
