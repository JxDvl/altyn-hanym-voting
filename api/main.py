from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import vote, auth
from .core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="High-Load Voting System API",
    version="1.0.0",
    description="API for accepting votes and retrieving results.",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(vote.router, prefix="/api/v1", tags=["voting"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])

# Add startup and shutdown events for graceful handling of external connections
@app.on_event("startup")
async def startup_event():
    logger.info("API startup initiated.")
    # Potential place for initial DB connectivity check
    # from .core.database import engine
    # try:
    #      with engine.connect() as connection:
    #           logger.info("Database connection test successful.")
    # except Exception as e:
    #      logger.error(f"Database connection test failed: {e}")
    #      # Decide if startup should fail or log a warning


@app.on_event("shutdown")
async def shutdown_event():
     logger.info("API shutdown initiated.")
     # Gently close RabbitMQ connection managed by VoteService if it's blocking
     # If using aio-pika, the library/connection pool handles this better
     if vote.vote_service.rabbitmq_connection and vote.vote_service.rabbitmq_connection.is_open:
         try:
              vote.vote_service.rabbitmq_connection.close() # Might block
              logger.info("RabbitMQ connection closed.")
         except Exception as e:
              logger.error(f"Error closing RabbitMQ connection: {e}")

     # Redis client managed by CacheService doesn't usually need explicit close with redis-py

     # SQLAlchemy engine connection pool is typically cleaned up automatically on process exit,
     # but explicit dispose can be added here if necessary:
     # from .core.database import engine
     # engine.dispose()
     # logger.info("SQLAlchemy engine disposed.")

     logger.info("API shutdown complete.")

