#!/bin/bash

cd "$(dirname "$0")"

# Start the Flask app with gunicorn
source venv/bin/activate
gunicorn app:app --bind 0.0.0.0:8081 --workers 4 --threads 2 --timeout 120 &
APP_PID=$!

# Start Cloudflare tunnel
cloudflared tunnel run taropopsicle &
TUNNEL_PID=$!

echo "App running (PID: $APP_PID) on http://localhost:8081"
echo "Tunnel running (PID: $TUNNEL_PID) → taropopsicle.com"
echo "Press Ctrl+C to stop both"

# Trap Ctrl+C to kill both processes
trap "kill $APP_PID $TUNNEL_PID 2>/dev/null; exit" INT TERM

# Wait for either process to exit
wait
