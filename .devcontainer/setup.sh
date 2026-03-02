#!/bin/bash
echo "Setting up Backend..."
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install transformers torch

echo "Setting up Frontend..."
cd ../frontend
npm install

echo "Setup Complete! You can now run the application."
