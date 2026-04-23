#!/bin/bash
set -e

echo "Setting up Backend..."
cd backend
pip install -r requirements.txt
pip install transformers torch apify-client

echo "Setting up Frontend..."
cd ../frontend
npm install

# Auto-generate .env from GitHub Codespaces Secrets
echo "Generating .env file from Codespaces Secrets..."
cd ..
cat > .env << EOF
FACEBOOK_APP_ID=${FACEBOOK_APP_ID:-}
FACEBOOK_APP_SECRET=${FACEBOOK_APP_SECRET:-}
FACEBOOK_REDIRECT_URI=${FACEBOOK_REDIRECT_URI:-http://localhost:8000/api/auth/meta/callback}
META_VERIFY_TOKEN=${META_VERIFY_TOKEN:-}
APIFY_API_TOKEN=${APIFY_API_TOKEN:-}
EOF

echo ".env generated successfully!"
echo "Setup Complete! Run: cd backend && uvicorn main:app --reload & cd ../frontend && npm run dev"
