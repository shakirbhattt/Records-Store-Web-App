from celery import Celery
import psycopg2
import os
import json
import logging
import pika
from time import sleep, time
from prometheus_client import Counter, Histogram, push_to_gateway
import socket
from api.telemetry import setup_telemetry, get_tracer
from opentelemetry.instrumentation.celery import CeleryInstrumentor

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenTelemetry (will use OTEL_SERVICE_NAME environment variable)
setup_telemetry()

# Get a tracer
tracer = get_tracer(__name__)

# Environment variables with defaults
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'kodekloud_records')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'admin')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
PROMETHEUS_PUSHGATEWAY = os.getenv('PROMETHEUS_PUSHGATEWAY', 'localhost:9091')

# Prometheus metrics
TASK_COUNT = Counter(
    'celery_tasks_total',
    'Number of Celery tasks executed',
    ['task_name', 'status']
)

TASK_FAILURE = Counter(
    'celery_task_failures_total',
    'Number of Celery task failures',
    ['task_name', 'exception_type']
)

TASK_DURATION = Histogram(
    'celery_task_duration_seconds',
    'Task execution time in seconds',
    ['task_name'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# Celery Configuration
celery_app = Celery(
    "kodekloud_record_store_worker",
    broker=f"pyamqp://guest@{RABBITMQ_HOST}//",
    backend="rpc://"
)

# Instrument Celery
CeleryInstrumentor().instrument()

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Database Connection
DB_CONFIG = {
    "dbname": POSTGRES_DB,
    "user": POSTGRES_USER,
    "password": POSTGRES_PASSWORD,
    "host": POSTGRES_HOST,
    "port": POSTGRES_PORT
}

def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

def push_metrics():
    """Push metrics to Prometheus Pushgateway"""
    try:
        hostname = socket.gethostname()
        push_to_gateway(
            PROMETHEUS_PUSHGATEWAY, 
            job='celery_worker',
            grouping_keys={'instance': hostname}
        )
        logger.debug("Metrics pushed to Pushgateway")
    except Exception as e:
        logger.error(f"Failed to push metrics: {e}")

# RabbitMQ Connection
RABBITMQ_QUEUE = "order_queue"

def consume_orders():
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE)
    
    def callback(ch, method, properties, body):
        order = json.loads(body)
        logger.info(f"Processing Order: {order}")
        process_order(order)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)
    logger.info("Waiting for orders...")
    channel.start_consuming()

@celery_app.task(name="process_order", bind=True, max_retries=3)
def process_order(self, order):
    with tracer.start_as_current_span("process_order_task"):
        task_name = 'process_order'
        start_time = time()
        
        logger.info(f"Processing order: {order}")
        
        try:
            # Simulate processing time
            sleep(2)
            
            conn = get_db_connection()
            cur = conn.cursor()
            
            # First check if product exists and has enough inventory
            cur.execute("SELECT id, name FROM products WHERE id = %s", (order["product_id"],))
            product = cur.fetchone()
            
            if not product:
                logger.error(f"Product {order['product_id']} not found")
                TASK_COUNT.labels(task_name=task_name, status='failed').inc()
                push_metrics()
                return {"status": "failed", "reason": "product_not_found"}
            
            # Insert the order
            cur.execute(
                "INSERT INTO orders (product_id, quantity, status) VALUES (%s, %s, %s) RETURNING id",
                (order["product_id"], order["quantity"], "processed")
            )
            order_id = cur.fetchone()[0]
            conn.commit()
            
            logger.info(f"Order {order_id} processed successfully")
            
            # Record successful task execution
            TASK_COUNT.labels(task_name=task_name, status='success').inc()
            TASK_DURATION.labels(task_name=task_name).observe(time() - start_time)
            push_metrics()
            
            return {"order_id": order_id, "status": "processed"}
            
        except Exception as e:
            logger.error(f"Error processing order: {e}")
            
            # Record task failure
            TASK_COUNT.labels(task_name=task_name, status='failed').inc()
            TASK_FAILURE.labels(
                task_name=task_name, 
                exception_type=type(e).__name__
            ).inc()
            TASK_DURATION.labels(task_name=task_name).observe(time() - start_time)
            push_metrics()
            
            # Retry the task if it fails
            self.retry(exc=e, countdown=5)
        finally:
            if 'conn' in locals() and conn:
                cur.close()
                conn.close()

# Additional tasks can be defined here
@celery_app.task(name="send_order_confirmation")
def send_order_confirmation(order_id):
    """Simulate sending an order confirmation email"""
    task_name = 'send_order_confirmation'
    start_time = time()
    
    try:
        logger.info(f"Sending confirmation for order {order_id}")
        # In a real app, you would send an actual email here
        sleep(1)
        
        # Record successful task execution
        TASK_COUNT.labels(task_name=task_name, status='success').inc()
        TASK_DURATION.labels(task_name=task_name).observe(time() - start_time)
        push_metrics()
        
        return {"status": "sent", "order_id": order_id}
    except Exception as e:
        logger.error(f"Failed to send confirmation for order {order_id}: {e}")
        
        # Record task failure
        TASK_COUNT.labels(task_name=task_name, status='failed').inc()
        TASK_FAILURE.labels(
            task_name=task_name, 
            exception_type=type(e).__name__
        ).inc()
        TASK_DURATION.labels(task_name=task_name).observe(time() - start_time)
        push_metrics()
        
        raise

if __name__ == "__main__":
    # This allows the file to be run directly for testing
    logger.info("Starting Celery worker directly...")
    celery_app.start()