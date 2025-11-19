# Camera Controls Guide

This document describes the camera control capabilities for both cameras in the dual webcam DVR system.

## Overview

The system provides real-time camera control via web interface and REST API. Controls vary by camera hardware capabilities.

## Camera 1: Logitech C920 PRO HD

### Available Controls

| Control | Range | Default | Description |
|---------|-------|---------|-------------|
| **Pan** | -36000 to 36000 | 0 | Horizontal position (step: 3600 = 10°) |
| **Tilt** | -36000 to 36000 | 0 | Vertical position (step: 3600 = 10°) |
| **Brightness** | 0-255 | 128 | Image brightness |
| **Contrast** | 0-255 | 128 | Image contrast |

> **Note**: The C920 PRO HD has a fixed focal length lens and does not support optical or digital zoom, despite the zoom_absolute control existing in the V4L2 driver.

### Web Interface Controls
- **Pan & Tilt Pad**: 9-button directional pad with center reset
- **Brightness Slider**: Control image brightness
- **Contrast Slider**: Control image contrast
- **Reset Button**: Restore all controls to factory defaults

### API Examples

```bash
# Pan right 10 degrees
curl "http://your-server/camera/control?pan=3600"

# Tilt up 10 degrees
curl "http://your-server/camera/control?tilt=3600"

# Adjust brightness and contrast
curl "http://your-server/camera/control?brightness=180&contrast=200"

# Full PT positioning
curl "http://your-server/camera/control?pan=7200&tilt=-3600&brightness=180"

# Reset all to defaults
curl "http://your-server/camera/control?reset=1"
```

## Camera 2: eMeet C960

### Available Controls

| Control | Range | Default | Description |
|---------|-------|---------|-------------|
| **Brightness** | -64 to 64 | 0 | Image brightness offset |
| **Contrast** | 0-64 | 32 | Image contrast |
| **Saturation** | 0-128 | 64 | Color saturation |
| **Sharpness** | 0-6 | 3 | Image sharpness |

> **Note**: Camera 2 does NOT support zoom, pan, or tilt controls due to hardware limitations.

### Web Interface Controls
- **Brightness Slider**: Adjust image brightness (-64 to 64)
- **Contrast Slider**: Control image contrast (0-64)
- **Saturation Slider**: Adjust color intensity (0-128)
- **Sharpness Slider**: Control image sharpness (0-6)
- **Reset Button**: Restore all controls to factory defaults

### API Examples

```bash
# Increase brightness
curl "http://your-server/camera2/control?brightness=10"

# Adjust contrast
curl "http://your-server/camera2/control?contrast=40"

# Boost saturation
curl "http://your-server/camera2/control?saturation=80"

# Sharpen image
curl "http://your-server/camera2/control?sharpness=5"

# Multiple adjustments
curl "http://your-server/camera2/control?brightness=5&contrast=35&saturation=70&sharpness=4"

# Reset all to defaults
curl "http://your-server/camera2/control?reset=1"
```

## API Response Format

All control endpoints return JSON:

```json
{
  "success": true,
  "controls": {
    "brightness": 150,
    "contrast": 200
  }
}
```

Error response:
```json
{
  "success": false,
  "error": "Invalid parameter value"
}
```

## Technical Implementation

### Backend
- Uses `v4l2-ctl` via subprocess to communicate with camera hardware
- Real-time application of settings (no restart required)
- Settings persist until camera power cycle
- Independent control endpoints for each camera

### Frontend
- HTML5 range sliders for smooth value adjustment
- Real-time value display next to each slider
- Immediate API calls on slider change (debounced)
- Visual feedback for applied settings

## Checking Available Controls

To see what controls your specific camera supports:

```bash
# Camera 1 (usually /dev/video0)
v4l2-ctl --device=/dev/video0 --list-ctrls

# Camera 2 (usually /dev/video2)
v4l2-ctl --device=/dev/video2 --list-ctrls
```

Sample output:
```
brightness 0x00980900 (int)    : min=0 max=255 step=1 default=128 value=128
contrast 0x00980901 (int)      : min=0 max=255 step=1 default=128 value=128
saturation 0x00980902 (int)    : min=0 max=255 step=1 default=128 value=128
zoom_absolute 0x009a090d (int) : min=100 max=500 step=1 default=100 value=100
pan_absolute 0x009a0908 (int)  : min=-36000 max=36000 step=3600 default=0 value=0
tilt_absolute 0x009a0909 (int) : min=-36000 max=36000 step=3600 default=0 value=0
```

## Troubleshooting

### Controls Not Responding
1. Check camera is connected: `ls -l /dev/video*`
2. Verify control is supported: `v4l2-ctl --device=/dev/videoX --list-ctrls`
3. Test direct v4l2 control: `v4l2-ctl --device=/dev/videoX --set-ctrl=brightness=150`
4. Check service logs: `sudo journalctl -u webcam-overlay -f`

### Settings Reset After Reboot
This is expected behavior. Camera controls return to factory defaults when the camera is power cycled. The web interface allows you to quickly restore your preferred settings.

### PTZ Not Available
Pan/Tilt/Zoom controls require hardware support. Most budget webcams only provide basic image adjustments. The Logitech C920 PRO HD is specifically chosen for its PTZ capabilities.

## Best Practices

1. **Lighting Conditions**: Adjust brightness and contrast based on ambient lighting
2. **Zoom Usage**: Digital zoom reduces image quality; use sparingly
3. **PTZ Positioning**: Save preferred positions as bookmarks in your browser
4. **Reset Feature**: Use reset when experimenting to quickly return to known-good settings
5. **Recording**: Camera settings apply to both live stream and recordings

## License

Camera control features are part of the WebcamStream project under MIT License.
