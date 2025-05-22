# High-Load Voting System

This project implements a high-load voting system with a FastAPI backend API and Python workers for processing votes asynchronously.

## Project Structure

voting_system/
├── api/ # FastAPI application
│ ├── main.py # FastAPI app entry point
│ ├── routers/ # API endpoints definitions
│ ├── services/ # Business logic and interactions with external services
│ ├── models/ # Pydantic models for request/response
│ └── core/ # Configuration and core setup
├── workers/ # Asynchronous vote processing workers
│ ├── vote_processor.py # Core vote processing logic
│ ├── db_handler.py # Database interaction logic for workers
│ └── message_consumer.py # RabbitMQ consumer implementation
├── common/ # Shared utilities or constants
├── tests/ # Unit and integration tests
├── README.md # Project overview and setup instructions
└── requirements.txt # Project dependencies


## Requirements

*   Python 3.9+
*   Docker (recommended for local development environment)
*   RabbitMQ instance
*   PostgreSQL database instance
*   Redis instance

## Setup

1.  **Clone the repository:**

bash
-- git clone <repository_url>
-- cd voting_system


2.  **Set up Environment Variables:**

    Copy the example configuration file and update it with your actual settings.

bash
-- cp .env.example .env
# Edit .env and provide database credentials, RabbitMQ connection string, Redis connection string, etc.


3.  **Install Dependencies:**

    It's recommended to use a virtual environment.

bash
-- python -m venv venv
-- source venv/bin/activate # On Windows use venv\Scripts\activate
pip install -r requirements.txt


4.  **Database Setup:**

    Apply database migrations to create necessary tables (`candidates`, `users`, `votes`). Migration tools like Alembic can be used, but for this initial codebase, you would manually run the provided SQL scripts or use an ORM capable of creating tables from models.

    *Assuming you have PostgreSQL running and configured:*
    
sql
-- Connect to your database and run the SQL from data schema document
-- Example:
-- CREATE TYPE vote_processing_status AS ENUM ('received', 'validating', 'processed', 'failed');
-- CREATE TABLE candidates (...);
-- CREATE TABLE users (...);
-- CREATE TABLE votes (...);


    Populate the `candidates` table with initial data.

5.  **RabbitMQ Setup:**

    Ensure a RabbitMQ instance is running and accessible. The worker will create the necessary queue if it doesn't exist.

6.  **Redis Setup:**

    Ensure a Redis instance is running and accessible.

## Running Components

### 1. Backend API

The FastAPI application handles incoming HTTP requests for voting and fetching results.

bash
-- cd api
-- uvicorn main:app --host 0.0.0.0 port 8000

The API documentation (Swagger UI) will be available at `http://127.0.0.1:8000/docs`.

### 2. Vote Processor Workers

The workers consume messages from the RabbitMQ queue, validate votes, and store them in PostgreSQL and update Redis.

bash
-- cd workers
-- python message_consumer.py

You can run multiple instances of the worker for parallel processing and scalability.

## Configuration

Configuration is loaded from environment variables. Refer to the `.env.example` file for necessary variables.

*   `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://user:password@host:port/dbname`)
*   `RABBITMQ_URL`: RabbitMQ connection string (e.g., `amqp://guest:guest@localhost:5672/`)
*   `RABBITMQ_QUEUE_NAME`: Name of the queue for vote messages (e.g., `vote_queue`)
*   `REDIS_URL`: Redis connection string (e.g., `redis://localhost:6379/0`)
*   `JWT_SECRET_KEY`: Secret key for decoding JWT tokens (used for user identification)
*   `JWT_ALGORITHM`: Algorithm used for JWT (e.g., `HS256`)
*   `RESULTS_CACHE_TTL_SECONDS`: TTL for cached results in Redis (e.g., `60`)

## Testing

Basic test structure is provided in the `tests/` directory.

bash
-- pip install -r requirements-dev.txt # Install test dependencies
-- pytest tests/

*(Note: Tests are not fully implemented in this initial codebase structure.)*

## Next Steps

*   Implement comprehensive error handling and logging.
*   Add monitoring metrics (using Prometheus client libraries).
*   Implement detailed JWT validation and user identification logic.
*   Add rate limiting implementation (e.g., using Redis).
*   Create database migrations using Alembic.
*   Write comprehensive unit and integration tests.
*   Implement Dockerfiles and Kubernetes deployments.
