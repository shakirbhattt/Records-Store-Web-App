from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Path
from sqlalchemy.orm import Session
from api.database import get_db
from api.models import Product, Order
from api.worker import process_order, send_order_confirmation
from pydantic import BaseModel
from api.telemetry import get_tracer
import logging
import json
import time
import random
from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode

router = APIRouter()

# Create structured logger
class StructuredLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
    
    def info(self, msg, **kwargs):
        # Add trace context
        span = trace.get_current_span()
        span_context = span.get_span_context()
        
        # Format as JSON directly
        log_data = {
            "message": msg,
            "level": "INFO",
            "trace_id": format(span_context.trace_id, "032x") if span_context.is_valid else None,
            "span_id": format(span_context.span_id, "016x") if span_context.is_valid else None,
            **kwargs
        }
        # Use dict instead of string
        self.logger.info(log_data)
    
    def error(self, msg, **kwargs):
        # Add trace context
        span = trace.get_current_span()
        span_context = span.get_span_context()
        
        # Format as JSON directly
        log_data = {
            "message": msg,
            "level": "ERROR",
            "trace_id": format(span_context.trace_id, "032x") if span_context.is_valid else None,
            "span_id": format(span_context.span_id, "016x") if span_context.is_valid else None,
            **kwargs
        }
        # Use dict instead of string
        self.logger.error(log_data)

# Use structured logger
logger = StructuredLogger(__name__)

# Get a tracer
tracer = get_tracer(__name__)

# Product Schema
class ProductCreate(BaseModel):
    name: str
    price: float

# Order Schema
class OrderCreate(BaseModel):
    product_id: int
    quantity: int

@router.get("/products")
def get_products(db: Session = Depends(get_db)):
    with tracer.start_as_current_span("get_products") as span:
        span.set_attribute("operation", "fetch_all_products")
        start_time = time.time()
        
        try:
            products = db.query(Product).all()
            duration = time.time() - start_time
            span.set_attribute("products.count", len(products))
            span.set_attribute("query.duration_ms", duration * 1000)
            
            logger.info(
                "products_fetched",
                count=len(products),
                duration_ms=round(duration * 1000, 2),
                operation="get_products"
            )
            return products
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(e)
            logger.error(
                "products_fetch_error",
                error=str(e),
                error_type=type(e).__name__,
                operation="get_products"
            )
            raise

@router.post("/products")
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    with tracer.start_as_current_span("create_product") as span:
        span.set_attribute("product.name", product.name)
        span.set_attribute("product.price", product.price)
        
        try:
            db_product = Product(name=product.name, price=product.price)
            db.add(db_product)
            db.commit()
            db.refresh(db_product)
            
            span.set_attribute("product.id", db_product.id)
            logger.info(
                "product_created",
                product_id=db_product.id,
                product_name=db_product.name,
                product_price=db_product.price,
                operation="create_product"
            )
            return db_product
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(e)
            logger.error(
                "product_creation_error",
                product_name=product.name,
                error=str(e),
                error_type=type(e).__name__,
                operation="create_product"
            )
            raise

@router.post("/checkout")
def checkout(order: OrderCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    with tracer.start_as_current_span("checkout_order") as span:
        span.set_attribute("order.product_id", order.product_id)
        span.set_attribute("order.quantity", order.quantity)
        
        try:
            # Verify product exists
            with tracer.start_as_current_span("verify_product") as product_span:
                product = db.query(Product).filter(Product.id == order.product_id).first()
                product_span.set_attribute("product.found", product is not None)
                
                if not product:
                    error_msg = f"Product with ID {order.product_id} not found"
                    product_span.set_status(Status(StatusCode.ERROR))
                    product_span.set_attribute("error.message", error_msg)
                    logger.error(
                        "product_not_found",
                        product_id=order.product_id,
                        operation="checkout"
                    )
                    raise HTTPException(status_code=404, detail=error_msg)
                
                product_span.set_attribute("product.name", product.name)
                product_span.set_attribute("product.price", product.price)

            # Simulate occasional latency
            if random.random() < 0.2:  # 20% chance of delay
                with tracer.start_as_current_span("processing_delay"):
                    delay = random.uniform(0.5, 2.0)
                    time.sleep(delay)
                    logger.info(
                        "processing_delay",
                        delay_seconds=round(delay, 2),
                        operation="checkout"
                    )

            # Create order record in database
            with tracer.start_as_current_span("create_order_record") as create_span:
                db_order = Order(product_id=order.product_id, quantity=order.quantity)
                db.add(db_order)
                db.commit()
                db.refresh(db_order)
                create_span.set_attribute("order.id", db_order.id)
            
            # Send to Celery for background processing
            with tracer.start_as_current_span("queue_background_processing") as queue_span:
                order_data = {"product_id": order.product_id, "quantity": order.quantity}
                task = process_order.delay(order_data)
                queue_span.set_attribute("task.id", task.id)
            
            # Queue confirmation email
            background_tasks.add_task(send_order_confirmation.delay, db_order.id)

            logger.info(
                "order_placed",
                order_id=db_order.id,
                product_id=order.product_id,
                quantity=order.quantity,
                task_id=task.id,
                operation="checkout"
            )
            
            span.set_attribute("order.id", db_order.id)
            span.set_attribute("order.task_id", task.id)
            
            return {
                "message": "Order received, processing in the background",
                "order_id": db_order.id,
                "task_id": task.id
            }
        except HTTPException as he:
            # Re-raise HTTP exceptions without additional logging
            span.set_status(Status(StatusCode.ERROR))
            span.set_attribute("error.status_code", he.status_code)
            span.set_attribute("error.detail", he.detail)
            raise
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(e)
            logger.error(
                "checkout_error",
                product_id=order.product_id,
                quantity=order.quantity,
                error=str(e),
                error_type=type(e).__name__,
                operation="checkout"
            )
            raise

@router.get("/orders")
def get_orders(db: Session = Depends(get_db)):
    with tracer.start_as_current_span("get_orders") as span:
        try:
            orders = db.query(Order).all()
            span.set_attribute("orders.count", len(orders))
            logger.info(
                "orders_fetched",
                count=len(orders),
                operation="get_orders"
            )
            return orders
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(e)
            logger.error(
                "orders_fetch_error",
                error=str(e),
                error_type=type(e).__name__,
                operation="get_orders"
            )
            raise

@router.post("/orders")
def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("order.product_id", order.product_id)
        span.set_attribute("order.quantity", order.quantity)
        
        try:
            # Verify product exists
            with tracer.start_as_current_span("verify_product") as product_span:
                product = db.query(Product).filter(Product.id == order.product_id).first()
                product_span.set_attribute("product.found", product is not None)
                
                if not product:
                    error_msg = f"Product with ID {order.product_id} not found"
                    product_span.set_status(Status(StatusCode.ERROR))
                    product_span.set_attribute("error.message", error_msg)
                    logger.error(
                        "product_not_found_order",
                        product_id=order.product_id,
                        operation="create_order"
                    )
                    raise HTTPException(status_code=404, detail=error_msg)

            # Create order record in database
            db_order = Order(product_id=order.product_id, quantity=order.quantity, status="pending")
            db.add(db_order)
            db.commit()
            db.refresh(db_order)
            
            span.set_attribute("order.id", db_order.id)
            logger.info(
                "order_created",
                order_id=db_order.id,
                product_id=order.product_id,
                quantity=order.quantity,
                operation="create_order"
            )
            
            return {
                "message": "Order created successfully",
                "order_id": db_order.id,
                "status": "pending"
            }
        except HTTPException as he:
            # Re-raise HTTP exceptions without additional logging
            span.set_status(Status(StatusCode.ERROR))
            span.set_attribute("error.status_code", he.status_code)
            span.set_attribute("error.detail", he.detail)
            raise
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(e)
            logger.error(
                "order_creation_error",
                product_id=order.product_id,
                quantity=order.quantity,
                error=str(e),
                error_type=type(e).__name__,
                operation="create_order"
            )
            raise

# New endpoint to manually process an order
@router.post("/orders/{order_id}/process")
def process_specific_order(
    order_id: int = Path(..., title="The ID of the order to process"),
    db: Session = Depends(get_db)
):
    with tracer.start_as_current_span("process_specific_order") as span:
        span.set_attribute("order.id", order_id)
        
        try:
            # Check if order exists
            with tracer.start_as_current_span("verify_order") as order_span:
                order = db.query(Order).filter(Order.id == order_id).first()
                order_span.set_attribute("order.found", order is not None)
                
                if not order:
                    error_msg = f"Order with ID {order_id} not found"
                    order_span.set_status(Status(StatusCode.ERROR))
                    order_span.set_attribute("error.message", error_msg)
                    logger.error(
                        "order_not_found",
                        order_id=order_id,
                        operation="process_specific_order"
                    )
                    raise HTTPException(status_code=404, detail=error_msg)
            
            # Send to Celery for processing
            with tracer.start_as_current_span("queue_background_processing") as queue_span:
                order_data = {"product_id": order.product_id, "quantity": order.quantity}
                task = process_order.delay(order_data)
                queue_span.set_attribute("task.id", task.id)
            
            span.set_attribute("task.id", task.id)
            logger.info(
                "manual_processing_triggered",
                order_id=order_id,
                task_id=task.id,
                operation="process_specific_order"
            )
            
            return {
                "message": f"Order {order_id} processing triggered",
                "order_id": order_id,
                "task_id": task.id
            }
        except HTTPException as he:
            # Re-raise HTTP exceptions without additional logging
            span.set_status(Status(StatusCode.ERROR))
            span.set_attribute("error.status_code", he.status_code)
            span.set_attribute("error.detail", he.detail)
            raise
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(e)
            logger.error(
                "order_processing_error",
                order_id=order_id,
                error=str(e),
                error_type=type(e).__name__,
                operation="process_specific_order"
            )
            raise

# Add a new endpoint for demonstrating slow requests and tracing
@router.get("/slow-operation")
def slow_operation():
    with tracer.start_as_current_span("slow_operation") as span:
        span.set_attribute("operation.type", "demo_slow")
        
        # Log the start of the slow operation
        logger.info(
            "slow_operation_started",
            operation="slow_operation"
        )
        
        # Perform a series of nested operations with delays
        with tracer.start_as_current_span("database_simulation") as db_span:
            db_span.set_attribute("database.operation", "query")
            time.sleep(0.3)  # Simulate DB query
            
            # Add another level of nesting
            with tracer.start_as_current_span("data_processing") as proc_span:
                proc_span.set_attribute("processing.type", "aggregation")
                time.sleep(0.5)  # Simulate processing
                
                # Log processing step
                logger.info(
                    "data_processing_step",
                    duration_ms=500,
                    operation="data_processing"
                )
                
        # Random chance of error for demonstration
        if random.random() < 0.3:  # 30% chance of error
            with tracer.start_as_current_span("error_simulation") as error_span:
                error_span.set_status(Status(StatusCode.ERROR))
                error_span.set_attribute("error.type", "RandomFailure")
                
                logger.error(
                    "random_failure",
                    reason="Simulated random failure for demonstration",
                    operation="slow_operation"
                )
                
                return {"status": "error", "message": "Random failure occurred"}
        
        # Log completion
        logger.info(
            "slow_operation_completed",
            duration_ms=800,
            operation="slow_operation"
        )
        
        return {"status": "success", "message": "Slow operation completed", "duration_ms": 800}