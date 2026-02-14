#!/bin/bash

# Simple black-box monitoring script
# In production, you would use a proper monitoring service like Pingdom, Datadog, etc.

while true; do
  echo "Performing health check..."
  
  # Check API health endpoint
  response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
  
  if [ $response -eq 200 ]; then
    echo "API is healthy (HTTP $response)"
  else
    echo "API is unhealthy (HTTP $response)"
    # In a real environment, this would trigger an alert
  fi
  
  # Check response time (simulating user experience)
  start_time=$(date +%s.%N)
  curl -s http://localhost:8000/ > /dev/null
  end_time=$(date +%s.%N)
  
  duration=$(echo "$end_time - $start_time" | bc)
  echo "Response time: ${duration}s"
  
  if (( $(echo "$duration > 1.0" | bc -l) )); then
    echo "Warning: Response time exceeds 1 second"
    # In a real environment, this would trigger an alert
  fi
  
  echo "-----------------------------------"
  sleep 30
done 