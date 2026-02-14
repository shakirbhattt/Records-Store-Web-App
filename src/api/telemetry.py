from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry import propagate
import logging
import os
import socket
import time
import sys
logger = logging.getLogger(__name__)

# Use an environment variable to determine the service name
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "kodekloud-record-store-service")

# Global flag to track if telemetry has been set up
_telemetry_initialized = False

# Import all metrics from our centralized metrics module
# This follows best practices by keeping all metrics in one place
from api.metrics import (
    METRICS_REGISTRY,
    # Traffic metrics
    http_requests_total,
    records_operations_total,
    # Latency metrics  
    http_request_duration_seconds,
    order_processing_duration_seconds,
    database_operation_duration_seconds,
    # Error metrics
    http_errors_total,
    application_errors_total,
    database_errors_total,
    # Saturation metrics
    active_connections,
    database_connections_active,
    task_queue_size,
    # Business metrics
    records_inventory_total,
    sales_revenue_total,
    customers_active_total,
    # Helper functions
    normalize_route,
    get_error_class
)

# For backward compatibility, create aliases to the old metric names
# Students can gradually migrate to the new naming convention
custom_registry = METRICS_REGISTRY

# CAPSTONE TODO: Students should add their own SLI metrics here
# Examples: login_attempts_total, search_requests_duration, checkout_success_rate, etc.

def setup_telemetry(service_name=None):
    """Initialize OpenTelemetry with the given service name"""
    global _telemetry_initialized
    
    # Use provided service name or environment variable
    actual_service_name = service_name or SERVICE_NAME
    
    logger.info(f"🔍 Attempting to set up OpenTelemetry for service: {actual_service_name}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Current working directory: {os.getcwd()}")
    
    # Only set up once
    if _telemetry_initialized:
        logger.info(f"⚠️ Telemetry already initialized, ignoring setup for {actual_service_name}")
        return False
    
    # Test network connectivity to Jaeger
    try:
        logger.info(f"🌐 Testing network connectivity to Jaeger OTLP endpoint...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("jaeger", 4317))  # OTLP gRPC port
        s.close()
        logger.info("✅ Network connection to Jaeger OTLP endpoint successful")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Jaeger OTLP endpoint: {e}")
    
    try:
        logger.info(f"🔧 Creating TracerProvider for {actual_service_name}")
        # Create a TracerProvider with proper resource
        resource = Resource.create({
            "service.name": actual_service_name,
            "service.instance.id": socket.gethostname(),
            "deployment.environment": "development"
        })
        
        provider = TracerProvider(resource=resource)
        
        logger.info(f"🔌 Configuring OTLP Exporter")
        # Use OTLP gRPC exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint="jaeger:4317",
            insecure=True
        )
        
        logger.info(f"➕ Adding BatchSpanProcessor")
        # Add Span Processor
        provider.add_span_processor(
            BatchSpanProcessor(otlp_exporter)
        )
        
        logger.info(f"🔄 Setting global TracerProvider")
        # Set the global TracerProvider
        trace.set_tracer_provider(provider)
        
        # Set up context propagation
        logger.info(f"🔗 Setting up W3C trace context propagation")
        propagate.set_global_textmap(TraceContextTextMapPropagator())
        
        _telemetry_initialized = True
        
        # Create a test span to verify tracing works
        logger.info(f"🧪 Creating test span")
        tracer = get_tracer("telemetry_setup")
        with tracer.start_as_current_span("telemetry_test_span") as span:
            span.set_attribute("test.attribute", "test-value")
            span.set_attribute("service.name", actual_service_name)
            logger.info("✅ Created test span during telemetry setup")
            # Sleep briefly to allow span to be exported
            time.sleep(0.5)
        
        logger.info(f"✅ OpenTelemetry setup complete for {actual_service_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Error setting up OpenTelemetry: {e}", exc_info=True)
        return False

def get_tracer(name):
    """Get a tracer with the given name"""
    return trace.get_tracer(name)