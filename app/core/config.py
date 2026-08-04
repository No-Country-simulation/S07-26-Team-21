from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "BENCHMARK·DC Engine"
    API_V1_STR: str = "/api/v1"

    # Configuración de Base de Datos PostgreSQL
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "benchmark_password_2026"
    POSTGRES_DB: str = "benchmark_engine"

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Genera la URL de conexión asíncrona usando asyncpg."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()