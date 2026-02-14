#!/bin/bash

echo "🚀 Generating End-to-End Dashboard Traffic..."

API_URL="http://localhost:8000"

echo "1. Testing basic endpoints..."
curl -s "$API_URL/" > /dev/null
curl -s "$API_URL/health" > /dev/null

echo "2. Creating some products..."
curl -s -X POST "$API_URL/products" \
  -H "Content-Type: application/json" \
  -d '{"name": "Abbey Road", "price": 25.99}' > /dev/null

curl -s -X POST "$API_URL/products" \
  -H "Content-Type: application/json" \
  -d '{"name": "Dark Side of the Moon", "price": 23.50}' > /dev/null

curl -s -X POST "$API_URL/products" \
  -H "Content-Type: application/json" \
  -d '{"name": "Thriller", "price": 19.99}' > /dev/null

echo "3. Browsing products (simulating user journey)..."
for i in {1..5}; do
  curl -s "$API_URL/products" > /dev/null
  sleep 0.5
done

echo "4. Creating orders..."
curl -s -X POST "$API_URL/orders" \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 2}' > /dev/null

curl -s -X POST "$API_URL/orders" \
  -H "Content-Type: application/json" \
  -d '{"product_id": 2, "quantity": 1}' > /dev/null

echo "5. Processing checkouts..."
for i in {1..3}; do
  curl -s -X POST "$API_URL/checkout" \
    -H "Content-Type: application/json" \
    -d '{"product_id": '"$i"', "quantity": 1}' > /dev/null
  sleep 1
done

echo "6. Browsing orders..."
for i in {1..3}; do
  curl -s "$API_URL/orders" > /dev/null
  sleep 0.5
done

echo "7. Generating some test traces..."
curl -s "$API_URL/trace-test" > /dev/null

echo "✅ End-to-end traffic generation complete!"
echo "📊 Check Grafana dashboard in ~30 seconds for data to appear"
echo "🔗 Dashboard: http://localhost:3000"
