"""
Prometheus Metrics for KodeKloud Records Store API

This module defines all Prometheus metrics following best practices:
1. Consistent naming with application prefix
2. Appropriate metric types for different use cases
3. Well-designed labels to avoid high cardinality
4. Standard histogram buckets
5. Clear documentation for students

Best Practices Applied:
- Metric names: <namespace>_<subsystem>_<name>_<unit>
- Labels: Keep cardinality low, use route patterns not full URLs
- Histograms: Use default buckets unless specific SLA requirements
- Organization: Group by Four Golden Signals (Latency, Traffic, Errors, Saturation)
"""

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
from typing import Optional

# Create a custom registry to avoid conflicts with default metrics
# This allows us to control exactly which metrics are exposed
METRICS_REGISTRY = CollectorRegistry()

# =============================================================================
# FOUR GOLDEN SIGNALS - METRICS ORGANIZATION
# =============================================================================

# -----------------------------------------------------------------------------
# 1. TRAFFIC METRICS - How much demand is being placed on your system?
# -----------------------------------------------------------------------------

# Total HTTP requests received
http_requests_total = Counter(
    name='kodekloud_http_requests_total',
    documentation='Total number of HTTP requests received',
    labelnames=['method', 'route', 'status_code'],
    registry=METRICS_REGISTRY
)

# Business-specific traffic metrics
records_operations_total = Counter(
    name='kodekloud_records_operations_total', 
    documentation='Total number of record operations (CRUD)',
    labelnames=['operation', 'status'],  # operation: create, read, update, delete
    registry=METRICS_REGISTRY
)

# -----------------------------------------------------------------------------
# 2. LATENCY METRICS - How long it takes to service requests?
# -----------------------------------------------------------------------------

# HTTP request duration using default buckets (recommended)
# Default buckets: [.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, +Inf]
http_request_duration_seconds = Histogram(
    name='kodekloud_http_request_duration_seconds',
    documentation='Time spent processing HTTP requests in seconds',
    labelnames=['method', 'route'],
    registry=METRICS_REGISTRY
    # Using default buckets - good for most web applications
)

# Business process latency with custom buckets for specific SLA requirements
order_processing_duration_seconds = Histogram(
    name='kodekloud_order_processing_duration_seconds',
    documentation='Time taken to process an order from start to completion',
    labelnames=['order_type'],  # e.g., 'standard', 'express', 'bulk'
    # Custom buckets based on business SLA: 95% under 5s, 99% under 30s
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, float('inf')],
    registry=METRICS_REGISTRY
)

# Database operation latency
database_operation_duration_seconds = Histogram(
    name='kodekloud_database_operation_duration_seconds',
    documentation='Time spent on database operations',
    labelnames=['operation', 'table'],  # operation: select, insert, update, delete
    registry=METRICS_REGISTRY
)

# -----------------------------------------------------------------------------
# 3. ERROR METRICS - How many requests are failing?
# -----------------------------------------------------------------------------

# HTTP errors by type
http_errors_total = Counter(
    name='kodekloud_http_errors_total',
    documentation='Total number of HTTP errors',
    labelnames=['method', 'route', 'error_code'],  # error_code: 4xx, 5xx
    registry=METRICS_REGISTRY
)

# Application-specific errors
application_errors_total = Counter(
    name='kodekloud_application_errors_total',
    documentation='Total number of application-level errors',
    labelnames=['error_type', 'component'],  # error_type: validation, business_logic, integration
    registry=METRICS_REGISTRY
)

# Database errors
database_errors_total = Counter(
    name='kodekloud_database_errors_total',
    documentation='Total number of database errors',
    labelnames=['error_type', 'operation'],  # error_type: connection, timeout, constraint
    registry=METRICS_REGISTRY
)

# -----------------------------------------------------------------------------
# 4. SATURATION METRICS - How "full" your service is?
# -----------------------------------------------------------------------------

# Current active connections/requests
active_connections = Gauge(
    name='kodekloud_active_connections_current',
    documentation='Current number of active connections',
    registry=METRICS_REGISTRY
)

# Database connection pool usage
database_connections_active = Gauge(
    name='kodekloud_database_connections_active',
    documentation='Number of active database connections',
    registry=METRICS_REGISTRY
)

database_connections_max = Gauge(
    name='kodekloud_database_connections_max',
    documentation='Maximum number of database connections in pool',
    registry=METRICS_REGISTRY
)

# Queue depth for async processing
task_queue_size = Gauge(
    name='kodekloud_task_queue_size_current',
    documentation='Current number of tasks waiting in queue',
    labelnames=['queue_name'],
    registry=METRICS_REGISTRY
)

# =============================================================================
# BUSINESS METRICS - Domain-specific measurements
# =============================================================================

# Inventory levels (business saturation metric)
records_inventory_total = Gauge(
    name='kodekloud_records_inventory_total',
    documentation='Current inventory count by record type',
    labelnames=['record_type', 'genre'],
    registry=METRICS_REGISTRY
)

# Revenue tracking
sales_revenue_total = Counter(
    name='kodekloud_sales_revenue_total',
    documentation='Total revenue from sales in cents',
    labelnames=['currency'],
    registry=METRICS_REGISTRY
)

# Customer metrics
customers_active_total = Gauge(
    name='kodekloud_customers_active_total',
    documentation='Number of active customers',
    registry=METRICS_REGISTRY
)

# =============================================================================
# HELPER FUNCTIONS FOR COMMON METRIC PATTERNS
# =============================================================================

def normalize_route(path: str) -> str:
    """
    Normalize URL paths to avoid high cardinality in metrics.
    
    Examples:
    - /users/123 -> /users/{id}
    - /records/456/reviews -> /records/{id}/reviews
    - /api/v1/orders/789 -> /api/v1/orders/{id}
    
    This prevents creating separate metric series for each unique ID.
    """
    import re
    
    # Replace numeric IDs with {id}
    path = re.sub(r'/\d+', '/{id}', path)
    
    # Replace UUIDs with {uuid}
    path = re.sub(r'/[a-f0-9\-]{36}', '/{uuid}', path)
    
    # Replace other potential high-cardinality values
    path = re.sub(r'/[a-f0-9]{32}', '/{hash}', path)
    
    return path

def get_error_class(status_code: int) -> str:
    """
    Convert HTTP status codes to error classes to reduce cardinality.
    
    Returns: '2xx', '3xx', '4xx', '5xx'
    """
    return f"{status_code // 100}xx"

# =============================================================================
# USAGE EXAMPLES
# =============================================================================

"""
EXAMPLE USAGE IN MIDDLEWARE:

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    
    # Get normalized route to avoid high cardinality
    route = normalize_route(request.url.path)
    method = request.method
    
    try:
        response = await call_next(request)
        status_code = response.status_code
        
        # Record successful request
        http_requests_total.labels(
            method=method,
            route=route,
            status_code=status_code
        ).inc()
        
        # Record request duration
        duration = time.time() - start_time
        http_request_duration_seconds.labels(
            method=method,
            route=route
        ).observe(duration)
        
        # Record errors if applicable
        if status_code >= 400:
            http_errors_total.labels(
                method=method,
                route=route,
                error_code=get_error_class(status_code)
            ).inc()
        
        return response
        
    except Exception as e:
        # Record application errors
        application_errors_total.labels(
            error_type=type(e).__name__,
            component="middleware"
        ).inc()
        raise

EXAMPLE BUSINESS METRIC USAGE:

# When processing an order
start_time = time.time()
try:
    process_order(order)
    order_processing_duration_seconds.labels(
        order_type=order.type
    ).observe(time.time() - start_time)
except ValidationError:
    application_errors_total.labels(
        error_type="validation",
        component="order_processor"
    ).inc()
    raise
"""
