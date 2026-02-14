# End-to-End Purchase Journey Observability Guide

## 🎯 Overview

This guide demonstrates **end-to-end visibility** for the KodeKloud Records Store purchase journey, showcasing how to follow a user request from browser click to database response and back through all system components.

## 🏗️ Architecture Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   User      │───▶│ API Gateway │───▶│ FastAPI     │───▶│ Database    │
│  (Browser)  │    │ (nginx)     │    │ Service     │    │ (PostgreSQL)│
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
                                      ┌─────────────┐
                                      │ Background  │
                                      │ Worker      │
                                      │ (Celery)    │
                                      └─────────────┘
                                              │
                                              ▼
                                      ┌─────────────┐
                                      │ Message     │
                                      │ Queue       │
                                      │ (RabbitMQ)  │
                                      └─────────────┘
```

## 🚀 Quick Start

### 1. Start the Complete Stack
```bash
# Start all services with observability stack
docker-compose up -d

# Verify all services are running
docker-compose ps
```

### 2. Access Observability Tools
- **Grafana Dashboard**: http://localhost:3000 (admin/admin)
- **Jaeger Tracing**: http://localhost:16686
- **Prometheus Metrics**: http://localhost:9090
- **Application API**: http://localhost:8000

### 3. Generate Test Traffic
```bash
# Single purchase journey with tracing
./demo_request_correlation.sh

# Manual checkout request
curl -X POST http://localhost:8000/checkout \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 1}'
```

## 📊 Complete Purchase Journey Dashboard

### Dashboard Panels Explained

#### 1. 🛒 Purchase Journey Overview
**What it shows**: High-level health metrics for the checkout process
- Checkout requests per second
- Success rate percentage
- P95 latency in seconds

**Why it matters**: Immediate understanding of system health from a business perspective.

#### 2. 📊 Request Flow Stages
**What it shows**: Request volume through each stage of the journey
- Product browsing rate
- Checkout initiation rate
- Order processing rate
- Email confirmation rate

**Why it matters**: Identifies where users drop off in the conversion funnel.

#### 3. ⏱️ End-to-End Journey Time
**What it shows**: Latency distribution across journey stages
- P50 and P95 checkout API response times
- P95 background order processing time

**Why it matters**: Pinpoints performance bottlenecks in the user experience.

#### 4. 🔍 Distributed Trace Analysis
**What it shows**: Individual trace details from Jaeger
- Trace IDs for detailed investigation
- Operation names and durations
- Error traces for debugging

**Why it matters**: Deep-dive debugging capability for specific user requests.

## 🔗 Request Correlation Pattern

### How It Works
Our system uses **OpenTelemetry trace IDs** to correlate requests across all system components:

```python
# 1. OpenTelemetry automatically generates trace IDs
from opentelemetry import trace

# 2. Trace IDs are included in structured logs
logger.info("Purchase initiated", 
           order_id=order.id, 
           # trace_id automatically included by OpenTelemetry
           )

# 3. Spans capture operation details
with tracer.start_as_current_span("checkout_order") as span:
    span.set_attribute("order.product_id", order.product_id)
    span.set_attribute("order.quantity", order.quantity)
```

### Tracing a Complete Journey

#### Step 1: Generate a Request
```bash
# Use our demo script
./demo_request_correlation.sh

# Or make a manual request
curl -X POST http://localhost:8000/checkout \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 1}'
```

#### Step 2: Find in Logs
```bash
# Query logs by order ID (from demo script output)
docker logs kodekloud-record-store-api | grep "order_id.*7"

# Or search for recent checkout events
docker logs kodekloud-record-store-api | grep "checkout" | tail -5
```

#### Step 3: View in Jaeger
1. Visit: `http://localhost:16686`
2. Search service: `kodekloud-record-store-api`
3. Search operation: `checkout_order`
4. Look for traces with matching order_id

#### Step 4: Check Dashboard
Visit the "KodeKloud Records Store - End-to-End Purchase Journey" dashboard in Grafana.

## 🎯 Key Observability Patterns Demonstrated

### 1. The Three Pillars Integration
- **Metrics**: Request rates, latencies, error rates
- **Logs**: Structured logging with correlation context
- **Traces**: Request flow across service boundaries

### 2. Business Context
- Revenue impact metrics (orders/hour, daily orders)
- Conversion funnel analysis
- Customer experience measurement

### 3. Basic Health Monitoring
- Service availability tracking
- Database connection health
- Background job processing status

## 🔧 Debugging Workflow

### When Something Goes Wrong

#### 1. Start with the Dashboard
- Check the Purchase Journey Overview panel
- Identify which stage has issues
- Look at error rates by journey stage

#### 2. Drill into Logs
```bash
# High error rate in checkout?
docker logs kodekloud-record-store-api | grep "ERROR" | grep "checkout"

# Search for recent events by order ID
docker logs kodekloud-record-store-api | grep "order_id.*7"
```

#### 3. Analyze Traces
- Go to Jaeger UI
- Search by service: `kodekloud-record-store-api`
- Filter by operation: `checkout_order`
- Look for slow or error traces

#### 4. Check Dependencies
- Database connection issues?
- RabbitMQ queue backing up?
- External service timeouts?

## 📈 Performance Analysis

### Latency Breakdown
```
Typical Purchase Journey:
├── Product browsing: ~50ms
├── Checkout API call: ~200ms
│   ├── Product validation: ~20ms
│   ├── Database insert: ~30ms
│   ├── Queue job: ~10ms
│   └── Response: ~10ms
└── Background processing: ~5000ms
    ├── Order processing: ~3000ms
    ├── Email sending: ~2000ms
    └── Cleanup: ~100ms

Total user-facing time: ~250ms
Total end-to-end time: ~5250ms
```

### SLO Targets
- **User-facing checkout**: < 500ms (P95)
- **Complete order processing**: < 10 seconds (P95)
- **Success rate**: > 99.9%
- **Availability**: > 99.95%

## 🚨 Alerting Setup

### Critical Alerts
```yaml
# High checkout error rate
alert: HighCheckoutErrorRate
expr: rate(http_requests_total{endpoint="/checkout",status_code=~"[45].."}[5m]) / rate(http_requests_total{endpoint="/checkout"}[5m]) > 0.05
for: 2m

# Slow checkout performance  
alert: SlowCheckoutPerformance
expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{endpoint="/checkout"}[5m])) > 1.0
for: 5m

# Background job failures
alert: HighJobFailureRate
expr: rate(celery_tasks_total{state="FAILURE"}[5m]) / rate(celery_tasks_total[5m]) > 0.1
for: 1m
```

## 🎓 Learning Exercises

### Exercise 1: Follow a Purchase Journey
1. Run: `./demo_request_correlation.sh`
2. Note the order ID from the output
3. Find the trace ID in the application logs
4. View the complete trace in Jaeger
5. Analyze performance in Grafana dashboard

### Exercise 2: Simulate a Failure
1. Stop the database: `docker stop kodekloud-record-store-db`
2. Generate traffic: `./demo_request_correlation.sh`
3. Observe how errors propagate through the system
4. See how the dashboard shows the impact
5. Restart database: `docker start kodekloud-record-store-db`

### Exercise 3: Load Testing
1. Generate multiple requests:
   ```bash
   for i in {1..10}; do
     curl -X POST http://localhost:8000/checkout \
       -H "Content-Type: application/json" \
       -d '{"product_id": 1, "quantity": 1}'
     sleep 1
   done
   ```
2. Watch the dashboard update in real-time
3. Identify any performance bottlenecks
4. Correlate metrics, logs, and traces

## 📚 Fundamentals Resources

- [OpenTelemetry Getting Started](https://opentelemetry.io/docs/getting-started/)
- [Prometheus Basics](https://prometheus.io/docs/introduction/overview/)
- [Grafana Fundamentals](https://grafana.com/docs/grafana/latest/getting-started/)
- [Structured Logging Best Practices](https://betterstack.com/community/guides/logging/structured-logging/)

## 🎯 Key Takeaways

1. **OpenTelemetry trace IDs** provide automatic request correlation across all system components
2. **End-to-end dashboards** provide business context to technical metrics
3. **The three pillars work together** - metrics show what, logs show why, traces show where
4. **Structured logging** with consistent labeling enables powerful correlation
5. **Start simple** - basic observability provides immediate value

This setup demonstrates fundamental observability patterns that provide immediate value for understanding system behavior. Focus on mastering these basics before moving to advanced techniques. 