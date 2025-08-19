# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RosettaDrone is a MAVLink wrapper for DJI drones that enables control via MAVLink-speaking ground control stations (QGroundControl, Mission Planner, etc.). It's an Android application that acts as a bridge between DJI SDK and MAVLink protocol.

## Build Commands

```bash
# Build the project
./gradlew build

# Build debug APK
./gradlew assembleDebug

# Build release APK
./gradlew assembleRelease

# Run lint checks
./gradlew lint

# Run unit tests
./gradlew test

# Run specific build variant tests
./gradlew testDebugUnitTest
./gradlew testReleaseUnitTest

# Run connected Android tests (requires device/emulator)
./gradlew connectedAndroidTest

# Clean build
./gradlew clean
```

## Architecture

### Core Components

- **DroneModel** (`app/src/main/java/sq/rogue/rosettadrone/DroneModel.java`): Central class that manages DJI drone state and MAVLink communication. Handles telemetry, commands, missions, and virtual stick control.

- **MAVLinkReceiver** (`app/src/main/java/sq/rogue/rosettadrone/MAVLinkReceiver.java`): Processes incoming MAVLink messages and dispatches them to appropriate handlers.

- **MainActivity** (`app/src/main/java/sq/rogue/rosettadrone/MainActivity.java`): Main UI controller that manages connection state, video feeds, and user interactions.

- **MissionManager** (`app/src/main/java/sq/rogue/rosettadrone/MissionManager.java`): Implements waypoint missions using VirtualSticks, enabling mission support on drones without native waypoint capabilities (DJI Mini series).

- **VideoService** (`app/src/main/java/sq/rogue/rosettadrone/video/VideoService.java`): Handles video streaming via RTP/H264 to ground control stations.

### Communication Flow

1. DJI SDK provides drone telemetry and accepts control commands
2. DroneModel translates between DJI SDK data and MAVLink messages
3. MAVLink packets are sent/received via UDP to ground control stations
4. Video stream is separately forwarded via RTP when enabled

### Key Design Patterns

- Uses DJI SDK 4.16.4 for drone communication
- MAVLink implementation uses ArduPilot dialect (manually tweaked generated code)
- Virtual Stick control for universal mission support
- Plugin system for extensibility (`Plugin.java`, `PluginManager.java`)

## Important Implementation Notes

### MAVLink Code Generation
The MAVLink Java code was generated but required manual fixes for double-precision handling (issues #805, #806 in MAVLink repo). Direct replacement with regenerated code will cause errors.

### DJI API Key Required
Create `app/src/main/res/values/keys.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="dji_key">INSERT_DJI_KEY_HERE</string>
    <string name="google_key">INSERT_GOOGLE_MAPS_KEY_HERE</string>
</resources>
```

### Safety Features
- "Safe Mode" prevents unexpected arming/takeoff
- Test Mode allows GUI/MAVLink testing without drone connection (tap drone icon 5 times)
- Simulator support for Hardware-In-Loop testing

### Platform Constraints
- Android only (compileSdkVersion 28, minSdkVersion 21)
- Supports armeabi-v7a and arm64-v8a architectures only
- Requires NDK 21.4.7075529 for native components