#!/bin/bash

echo "KodeKloud Records Store - Generating Test Data for Observability"
echo "============================================================="

# Generate logs with trace context
echo "Generating logs with trace context..."
curl -s http://localhost:8000/trace-test
sleep 1

# Generate logs with errors
echo "Generating error logs..."
curl -s http://localhost:8000/error-test
sleep 1

# Attempt to get non-existent product to generate 404 error
echo "Generating 404 error..."
curl -s http://localhost:8000/products/999
sleep 1

# Generate logs with operations
echo "Generating logs with operations..."
curl -s http://localhost:8000/products
sleep 1

# Create a product
echo "Creating a product..."
curl -s http://localhost:8000/products -X POST -H "Content-Type: application/json" -d '{"name":"Vinyl Record", "price":19.99}'
sleep 1

# Create an order
echo "Creating an order..."
curl -s http://localhost:8000/checkout -X POST -H "Content-Type: application/json" -d '{"product_id":1, "quantity":2}'
sleep 1

# Generate slow operation with nested spans
echo "Generating slow operation with nested spans..."
curl -s http://localhost:8000/slow-operation
sleep 1

# Send multiple requests to simulate traffic
echo "Generating traffic..."
for i in {1..5}; do
  curl -s http://localhost:8000/products &
  curl -s http://localhost:8000/orders &
  sleep 0.5
done

echo "Done generating test logs"
echo "Now you can explore the logs in Grafana and traces in Jaeger"
echo "Grafana URL: http://localhost:3000"
echo "Jaeger URL: http://localhost:16686" 