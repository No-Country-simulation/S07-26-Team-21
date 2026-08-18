from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    PROJECT_NAME: str = "BENCHMARK·DC Engine"
    API_V1_STR: str = "/api/v1"

    # Configuración de CORS
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]


    # Configuración de Base de Datos PostgreSQL
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "benchmark_password_2026"
    POSTGRES_DB: str = "benchmark_engine"

    # Configuración de Proveedores LLM (US-19)
    LLM_PROVIDER: str = "gemini"  # "gemini" | "claude" | "ollama"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"

    CLAUDE_API_KEY: str | None = None
    CLAUDE_MODEL: str = "claude-3-5-sonnet-20241022"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_TIMEOUT_SECONDS: float = 25.0

    LLM_RATE_LIMIT_PER_MINUTE: int = 30



    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Genera la URL de conexión asíncrona usando asyncpg."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()