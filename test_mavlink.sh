#\!/bin/bash
# UDP listener test script
echo "Testing UDP port 14550 for MAVLink data..."
echo "Press Ctrl+C to stop"
echo ""
nc -u -l 14550 | hexdump -C | head -20
