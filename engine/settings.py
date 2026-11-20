import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    api_token: str
    llm_mode: str = "none"
    send_notifications: bool = False
    allow_synthetic_live: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        for name in ("SEND_NOTIFICATIONS", "ALLOW_SYNTHETIC_LIVE"):
            if os.getenv(name, "false").lower() != "false":
                raise ValueError(f"{name} must remain false in this release")
        if os.getenv("LLM_MODE", "none") != "none":
            raise ValueError("Only LLM_MODE=none is implemented")
        return cls(os.getenv("DATABASE_URL", "sqlite:///rie-local.db"), os.getenv("API_TOKEN", ""))
