from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    RABBITMQ_URL: str
    RABBITMQ_QUEUE_NAME: str
    RABBITMQ_DLX_EXCHANGE: str = "vote_dlx" # Default DLX name
    RABBITMQ_DLQ_QUEUE: str = "vote_dlq"   # Default DLQ name
    REDIS_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    RESULTS_CACHE_TTL_SECONDS: int = 60
    WORKER_RECONNECT_DELAY_SECONDS: int = 5 # Delay for worker reconnects

    model_config = SettingsConfigDict(env_file=".env", extra='ignore') # 'ignore' for unknown fields

settings = Settings()