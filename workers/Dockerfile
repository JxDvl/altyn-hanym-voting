# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Copy the requirements file first
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the worker code and any common modules
COPY ./workers /app/workers
COPY ./api/core /app/api/core
COPY ./api/models /app/api/models
COPY ./common /app/common

# Create a non-root user and switch to it
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# Command to run the worker script
# The message_consumer.py script contains the main IOLoop logic
CMD ["python", "workers/message_consumer.py"]
