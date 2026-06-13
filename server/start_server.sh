#!/bin/bash

# Navigate to the server directory
cd "$(dirname "$0")"

# Set up Python virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    echo "Installing Python dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt
    deactivate
fi

# Build the Go server
echo "Building Go backend..."
go build -o wheremyphoneat

# Run the Go server
echo "Starting the server..."
./wheremyphoneat
