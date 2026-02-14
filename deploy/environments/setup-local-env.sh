#!/bin/bash

echo "🔧 Setting up local development environment configuration"
echo "======================================================="

# Check if we're in the right directory
if [ ! -f "docker-compose.yaml" ]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

ENV_DIR="deploy/environments"
TEMPLATE_DIR="$ENV_DIR/templates"

# Function to create env file from template
create_env_file() {
    local env_name=$1
    local template_file="$TEMPLATE_DIR/env.${env_name}.template"
    local env_file="$ENV_DIR/.env.${env_name}"
    
    if [ -f "$env_file" ]; then
        echo "⚠️  $env_file already exists. Backup created as $env_file.backup"
        cp "$env_file" "$env_file.backup"
    fi
    
    echo "📄 Creating $env_file from template..."
    cp "$template_file" "$env_file"
    
    # For development, replace placeholders with safe defaults
    if [ "$env_name" = "dev" ]; then
        sed -i.bak 's/CHANGE_ME_DEV_PASSWORD/dev_password_123/g' "$env_file"
        sed -i.bak 's/CHANGE_ME_GRAFANA_PASSWORD/dev_admin_123/g' "$env_file"
        rm "$env_file.bak"
        echo "✅ Development environment configured with safe defaults"
    else
        echo "⚠️  Remember to replace placeholder values in $env_file"
    fi
}

# Create development environment (safe for local use)
create_env_file "dev"

# For staging and production, just copy templates
echo ""
echo "📝 For staging and production environments:"
echo "   1. Copy the template files manually"
echo "   2. Replace \${VARIABLE} placeholders with actual values"
echo "   3. Store sensitive values in CI/CD secrets, not in files"

echo ""
echo "🎯 Next steps:"
echo "   1. Run: docker-compose --env-file deploy/environments/.env.dev up"
echo "   2. For production: Set up GitHub secrets for sensitive values"
echo ""
echo "🔒 Security reminder: Never commit files with real passwords!"
