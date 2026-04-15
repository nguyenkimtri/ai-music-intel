#!/bin/bash
echo "------------------------------------------------"
echo "🚀 AI Music Intelligence Platform - Auto Updater"
echo "------------------------------------------------"

# 1. Pull latest code
echo "📥 Step 1: Pulling latest code from GitHub..."
git pull origin main --force

# 2. Update Backend
echo "📦 Step 2: Updating Backend dependencies..."
cd backend && npm install
cd ..

# 3. Update Worker
echo "🐍 Step 3: Updating Worker dependencies..."
cd worker && pip install -r requirements.txt
cd ..

# 4. Restart Services
echo "🔄 Step 4: Restarting services with PM2..."
pm2 restart ecosystem.config.js

echo "------------------------------------------------"
echo "✅ UPDATE COMPLETED SUCCESSFULLY!"
echo "------------------------------------------------"
