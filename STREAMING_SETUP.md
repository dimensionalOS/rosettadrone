# RosettaDrone Video & MAVLink Streaming Setup

This guide documents the setup and debugging process for streaming video and MAVLink telemetry from a DJI Mavic 2 Pro to a computer using RosettaDrone on Android 15.

## Overview

- **Drone**: DJI Mavic 2 Pro
- **Android Device**: Samsung S24 FE (Android 15 / One UI 7.0)
- **RosettaDrone**: MAVLink wrapper for DJI drones
- **Computer IP**: 10.0.0.152
- **Video Port**: 5600 (UDP/RTP)
- **MAVLink Port**: 14550 (UDP)

## Initial Android Setup

### 1. Enable Developer Mode & USB Debugging
On your Android device:
1. Go to **Settings → About phone → Software information**
2. Tap **Build number** 7 times to enable Developer Mode
3. Go back to **Settings → Developer options**
4. Enable **USB debugging**
5. Enable **Wireless debugging** (optional, for WiFi ADB)

### 2. Connect via USB and Setup ADB
Connect your Android device to your computer via USB:

```bash
# Install ADB if not already installed
sudo apt install android-tools-adb

# Check if device is detected
adb devices

# If you see "unauthorized", check your phone and approve the computer

# Setup TCP/IP connection for wireless debugging
adb tcpip 5555

# Get the Android device's IP address
adb shell ip addr show wlan0 | grep "inet " | awk '{print $2}' | cut -d/ -f1

# Connect wirelessly (replace with your device's IP)
adb connect 192.168.1.xxx:5555

# Now you can unplug the USB cable and use ADB wirelessly

# Install the APK
adb install app/build/outputs/apk/debug/app-debug.apk

# Monitor logs
adb logcat | grep -E "MainActivity|VideoService|RtpSocket"
```

### 3. Build and Install RosettaDrone

```bash
# Clone the repository
git clone https://github.com/RosettaDrone/rosettadrone.git
cd rosettadrone

# Build the APK
./gradlew assembleDebug

# Install via ADB
adb install app/build/outputs/apk/debug/app-debug.apk

# Or install release version
./gradlew assembleRelease
adb install app/build/outputs/apk/release/app-release.apk
```

## Key Issues Fixed

### 1. Android 15 Compatibility
**Problem**: App wouldn't install with "App not compatible with phone" error.

**Solution**: Modified `AndroidManifest.xml` to make USB accessory optional:
```xml
<uses-feature android:name="android.hardware.usb.accessory" android:required="false" />
```

### 2. Video Service Not Binding
**Problem**: VideoService was commented out in AndroidManifest.xml, preventing video streaming.

**Solution**: Uncommented the service declaration:
```xml
<service android:name="sq.rogue.rosettadrone.video.VideoService">
</service>
```

### 3. Video Listener Null Pointer
**Problem**: `mReceivedVideoDataListener` was null when `onDroneConnected()` was called, causing video registration to fail.

**Solution**: Created the video listener in `onCreate()` before drone connection:
```java
private void createVideoListener() {
    mReceivedVideoDataListener = (videoBuffer, size) -> {
        // Process video data
        if (mExternalVideoOut == true) {
            NativeHelper.getInstance().parse(videoBuffer, size, parserMode);
        }
    };
}
```

### 4. Wrong IP Address for Streaming
**Problem**: Video was streaming to 127.0.0.1 instead of external IP 10.0.0.152.

**Solution**: Fixed `getVideoIP()` to return external GCS IP when external video is enabled:
```java
private String getVideoIP() {
    if (mExternalVideoOut && !prefs.getBoolean("pref_separate_gcs", false)) {
        return getGCSAddress();  // Returns 10.0.0.152
    }
    return prefs.getString("pref_video_ip", "127.0.0.1");
}
```

### 5. Camera Mode for Video Streaming
**Problem**: DJI SDK doesn't send video data when camera is in PHOTO mode.

**Solution**: Set camera to VIDEO mode when initializing video feed:
```java
if (mProduct != null && mProduct.getCamera() != null) {
    mProduct.getCamera().setMode(SettingsDefinitions.CameraMode.RECORD_VIDEO, djiError -> {
        if (djiError == null) {
            // Create codec manager after camera is in video mode
            if (mCodecManager == null) {
                mCodecManager = new DJICodecManager(getApplicationContext(), 
                    (SurfaceTexture)null, 1920, 1080);
            }
        }
    });
}
```

### 6. Mavic 2 Pro Requires Transcoded Feed
**Problem**: Mavic 2 Pro sends H.265 video which needs special handling.

**Solution**: Use transcoded video feed for Mavic 2 models:
```java
VideoFeeder.VideoFeed videoFeed = null;
if (mProduct.getModel() == Model.MAVIC_2_PRO || mProduct.getModel() == Model.MAVIC_2_ZOOM) {
    videoFeed = videoFeeder.provideTranscodedVideoFeed();
} else {
    videoFeed = videoFeeder.getPrimaryVideoFeed();
}
```

## Setup Instructions

### 1. Configure RosettaDrone App

In the RosettaDrone app settings:
- **Enable External Video**: Toggle ON "Use Custom Decoder"
- **GCS IP Address**: Set to your computer's IP (e.g., 10.0.0.152)
- **Video Port**: 5600
- **MAVLink Port**: 14550
- **Safety Mode**: Toggle as needed (OFF for arming/flying)

### 2. Install GStreamer on Linux

```bash
# Install GStreamer packages
sudo apt update
sudo apt install gstreamer1.0-tools gstreamer1.0-plugins-base \
                 gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
                 gstreamer1.0-plugins-ugly gstreamer1.0-libav \
                 gstreamer1.0-gl gstreamer1.0-gtk3
```

### 3. View Video Stream

Once RosettaDrone is connected to the drone and streaming:

```bash
# View the video stream using GStreamer
gst-launch-1.0 udpsrc port=5600 ! \
    application/x-rtp,encoding-name=H264,payload=96 ! \
    rtph264depay ! h264parse ! avdec_h264 ! \
    videoconvert ! autovideosink
```

### 4. Alternative Video Viewing Methods

#### Using VLC with SDP file
Create `stream.sdp`:
```
v=0
o=- 0 0 IN IP4 10.0.0.152
s=DJI Stream
c=IN IP4 10.0.0.152
t=0 0
m=video 5600 RTP/AVP 96
a=rtpmap:96 H264/90000
```

Then run:
```bash
vlc stream.sdp
```

#### Using FFplay with SDP
```bash
ffplay -protocol_whitelist file,udp,rtp -i stream.sdp
```

## Debugging Tips

### Check if video data is being received
```bash
# Monitor RosettaDrone logs for video debug info
adb logcat | grep VIDEO_DEBUG
```

Key logs to look for:
- `VIDEO_DEBUG: Received video data from DJI` - DJI SDK is sending data
- `VIDEO_DEBUG: SENDING UDP PACKET TO 10.0.0.152:5600` - RTP packets being sent
- `VIDEO_DEBUG: Camera set to video mode successfully` - Camera mode is correct

### Check if packets are arriving at computer
```bash
# Monitor UDP traffic on port 5600
sudo tcpdump -i any -n port 5600
```

### Verify GStreamer is receiving data
```bash
# Add verbose flag to see packet info
GST_DEBUG=2 gst-launch-1.0 udpsrc port=5600 ! \
    application/x-rtp,encoding-name=H264,payload=96 ! \
    rtph264depay ! h264parse ! avdec_h264 ! \
    videoconvert ! autovideosink
```

## MAVLink Connection

### Using QGroundControl
1. Set RosettaDrone GCS IP to your computer's IP
2. QGroundControl should auto-detect on port 14550

### Using DroneKit Python
```python
from dronekit import connect
vehicle = connect('udp:0.0.0.0:14550', wait_ready=True)
print(f"Battery: {vehicle.battery}")
print(f"GPS: {vehicle.gps_0}")
print(f"Mode: {vehicle.mode.name}")
```

### Debugging mavlink connection
```bash
adb logcat | grep -E "MAVLink|GCS|UDP|Rosetta"
```

## Technical Details

### Video Processing Pipeline
1. DJI SDK → `mReceivedVideoDataListener` callback
2. Raw H.264/H.265 data → `NativeHelper.parse()` (JNI/FFmpeg)
3. Decoded frames → `VideoService.onDataRecv()`
4. H.264 NAL units → `RtpSocket` (packetization)
5. RTP packets → UDP socket to 10.0.0.152:5600

### RTP Stream Format
- **Payload Type**: 96 (dynamic)
- **Encoding**: H264
- **Clock Rate**: 90000
- **Resolution**: 1920x1080 (Mavic 2 Pro)

## Troubleshooting

### No video in GStreamer
1. Check camera is in VIDEO mode (not PHOTO)
2. Verify IP address in RosettaDrone settings
3. Ensure firewall allows UDP port 5600
4. Check `adb logcat` for errors

### Video stuttering or artifacts
- This is often due to packet loss over WiFi
- Try reducing video bitrate in settings
- Ensure strong WiFi connection between devices

### MAVLink not connecting
1. Verify GCS IP is correct
2. Check firewall allows UDP port 14550
3. Ensure RosettaDrone shows "connected" to drone
4. Try `nc -lu 14550` to test if packets arrive
