#!/bin/bash

# For manual testing, run these commands:
curl -s http://localhost:8000/
curl -s http://localhost:8000/trace-test
curl -s http://localhost:8000/health

# Automated version (commented out):
for i in {1..100}; do
  curl -s http://localhost:8000/ > /dev/null
  curl -s http://localhost:8000/trace-test > /dev/null
  curl -s http://localhost:8000/health > /dev/null
  echo "Request $i sent"
  sleep 0.5
done 