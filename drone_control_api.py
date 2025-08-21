#!/usr/bin/env python3
"""
DJI Drone Control API via RosettaDrone
Direct MAVLink control for DJI drones using pymavlink

Author: Dimensional OS Integration
Date: 2024
"""

from pymavlink import mavutil
import time
from typing import Optional, Tuple
import logging

class DJIDroneController:
    """
    Control interface for DJI drones via RosettaDrone MAVLink bridge
    """
    
    def __init__(self, connection_string: str = 'udp:0.0.0.0:14550', timeout: float = 30):
        """
        Initialize drone controller
        
        Args:
            connection_string: MAVLink connection string (default: udp:0.0.0.0:14550)
            timeout: Connection timeout in seconds
        """
        self.connection_string = connection_string
        self.master = None
        self.connected = False
        self.telemetry = {}
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def connect(self) -> bool:
        """
        Connect to drone via MAVLink
        
        Returns:
            True if connection successful
        """
        try:
            self.logger.info(f"Connecting to {self.connection_string}")
            self.master = mavutil.mavlink_connection(self.connection_string)
            self.master.wait_heartbeat(timeout=30)
            self.connected = True
            self.logger.info(f"Connected to system {self.master.target_system}")
            
            # Update initial telemetry
            self.update_telemetry()
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False
    
    def update_telemetry(self, timeout: float = 0.1):
        """Update telemetry data from available messages without blocking"""
        # Read any available telemetry messages without blocking command flow
        end_time = time.time() + timeout
        while time.time() < end_time:
            msg = self.master.recv_match(type=['ATTITUDE', 'GLOBAL_POSITION_INT', 'VFR_HUD', 
                                                'HEARTBEAT', 'SYS_STATUS', 'GPS_RAW_INT'],
                                         blocking=False)
            if not msg:
                break
                
            msg_type = msg.get_type()
            
            if msg_type == 'ATTITUDE':
                self.telemetry['roll'] = msg.roll
                self.telemetry['pitch'] = msg.pitch
                self.telemetry['yaw'] = msg.yaw
                
            elif msg_type == 'GLOBAL_POSITION_INT':
                self.telemetry['lat'] = msg.lat / 1e7
                self.telemetry['lon'] = msg.lon / 1e7
                self.telemetry['alt'] = msg.alt / 1000.0
                
            elif msg_type == 'VFR_HUD':
                self.telemetry['groundspeed'] = msg.groundspeed
                self.telemetry['airspeed'] = msg.airspeed
                self.telemetry['heading'] = msg.heading
                self.telemetry['climb'] = msg.climb
                
            elif msg_type == 'HEARTBEAT':
                self.telemetry['armed'] = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                self.telemetry['mode'] = msg.custom_mode
                
            elif msg_type == 'SYS_STATUS':
                self.telemetry['battery_voltage'] = msg.voltage_battery / 1000.0
                self.telemetry['battery_current'] = msg.current_battery / 100.0
    
    def arm(self, force: bool = False) -> bool:
        """
        Arm the drone motors
        
        Args:
            force: Force arm even if pre-arm checks fail
            
        Returns:
            True if arm successful
        """
        self.logger.info("Arming motors...")
        
        # Update telemetry before sending command
        self.update_telemetry()
        
        # Send arm command with exact same parameters as working script
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1,  # 1 to arm
            0, 0, 0, 0, 0, 0  # All zeros like working script
        )
        
        # Wait for ACK
        ack = self.master.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)
        if ack and ack.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
            if ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                self.logger.info("Arm command accepted")
                
                # Verify armed status by checking heartbeat directly
                for i in range(10):
                    msg = self.master.recv_match(type='HEARTBEAT', blocking=True, timeout=1)
                    if msg:
                        armed = msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
                        if armed:
                            self.logger.info("Motors ARMED successfully!")
                            # Update telemetry with armed status
                            self.telemetry['armed'] = True
                            return True
                    time.sleep(0.5)
            else:
                self.logger.error(f"Arm command failed with result: {ack.result}")
                if ack.result == 4:
                    self.logger.error("Make sure Safety Mode is OFF in RosettaDrone")
                return False
        
        self.logger.error("Failed to arm - no ACK received")
        return False
    
    def disarm(self) -> bool:
        """
        Disarm the drone motors
        
        Returns:
            True if disarm successful
        """
        self.logger.info("Disarming motors...")
        
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0,  # 0 to disarm
            0, 0, 0, 0, 0, 0
        )
        
        time.sleep(1)
        return True
    
    def takeoff(self, altitude: float = 3.0) -> bool:
        """
        Takeoff to specified altitude
        
        Args:
            altitude: Target altitude in meters (default: 3m)
            
        Returns:
            True if takeoff initiated
        """
        self.logger.info(f"Taking off to {altitude}m...")
        
        # Must be in GUIDED mode
        if not self.set_mode('GUIDED'):
            self.logger.error("Failed to set GUIDED mode")
            return False
        
        # Update telemetry to check armed status
        self.update_telemetry()
        
        # Must be armed
        if not self.telemetry.get('armed', False):
            if not self.arm():
                return False
        
        # Send takeoff command
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0, 0, 0, 0, 0, 0,
            altitude
        )
        
        ack = self.master.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)
        if ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
            self.logger.info("Takeoff command accepted")
            
            # After takeoff, send position hold to prevent drift
            time.sleep(2)  # Give it time to start takeoff
            self.hold_position()
            return True
            
        self.logger.error("Takeoff failed")
        return False
    
    def land(self) -> bool:
        """
        Land the drone at current position
        
        Returns:
            True if land command sent
        """
        self.logger.info("Landing...")
        
        # Send explicit LAND command
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0,
            0, 0, 0, 0,  # Empty params
            0, 0, 0  # lat, lon, alt (0 = current position)
        )
        
        # Wait for ACK
        ack = self.master.recv_match(type='COMMAND_ACK', blocking=True, timeout=3)
        if ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
            self.logger.info("Land command accepted")
            return True
        
        # Fallback to LAND mode
        self.logger.info("Trying LAND mode as fallback")
        return self.set_mode('LAND')
    
    def set_mode(self, mode: str) -> bool:
        """
        Set flight mode
        
        Args:
            mode: Flight mode name (STABILIZE, GUIDED, LAND, RTL, etc.)
            
        Returns:
            True if mode change successful
        """
        mode_mapping = {
            'STABILIZE': 0,
            'GUIDED': 4,
            'LOITER': 5,
            'RTL': 6,
            'LAND': 9,
            'POSHOLD': 16
        }
        
        if mode not in mode_mapping:
            self.logger.error(f"Unknown mode: {mode}")
            return False
        
        mode_id = mode_mapping[mode]
        self.logger.info(f"Setting mode to {mode}")
        
        # Update telemetry before sending command
        self.update_telemetry()
        
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id,
            0, 0, 0, 0, 0
        )
        
        ack = self.master.recv_match(type='COMMAND_ACK', blocking=True, timeout=3)
        if ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
            self.logger.info(f"Mode changed to {mode}")
            self.telemetry['mode'] = mode_id
            return True
            
        # Fallback method
        self.master.mav.set_mode_send(
            self.master.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id
        )
        time.sleep(1)
        self.telemetry['mode'] = mode_id
        return True
    
    def move(self, forward: float = 0, right: float = 0, down: float = 0, 
             yaw_rate: float = 0, duration: float = 1.0):
        """
        Move drone with velocity commands
        
        Args:
            forward: Forward velocity in m/s (positive = forward)
            right: Right velocity in m/s (positive = right)
            down: Down velocity in m/s (positive = down)
            yaw_rate: Yaw rate in rad/s
            duration: Duration to maintain velocity in seconds
        """
        self.logger.info(f"Moving: forward={forward}, right={right}, down={down} for {duration}s")
        
        # Send velocity commands for duration
        end_time = time.time() + duration
        while time.time() < end_time:
            self.master.mav.set_position_target_local_ned_send(
                0,  # time_boot_ms
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_FRAME_BODY_NED,
                0b0000111111000111,  # type_mask (only velocities enabled)
                0, 0, 0,  # x, y, z positions (not used)
                forward, right, down,  # velocities in m/s
                0, 0, 0,  # accelerations (not used)
                0, yaw_rate  # yaw, yaw_rate
            )
            time.sleep(0.1)
        
        # Stop movement
        self.stop()
    
    def stop(self):
        """Stop all movement"""
        self.master.mav.set_position_target_local_ned_send(
            0, self.master.target_system, self.master.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_NED,
            0b0000111111000111,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
        )
    
    def hold_position(self):
        """Hold current position (hover in place)"""
        self.logger.info("Holding position")
        # Send zero velocity commands to hold position
        for i in range(5):  # Send multiple times to ensure it's received
            self.master.mav.set_position_target_local_ned_send(
                0,  # time_boot_ms
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_FRAME_BODY_NED,
                0b0000111111000111,  # type_mask (only velocities enabled)
                0, 0, 0,  # positions (not used)
                0, 0, 0,  # zero velocities = hold position
                0, 0, 0,  # accelerations (not used)
                0, 0  # yaw, yaw_rate
            )
            time.sleep(0.1)
    
    def goto(self, lat: float, lon: float, alt: float):
        """
        Fly to GPS position
        
        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees  
            alt: Altitude in meters (relative to home)
        """
        self.logger.info(f"Going to position: {lat}, {lon}, {alt}m")
        
        self.master.mav.set_position_target_global_int_send(
            0,  # time_boot_ms
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            0b0000111111111000,  # type_mask (only positions enabled)
            int(lat * 1e7),  # lat in degrees * 1e7
            int(lon * 1e7),  # lon in degrees * 1e7
            alt,  # alt in meters
            0, 0, 0,  # velocities (not used)
            0, 0, 0,  # accelerations (not used)
            0, 0  # yaw, yaw_rate (not used)
        )
    
    def return_to_home(self) -> bool:
        """
        Return to home position
        
        Returns:
            True if RTL mode set
        """
        self.logger.info("Returning to home...")
        return self.set_mode('RTL')
    
    def release_control(self):
        """Release control back to RC transmitter"""
        self.logger.info("Releasing control to RC...")
        self.stop()
        self.set_mode('STABILIZE')
    
    def get_telemetry(self) -> dict:
        """
        Get current telemetry data
        
        Returns:
            Dictionary with telemetry values
        """
        # Update telemetry before returning
        self.update_telemetry()
        return self.telemetry.copy()
    
    def get_state_string(self) -> str:
        """
        Get formatted state string for monitoring
        
        Returns:
            Formatted string with all telemetry data
        """
        t = self.telemetry
        
        # Mode names mapping
        mode_names = {
            0: 'STABILIZE', 
            4: 'GUIDED', 
            5: 'LOITER', 
            6: 'RTL', 
            9: 'LAND',
            16: 'POSHOLD'
        }
        
        mode = mode_names.get(t.get('mode', -1), f"MODE_{t.get('mode', -1)}")
        armed = "ARMED" if t.get('armed', False) else "DISARMED"
        
        state = f"""
=== DRONE STATE ===
Status: {mode} | {armed}
Position: Lat={t.get('lat', 0):.6f}, Lon={t.get('lon', 0):.6f}, Alt={t.get('alt', 0):.1f}m
Attitude: Roll={t.get('roll', 0):.2f}, Pitch={t.get('pitch', 0):.2f}, Yaw={t.get('yaw', 0):.2f}
Velocity: GS={t.get('groundspeed', 0):.1f}m/s, AS={t.get('airspeed', 0):.1f}m/s, Climb={t.get('climb', 0):.1f}m/s
Heading: {t.get('heading', 0)}°
Battery: {t.get('battery_voltage', 0):.2f}V, {t.get('battery_current', 0):.2f}A
==================
"""
        return state
    
    def print_telemetry_stream(self, duration: float = 30):
        """
        Print telemetry stream for monitoring
        
        Args:
            duration: How long to print telemetry in seconds
        """
        import sys
        end_time = time.time() + duration
        
        print("\nStreaming telemetry (Ctrl+C to stop)...")
        try:
            while time.time() < end_time:
                t = self.telemetry
                
                # Mode and arm status
                mode_names = {0: 'STAB', 4: 'GUID', 5: 'LOIT', 6: 'RTL', 9: 'LAND', 16: 'POSH'}
                mode = mode_names.get(t.get('mode', -1), f"M{t.get('mode', -1)}")
                armed = "ARM" if t.get('armed', False) else "DIS"
                
                # Alternate between different telemetry lines
                msg_type = int(time.time() * 2) % 3
                
                if msg_type == 0:
                    print(f"[STATUS] Mode={t.get('mode', -1)} {armed}")
                elif msg_type == 1:
                    print(f"[HUD] Alt={t.get('alt', 0):.1f}m GS={t.get('groundspeed', 0):.1f}m/s")
                elif msg_type == 2:
                    print(f"[ATT] Roll={t.get('roll', 0):.2f} Pitch={t.get('pitch', 0):.2f} Yaw={t.get('yaw', 0):.2f}")
                    print(f"[GPS] Lat={t.get('lat', 0):.6f} Lon={t.get('lon', 0):.6f} Alt={t.get('alt', 0):.2f}m")
                
                sys.stdout.flush()
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            print("\nTelemetry stream stopped")
    
    def disconnect(self):
        """Disconnect from drone"""
        if self.master:
            self.master.close()
        self.connected = False
        self.logger.info("Disconnected")

# Example usage
if __name__ == "__main__":
    # Create controller
    drone = DJIDroneController()
    
    # Connect
    if drone.connect():
        # Get telemetry
        print(f"Telemetry: {drone.get_telemetry()}")
        
        # Example: Takeoff, move forward, land
        # drone.takeoff(3)
        # time.sleep(5)
        # drone.move(forward=1, duration=2)
        # time.sleep(2)
        # drone.land()
        
        # Disconnect
        drone.disconnect()