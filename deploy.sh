#!/bin/bash
# Open Feis - Deployment Script
# Run this on the server to deploy/update

set -e

echo "🍀 Open Feis Deployment"
echo "======================="

# Navigate to project directory
cd /opt/openfeis

# Pull latest code
echo "📥 Pulling latest code..."
git pull origin main

# Build and restart containers
echo "🔨 Building Docker images..."
docker compose build --no-cache

echo "🚀 Starting services..."
docker compose up -d

# Clean up old images
echo "🧹 Cleaning up..."
docker image prune -f

# Show status
echo ""
echo "✅ Deployment complete!"
echo ""
docker compose ps
echo ""
echo "🌐 Site: https://openfeis.org"
echo "📊 Logs: docker compose logs -f"

