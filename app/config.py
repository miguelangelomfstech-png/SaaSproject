from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_BASE_URL: str = "http://localhost:8000"
    ADMIN_SECRET: str = "change-me"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/ranklens.db"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    # Comma-separated "price_id=plan" pairs, e.g. "price_abc=starter,price_def=pro"
    STRIPE_PRICE_MAP: str = ""

    # AI
    GEMINI_API_KEY: str = ""

    # Email (Resend)
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "RankLens <noreply@ranklens.dev>"

    @property
    def price_to_plan(self) -> dict[str, str]:
        """Parse STRIPE_PRICE_MAP into a dict."""
        mapping: dict[str, str] = {}
        for pair in self.STRIPE_PRICE_MAP.split(","):
            pair = pair.strip()
            if "=" in pair:
                price_id, plan = pair.split("=", 1)
                mapping[price_id.strip()] = plan.strip()
        return mapping

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
