#!/bin/bash

# Fly.io Deployment Script for LinkedIn Automation API
# This script automates the deployment process to Fly.io

set -e  # Exit on any error

echo "🚀 Starting Fly.io deployment for LinkedIn Automation API..."

# Check if fly CLI is installed
if ! command -v fly &> /dev/null; then
    echo "❌ Fly CLI is not installed. Please install it first:"
    echo "   curl -L https://fly.io/install.sh | sh"
    exit 1
fi

# Check if user is authenticated
if ! fly auth whoami &> /dev/null; then
    echo "❌ Not authenticated with Fly.io. Please run:"
    echo "   fly auth login"
    exit 1
fi

echo "✅ Fly CLI is installed and authenticated"

# Check if app exists
if ! fly apps list | grep -q "linkedin-automation-api"; then
    echo "📝 Creating new Fly.io app..."
    fly apps create linkedin-automation-api --org personal
else
    echo "✅ App 'linkedin-automation-api' already exists"
fi

# Set secrets if they don't exist
echo "🔐 Setting up environment secrets..."

# Check if secrets are already set
if ! fly secrets list | grep -q "SECRET_KEY"; then
    echo "⚠️  SECRET_KEY not found. Please set it manually:"
    echo "   fly secrets set SECRET_KEY='your-actual-secret-key'"
fi

if ! fly secrets list | grep -q "JWT_SECRET_KEY"; then
    echo "⚠️  JWT_SECRET_KEY not found. Please set it manually:"
    echo "   fly secrets set JWT_SECRET_KEY='your-actual-jwt-secret-key'"
fi

if ! fly secrets list | grep -q "UNIPILE_API_KEY"; then
    echo "⚠️  UNIPILE_API_KEY not found. Please set it manually:"
    echo "   fly secrets set UNIPILE_API_KEY='your-actual-unipile-api-key'"
fi

if ! fly secrets list | grep -q "UNIPILE_WEBHOOK_SECRET"; then
    echo "⚠️  UNIPILE_WEBHOOK_SECRET not found. Please set it manually:"
    echo "   fly secrets set UNIPILE_WEBHOOK_SECRET='your-actual-webhook-secret'"
fi

# Deploy the application
echo "🚀 Deploying application to Fly.io..."
fly deploy

# Wait for deployment to complete
echo "⏳ Waiting for deployment to complete..."
sleep 10

# Check deployment status
echo "📊 Checking deployment status..."
fly status

# Test the application
echo "🧪 Testing application..."
if curl -f https://linkedin-automation-api.fly.dev/ > /dev/null 2>&1; then
    echo "✅ Application is running successfully!"
    echo "🌐 Your app is available at: https://linkedin-automation-api.fly.dev"
else
    echo "❌ Application health check failed. Check logs with:"
    echo "   fly logs"
    exit 1
fi

# Show useful commands
echo ""
echo "📋 Useful commands:"
echo "   View logs: fly logs"
echo "   Check status: fly status"
echo "   SSH into app: fly ssh console"
echo "   Scale app: fly scale count 2"
echo "   Restart app: fly apps restart"

echo ""
echo "🎉 Deployment completed successfully!" 