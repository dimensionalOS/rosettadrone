# DJI Drone Control API Documentation

## Overview

This API provides programmatic control of DJI drones (tested with Mavic 2 Pro) through the RosettaDrone Android app, which acts as a MAVLink bridge between the DJI SDK and your control system.

## Architecture

```
Your Python Code <--MAVLink UDP--> RosettaDrone App <--DJI SDK--> DJI Drone
   (Computer)                      (Android Phone)                (Mavic 2 Pro)
```

## Requirements

### Hardware
- DJI Drone (Mavic 2 Pro tested, should work with other DJI drones)
- Android phone/tablet with USB-C
- DJI RC Controller
- Computer on same network as Android device

### Software
- RosettaDrone APK (modified version with bidirectional MAVLink)
- Python 3.7+
- pymavlink (`pip install pymavlink`)

## Installation

```bash
# Install pymavlink
pip install pymavlink

# Copy the API file
cp drone_control_api.py your_project/
```

## Quick Start

```python
from drone_control_api import DJIDroneController
import time

# Create controller instance
drone = DJIDroneController('udp:0.0.0.0:14550')

# Connect to drone
if drone.connect():
    # Arm and takeoff
    drone.takeoff(3)  # Takeoff to 3 meters
    time.sleep(5)
    
    # Move forward 2m/s for 2 seconds
    drone.move(forward=2, duration=2)
    
    # Land
    drone.land()
    
    # Disconnect
    drone.disconnect()
```

## API Reference

### Class: `DJIDroneController`

Main controller class for drone operations.

#### `__init__(connection_string='udp:0.0.0.0:14550', timeout=30)`
Initialize the drone controller.
- `connection_string`: MAVLink connection string
- `timeout`: Connection timeout in seconds

#### `connect() -> bool`
Connect to the drone via MAVLink.
- Returns: `True` if connection successful

#### `arm(force=False) -> bool`
Arm the drone motors.
- `force`: Force arm even if pre-arm checks fail
- Returns: `True` if arm successful

#### `disarm() -> bool`
Disarm the drone motors.
- Returns: `True` if disarm successful

#### `takeoff(altitude=3.0) -> bool`
Takeoff to specified altitude.
- `altitude`: Target altitude in meters
- Returns: `True` if takeoff initiated

#### `land() -> bool`
Land the drone at current position.
- Returns: `True` if land command sent

#### `set_mode(mode) -> bool`
Set flight mode.
- `mode`: Mode name ('STABILIZE', 'GUIDED', 'LAND', 'RTL', 'LOITER', 'POSHOLD')
- Returns: `True` if mode change successful

#### `move(forward=0, right=0, down=0, yaw_rate=0, duration=1.0)`
Move drone with velocity commands.
- `forward`: Forward velocity in m/s (positive = forward)
- `right`: Right velocity in m/s (positive = right)
- `down`: Down velocity in m/s (positive = down)
- `yaw_rate`: Yaw rate in rad/s
- `duration`: How long to maintain velocity

#### `stop()`
Stop all movement immediately.

#### `goto(lat, lon, alt)`
Fly to GPS position.
- `lat`: Latitude in degrees
- `lon`: Longitude in degrees
- `alt`: Altitude in meters (relative to home)

#### `return_to_home() -> bool`
Return to home position.
- Returns: `True` if RTL mode set

#### `release_control()`
Release control back to RC transmitter.

#### `get_telemetry() -> dict`
Get current telemetry data.
- Returns: Dictionary with telemetry values

#### `disconnect()`
Disconnect from drone.

## Telemetry Data

The `get_telemetry()` method returns a dictionary with:

```python
{
    'armed': bool,           # Motor armed status
    'mode': int,             # Flight mode number
    'lat': float,            # Latitude in degrees
    'lon': float,            # Longitude in degrees
    'alt': float,            # Altitude in meters
    'roll': float,           # Roll in radians
    'pitch': float,          # Pitch in radians
    'yaw': float,            # Yaw in radians
    'heading': int,          # Heading in degrees (0-360)
    'groundspeed': float,    # Ground speed in m/s
    'airspeed': float,       # Air speed in m/s
    'climb': float,          # Climb rate in m/s
    'battery_voltage': float,# Battery voltage (Note: often 0 with DJI)
    'battery_current': float # Battery current (Note: often 0 with DJI)
}
```

## Movement Examples

### Basic Movement Pattern
```python
# Square pattern flight
drone.move(forward=2, duration=2)   # Forward 2m/s for 2 seconds
drone.move(right=2, duration=2)     # Right 2m/s for 2 seconds
drone.move(forward=-2, duration=2)  # Backward 2m/s for 2 seconds
drone.move(right=-2, duration=2)    # Left 2m/s for 2 seconds
```

### Diagonal Movement
```python
# Move diagonally forward-right
drone.move(forward=1, right=1, duration=3)
```

### Altitude Changes
```python
# Climb 1m/s for 2 seconds
drone.move(down=-1, duration=2)  # Negative down = up

# Descend 0.5m/s for 2 seconds
drone.move(down=0.5, duration=2)
```

### Rotation
```python
# Rotate at 0.5 rad/s for 2 seconds
drone.move(yaw_rate=0.5, duration=2)
```

## Safety Considerations

### 1. Always Test in Safe Environment
- Test in open area away from people and obstacles
- Start with small movements and low altitudes
- Have RC controller ready for manual override

### 2. RC Override Issue
After sending MAVLink commands, you may temporarily lose RC control. To regain control:
```python
drone.release_control()  # Switches back to STABILIZE mode
```

### 3. Connection Loss Handling
```python
import time

def safe_flight():
    drone = DJIDroneController()
    
    try:
        if not drone.connect():
            print("Failed to connect")
            return
            
        # Your flight code here
        drone.takeoff(2)
        time.sleep(3)
        
    except Exception as e:
        print(f"Error: {e}")
        
    finally:
        # Always try to land and release control
        try:
            drone.land()
            drone.release_control()
            drone.disconnect()
        except:
            pass
```

### 4. Pre-flight Checks
```python
def preflight_check(drone):
    telemetry = drone.get_telemetry()
    
    # Check GPS
    if telemetry.get('lat', 0) == 0:
        print("WARNING: No GPS fix")
        return False
    
    # Check if already armed
    if telemetry.get('armed', False):
        print("WARNING: Drone already armed")
        return False
    
    return True
```

## Integration with dimOS

### As a Robot Module
```python
# dimensional_robots/dji_drone.py

from drone_control_api import DJIDroneController

class DJIDroneRobot:
    def __init__(self, config):
        self.drone = DJIDroneController(config.get('connection', 'udp:0.0.0.0:14550'))
        self.connected = False
        
    def initialize(self):
        """Initialize drone connection"""
        self.connected = self.drone.connect()
        return self.connected
    
    def get_state(self):
        """Get current drone state for AI system"""
        if not self.connected:
            return None
            
        telemetry = self.drone.get_telemetry()
        return {
            'type': 'aerial_robot',
            'position': {
                'lat': telemetry.get('lat', 0),
                'lon': telemetry.get('lon', 0),
                'alt': telemetry.get('alt', 0)
            },
            'orientation': {
                'roll': telemetry.get('roll', 0),
                'pitch': telemetry.get('pitch', 0),
                'yaw': telemetry.get('yaw', 0)
            },
            'velocity': {
                'groundspeed': telemetry.get('groundspeed', 0),
                'climb': telemetry.get('climb', 0)
            },
            'armed': telemetry.get('armed', False)
        }
    
    def execute_command(self, command, params):
        """Execute AI-generated commands"""
        if command == 'takeoff':
            return self.drone.takeoff(params.get('altitude', 3))
        elif command == 'move':
            return self.drone.move(**params)
        elif command == 'goto':
            return self.drone.goto(**params)
        elif command == 'land':
            return self.drone.land()
        elif command == 'rtl':
            return self.drone.return_to_home()
    
    def shutdown(self):
        """Safe shutdown"""
        if self.connected:
            self.drone.land()
            self.drone.release_control()
            self.drone.disconnect()
```

### Video Stream Integration
The video streams to `10.0.0.152:5600` as RTP/H.264. To integrate:

```python
import cv2
import subprocess

def get_video_stream():
    """Get video stream from drone"""
    # Use GStreamer to decode RTP stream
    gst_pipeline = (
        'udpsrc port=5600 ! '
        'application/x-rtp,encoding-name=H264,payload=96 ! '
        'rtph264depay ! h264parse ! avdec_h264 ! '
        'videoconvert ! appsink'
    )
    
    cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
    return cap
```

## Troubleshooting

### Connection Issues
- Verify RosettaDrone shows drone connected (DJI light green)
- Check firewall allows UDP port 14550
- Ensure computer and Android on same network
- Try `adb shell netstat -an | grep 14550` to verify socket

### Control Not Working
- Make sure Safety Mode is OFF in RosettaDrone
- Drone must have GPS fix for GUIDED mode
- Battery must be connected and charged
- Try manual arm with RC first to verify drone is ready

### RC Control Lost After MAVLink Commands
- Use `drone.release_control()` to return to manual mode
- Or switch flight mode on RC controller
- This is a known issue with virtual stick mode

### Altitude/Battery Reading 0
- Known telemetry issue with RosettaDrone
- Doesn't affect actual flight control
- Use GPS altitude or visual confirmation

## Flight Modes

- **STABILIZE (0)**: Manual control, self-leveling
- **GUIDED (4)**: Autonomous control via MAVLink
- **LOITER (5)**: Hold position with GPS
- **RTL (6)**: Return to Launch
- **LAND (9)**: Auto land at current position
- **POSHOLD (16)**: Position hold with manual override

## License

This API is provided as-is for integration with dimensional OS and robotic systems.