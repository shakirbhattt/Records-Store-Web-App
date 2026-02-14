#!/bin/bash

# Environment Configuration Validation Script
# Usage: ./scripts/validate_env.sh <env_file>

ENV_FILE=$1

if [ -z "$ENV_FILE" ]; then
    echo "Usage: $0 <env_file>"
    echo "Example: $0 .env.dev"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Environment file not found: $ENV_FILE"
    exit 1
fi

echo "🔍 Validating $ENV_FILE..."

# Check required variables exist
required_vars=(
    "POSTGRES_HOST"
    "POSTGRES_DB" 
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
    "DEBUG"
    "LOG_LEVEL"
    "GRAFANA_ADMIN_PASSWORD"
    "ENVIRONMENT"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if ! grep -q "^${var}=" "$ENV_FILE"; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "❌ Missing required variables:"
    printf '   - %s\n' "${missing_vars[@]}"
    exit 1
fi

# Check for security issues
security_issues=()

# Check for weak passwords in non-dev environments
if [[ "$ENV_FILE" != *".dev"* ]]; then
    if grep -q "password123\|admin123\|secret123\|password\|admin" "$ENV_FILE"; then
        security_issues+=("Weak passwords detected")
    fi
fi

# Check for debug mode in production
if [[ "$ENV_FILE" == *".prod"* ]]; then
    if grep -q "DEBUG=true" "$ENV_FILE"; then
        security_issues+=("Debug mode enabled in production")
    fi
fi

# Check for proper log levels
log_level=$(grep "^LOG_LEVEL=" "$ENV_FILE" | cut -d'=' -f2)
if [[ "$ENV_FILE" == *".prod"* ]] && [[ "$log_level" != "WARNING" && "$log_level" != "ERROR" ]]; then
    security_issues+=("Log level too verbose for production")
fi

if [ ${#security_issues[@]} -gt 0 ]; then
    echo "⚠️  Security warnings:"
    printf '   - %s\n' "${security_issues[@]}"
    if [[ "$ENV_FILE" == *".prod"* ]]; then
        echo "❌ Security issues found in production config - validation failed"
        exit 1
    fi
fi

# Validate environment-specific settings
env_name=$(grep "^ENVIRONMENT=" "$ENV_FILE" | cut -d'=' -f2)
case "$env_name" in
    "development")
        if ! grep -q "DEBUG=true" "$ENV_FILE"; then
            echo "⚠️  Development environment should have DEBUG=true"
        fi
        ;;
    "staging"|"production")
        if grep -q "DEBUG=true" "$ENV_FILE"; then
            echo "❌ $env_name environment should have DEBUG=false"
            exit 1
        fi
        ;;
    *)
        echo "❌ Invalid environment name: $env_name"
        exit 1
        ;;
esac

echo "✅ $ENV_FILE validation passed"

# Display configuration summary
echo ""
echo "📊 Configuration Summary:"
echo "   Environment: $env_name"
echo "   Database: $(grep "^POSTGRES_DB=" "$ENV_FILE" | cut -d'=' -f2)"
echo "   Debug Mode: $(grep "^DEBUG=" "$ENV_FILE" | cut -d'=' -f2)"
echo "   Log Level: $(grep "^LOG_LEVEL=" "$ENV_FILE" | cut -d'=' -f2)"
