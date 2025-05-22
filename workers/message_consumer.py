import pika
import json
import time
import logging
from uuid import UUID
from typing import Dict, Any
from datetime import datetime
from jose import jwt, JWTError # For decoding user_token
from tenacity import Retrying, stop_after_attempt, wait_fixed, retry_if_exception_type # Removed unused retry_if_not_result

from ..api.core.config import settings
from ..api.core.database import SessionLocal # Import SessionLocal
from ..api.models.database_models import User # Import User model if needed for token logic
from .db_handler import DBHandler
import redis
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError # Import DB error types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_handler = DBHandler() # Initialize DB handler

# Redis connection for updating vote counts
redis_client = None
try:
    @retry(stop=stop_after_attempt(5), wait=wait_fixed(settings.WORKER_RECONNECT_DELAY_SECONDS/2),
           retry=retry_if_exception_type(RedisConnectionError))
    def connect_redis():
        client = redis.StrictRedis.from_url(settings.REDIS_URL) # Keep decode_responses=True for Redis HASH field (UUID string)
        client.ping() # Check connection
        logger.info("Worker successfully connected to Redis.")
        return client

    redis_client = connect_redis()
except RedisConnectionError as e:
    logger.error(f"Worker failed to connect to Redis after multiple retries: {e}. Vote counts in Redis will be inaccurate/delayed.")
    # Worker can still process votes into DB, but Redis counts will be affected.

class VoteMessageProcessor:
    def __init__(self):
        self._connection = None
        self._channel = None
        self._consumer_tag = None
        self._introspect_delay = settings.WORKER_RECONNECT_DELAY_SECONDS # Delay for scheduled checks/reconnects

    def connect(self):
        """Connect to RabbitMQ using async SelectConnection."""
        if self._connection is None or self._connection.is_closed:
            logger.info(f"Attempting to connect to RabbitMQ: {settings.RABBITMQ_URL}")
            try:
                # Use SelectConnection which integrates with an IOLoop
                self._connection = pika.SelectConnection(
                    pika.URLParameters(settings.RABBITMQ_URL),
                    on_open_callback=self.on_connection_open,
                    on_close_callback=self.on_connection_closed,
                    on_open_error_callback=self.on_connection_open_error
                )
                # Start the IOLoop; this call is blocking until ioloop stops
                self._connection.ioloop.start()
            except Exception as e:
                # This is a critical failure before IOLoop starts or during initial setup
                logger.error(f"Failed to start RabbitMQ IOLoop or connection: {e}")
                # Can't schedule reconnect via IOLoop if it failed to start.
                # Exit or handle externally if this is the main entry point.
                # If run as a systemd service with restart policy, it will restart.
        else:
             logger.info("RabbitMQ connection is already open.")


    def on_connection_open(self, connection):
        logger.info("RabbitMQ connection opened successfully.")
        self._connection.add_on_close_callback(self.on_connection_closed)
        self.open_channel()

    def on_connection_closed(self, connection, reason):
        self._channel = None
        # Use the IOLoop to schedule a reconnect attempt
        if self._connection and self._connection.ioloop: # Check if ioloop is available before scheduling
             if self._connection.is_open:
                  logger.warning(f"RabbitMQ connection closed unexpectedly: {reason}. Scheduling reconnect.")
                  self._schedule_reconnect()
             else:
                 logger.info(f"RabbitMQ connection closed: {reason}. If not graceful shutdown, maybe due to error.")
                 if reason is not None: # If reason is None, it might be a planned close
                      self._schedule_reconnect() # Schedule reconnect on unplanned closes
        else:
             logger.error("IOLoop not available. Cannot schedule RabbitMQ reconnect.")


    def on_connection_open_error(self, connection, err):
         logger.error(f"RabbitMQ connection open error: {err}. Scheduling reconnect.")
         self._connection = None # Ensure connection is None for proper reconnect
         self._schedule_reconnect() # Attempt to schedule reconnect

    def open_channel(self):
        """Open a new channel."""
        if self._connection and self._connection.is_open:
            logger.info("Creating RabbitMQ channel.")
            # Open channel with callback
            self._connection.channel(on_open_callback=self.on_channel_open)
        else:
            logger.warning("Cannot open channel, connection is not open.")

    def on_channel_open(self, channel):
        logger.info("RabbitMQ channel opened.")
        self._channel = channel
        self._channel.add_on_close_callback(self.on_channel_closed)
        # Declare queues and exchanges after channel opened
        self.declare_dead_letter_exchange(settings.RABBITMQ_DLX_EXCHANGE)


    def on_channel_closed(self, channel, reason):
        logger.warning(f"RabbitMQ channel closed: {reason}")
        self._channel = None
        # Channel closed, connection might still be open. Attempt to reopen channel.
        if self._connection and self._connection.is_open:
             logger.info("Scheduling channel reopen.")
             # Schedule channel reopen via IOLoop
             self._connection.ioloop.call_later(1, self.open_channel) # Short delay before reopening channel

    def declare_dead_letter_exchange(self, exchange_name):
        """Declare DLX."""
        logger.info(f"Declaring DLX '{exchange_name}'")
        self._channel.exchange_declare(
            exchange=exchange_name,
            exchange_type='fanout', # Typical type for DLX
            durable=True,
            callback=self.on_dlx_declared
        )

    def on_dlx_declared(self, frame):
         logger.info("DLX declared. Declaring DLQ.")
         self.declare_dead_letter_queue(settings.RABBITMQ_DLQ_QUEUE)


    def declare_dead_letter_queue(self, queue_name):
        """Declare DLQ and bind it to DLX."""
        logger.info(f"Declaring DLQ '{queue_name}'")
        self._channel.queue_declare(
            queue=queue_name,
            durable=True,
            callback=self.on_dlq_declared
        )

    def on_dlq_declared(self, frame):
         logger.info("DLQ declared. Binding DLQ to DLX.")
         # Bind DLQ to the DLX (using DLQ name as routing key if fanout)
         self._channel.queue_bind(
             queue=settings.RABBITMQ_DLQ_QUEUE,
             exchange=settings.RABBITMQ_DLX_EXCHANGE,
             routing_key='#', # For fanout exchange, any routing key works, '#' is a common convention
             callback=self.on_dlq_bound
         )


    def on_dlq_bound(self, frame):
        logger.info("DLQ bound to DLX. Declaring main queue.")
        self.declare_main_queue(settings.RABBITMQ_QUEUE_NAME, settings.RABBITMQ_DLX_EXCHANGE)


    def declare_main_queue(self, queue_name, dlx_exchange_name):
        """Declare the main message queue with DLX argument."""
        logger.info(f"Declaring main queue '{queue_name}' with DLX argument.")
        self._channel.queue_declare(
            queue=queue_name,
            durable=True, # Ensure queue survives broker restart
            arguments={'x-dead-letter-exchange': dlx_exchange_name}, # Route rejected messages to DLX
            callback=self.on_main_queue_declared
        )


    def on_main_queue_declared(self, frame):
        logger.info("Main queue declared. Starting to consume messages.")
        self.start_consuming()

    def start_consuming(self):
         """Start consuming messages from the queue."""
         if self._channel:
             try:
                 # Set prefetch count for fair dispatch among workers
                 self._channel.basic_qos(prefetch_count=10) # Process up to 10 messages concurrently per worker
                 self._consumer_tag = self._channel.basic_consume(
                     settings.RABBITMQ_QUEUE_NAME,
                     on_message_callback=self.on_message,
                     auto_ack=False  # Important: Manual acknowledgement
                 )
                 logger.info(f"Started consuming from '{settings.RABBITMQ_QUEUE_NAME}' with consumer tag: {self._consumer_tag}. Auto-ack is OFF.")
             except pika.exceptions.ChannelClosedByBroker as e:
                 logger.error(f"Channel closed by broker when starting to consume: {e}")
                 # Handled by on_channel_closed callback
             except Exception as e:
                 logger.error(f"Failed to start consuming: {e}")
                 # Decide whether to retry starting consume or rely on channel/connection reconnect
                 # Generally, rely on reconnects.

    def stop_consuming(self):
        """Stop consuming messages and gracefully shutdown."""
        if self._channel and self._consumer_tag:
            logger.info(f"Stopping consumer tag: {self._consumer_tag}")
            self._channel.basic_cancel(self._consumer_tag) # Removed callback, basic_cancel is often blocking/initiates shutdown sequence
            self._consumer_tag = None
        logger.info("Consumer stopping.")


    def close_connection(self):
         """Close the RabbitMQ connection gracefully."""
         if self._connection and self._connection.is_open:
             logger.info("Closing RabbitMQ connection.")
             self._connection.close() # Initiate graceful close
         else:
             logger.info("RabbitMQ connection is already closed.")


    def _schedule_reconnect(self):
         """Schedule a reconnect attempt after a delay using the IOLoop."""
         if self._connection is not None and self._connection.ioloop:
             logger.warning(f"Scheduling RabbitMQ reconnect attempt in {self._introspect_delay} seconds.")
             # Cancel previous scheduled calls if any? Not strictly needed with simple retry
             self._connection.ioloop.call_later(self._introspect_delay, self.connect)
         else:
              logger.error("IOLoop not available. Cannot schedule RabbitMQ reconnect.")

    def on_message(self, ch, method, properties, body):
        """Callback function when a message is received."""
        logger.info(f"Received message (delivery_tag={method.delivery_tag}): {body}")
        delivery_tag = method.delivery_tag

        try:
            # Deserialize message
            message_data = json.loads(body)
            candidate_id_str = message_data.get("candidate_id")
            user_token = message_data.get("user_token")
            vote_timestamp_str = message_data.get("vote_timestamp")
            source_ip = message_data.get("source_ip")
            user_agent = message_data.get("user_agent")

            # Basic validation of message structure
            if not candidate_id_str or not user_token or not vote_timestamp_str:
                logger.error(f"Invalid message format: Missing required fields in message (delivery_tag={delivery_tag}). Rejecting.")
                ch.basic_reject(delivery_tag=delivery_tag, requeue=False) # Send to DLQ
                return

            try:
                candidate_id = UUID(candidate_id_str)
                # No need to parse vote_timestamp string here if DBHandler handles it.
                # Ensure IPs are valid format if needed, or rely on DB INET type casting later.
            except (ValueError, TypeError) as e:
                 logger.error(f"Invalid data types in message (delivery_tag={delivery_tag}): {e} for {body}. Rejecting.")
                 ch.basic_reject(delivery_tag=delivery_tag, requeue=False) # Send to DLQ
                 return

            # *** Detailed Validation: User Token -> user_identifier ***
            # Decode the token to get user claims and derive a consistent user_identifier
            # This identifier is used to link votes to a unique user in the 'users' table.
            try:
                # Assuming user_identifier is a claim 'user_uid' in the token
                # Decode without verifying expiry to process historical votes if queuing was delayed
                payload = jwt.decode(
                     user_token,
                     settings.JWT_SECRET_KEY,
                     algorithms=[settings.JWT_ALGORITHM],
                     options={"verify_signature": True, "verify_aud": False, "verify_iss": False, "verify_exp": False} # Don't verify expiry here
                )
                user_identifier: Optional[str] = payload.get("user_uid") # Assuming 'user_uid' claim

                if not user_identifier:
                     logger.error(f"User identifier claim ('user_uid') missing in valid token payload (delivery_tag={delivery_tag}). Rejecting.")
                     ch.basic_reject(delivery_tag=delivery_tag, requeue=False) # Send to DLQ
                     return

            except JWTError as e:
                logger.error(f"Invalid or malformed JWT token in message payload (delivery_tag={delivery_tag}): {e}. Rejecting.")
                # Invalid token means we cannot identify the user reliably. Reject.
                ch.basic_reject(delivery_tag=delivery_tag, requeue=False) # Send to DLQ
                return
            except Exception as e:
                 # Catch other token processing errors
                 logger.error(f"Unexpected error during JWT processing (delivery_tag={delivery_tag}): {e} for {body}. Rejecting.")
                 ch.basic_reject(delivery_tag=delivery_tag, requeue=False) # Send to DLQ
                 return


            # *** Process Vote (DB and Redis Write) ***
            # Call DBHandler to insert/upsert user and insert vote, handling ON CONFLICT internally with retries
            try:
                vote_processing_status = db_handler.execute_transaction(
                    user_identifier=user_identifier,
                    candidate_id=candidate_id,
                    vote_timestamp=vote_timestamp_str, # Pass the original string timestamp
                    source_ip=source_ip,
                    user_agent=user_agent
                )

                if vote_processing_status == 'processed':
                    # Only increment Redis count on a successfully inserted *new* vote
                    if redis_client is not None:
                         try:
                              # Use HINCRBY to atomically increment the vote count in Redis HASH
                              redis_key = "candidate_votes" # Key for the HASH storing all counts
                              redis_field = str(candidate_id) # Field is the candidate UUID string
                              # HINCRBY returns the new value after increment
                              new_count = redis_client.hincrby(redis_key, redis_field, 1)
                              logger.info(f"Incremented Redis vote count for candidate_id={candidate_id}. New count: {new_count}")
                         except (RedisConnectionError, RedisTimeoutError) as e:
                             # This is an edge case. Vote is in PG, but count might be slightly off in Redis.
                             # Log error but do NOT NACK message just because Redis failed if DB was successful.
                             logger.error(f"Failed to increment Redis vote count for candidate_id={candidate_id}: {e}. Vote recorded in DB.")
                         except Exception as e:
                             logger.error(f"Unexpected error during Redis HINCRBY for candidate_id={candidate_id}: {e}. Vote recorded in DB.")

                    # Acknowledge message ONLY if database transaction (insert or conflict) was handled (processed or duplicate)
                    ch.basic_ack(delivery_tag)
                    logger.info(f"Message acknowledged (delivery_tag={delivery_tag}) after successful DB operation (status={vote_processing_status}).")

                elif vote_processing_status == 'duplicate':
                    # Vote was a duplicate (handled by ON CONFLICT). Acknowledge the message.
                    # No Redis HASH increment for duplicates based on typical requirements.
                    ch.basic_ack(delivery_tag)
                    logger.info(f"Duplicate vote message (delivery_tag={delivery_tag}) acknowledged for user_identifier={user_identifier}, candidate_id={candidate_id}.")

                elif vote_processing_status == 'failed':
                     # DB operation failed *after* retries within DBHandler.
                     # This indicates a persistent DB error or unhandled exception.
                     # Reject without requeue to send to DLQ.
                     logger.error(f"Vote processing failed after DB retries for message (delivery_tag={delivery_tag}): {body}. Rejecting to DLQ.")
                     ch.basic_reject(delivery_tag=delivery_tag, requeue=False) # Send to DLQ

            except (SQLAlchemyError, IntegrityError) as e:
                # Catch DB errors not fully handled or retried by DBHandler (e.g. Integrity Errors)
                # Log and reject to DLQ for investigation.
                logger.error(f"Persistent DB error during vote processing (delivery_tag={delivery_tag}): {e}. Rejecting to DLQ.", exc_info=True)
                ch.basic_reject(delivery_tag=delivery_tag, requeue=False) # Send to DLQ
            except Exception as e:
                # Catch any other unexpected exceptions during the main processing logic
                logger.error(f"An unexpected error occurred during vote processing logic (delivery_tag={delivery_tag}): {e} for message: {body}. Rejecting to DLQ.", exc_info=True)
                # Reject message. If DLQ is configured, it goes there. If not, it might be lost.
                ch.basic_reject(delivery_tag=delivery_tag, requeue=False) # safer to send to DLQ

        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON message (delivery_tag={delivery_tag}): {body}. Rejecting.")
            # Negative acknowledgement for bad message format, do not requeue (poison message)
            ch.basic_reject(delivery_tag=delivery_tag, requeue=False) # Send to DLQ
        except Exception as e:
            # Catch ANY other top-level exceptions before main processing logic starts
            logger.error(f"A critical error occurred BEFORE vote processing logic (delivery_tag={delivery_tag}): {e} for {body}. Rejecting to DLQ.", exc_info=True)
            ch.basic_reject(delivery_tag=delivery_tag, requeue=False) # Send to DLQ


# Entry point for the worker script IF RUNNING STANDALONE
if __name__ == "__main__":
    processor = VoteMessageProcessor()
    logger.info("Starting Vote Processor Worker.")
    try:
        processor.connect() # This call is blocking due to IOLoop.start()
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C (relies on pika's IOLoop handling)
        logger.info("KeyboardInterrupt received. Stopping worker gracefully.")
        processor.stop_consuming()
        processor.close_connection() # Initiates graceful close of the connection
        # The IOLoop will stop automatically after these close ops complete

    logger.info("Worker shutdown complete.")

