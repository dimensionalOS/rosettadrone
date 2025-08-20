#\!/bin/bash
echo "=== Simple MAVLink Monitor ==="
echo "Listening on port 14550 for MAVLink packets from RosettaDrone..."
echo "If you see hex data starting with FE or FD, MAVLink is working\!"
echo "Press Ctrl+C to stop"
echo ""
nc -u -l 14550 | xxd | head -20
