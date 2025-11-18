# Quick Start Guide

Get your Dual Webcam DVR system running in 5 minutes!

## Prerequisites

- Linux system (Ubuntu/Debian)
- 1-2 USB webcams
- sudo/root access

## Installation Steps

### 1. Download
```bash
# If using git
git clone <repository-url>
cd WebcamStream

# Or extract the downloaded ZIP
unzip WebcamStream.zip
cd WebcamStream
```

### 2. Install
```bash
sudo ./install.sh
```

Follow the prompts:
- OpenWeatherMap API key (optional - press Enter to skip)
- Your city name (e.g., "New York,NY,US")

### 3. Access
Open in your browser:
```
http://<your-server-ip>
```

That's it! 🎉

## What You Get

- **Live Stream**: Real-time webcam feeds with weather overlay
- **DVR Recording**: Start/stop recording with one click
- **Gallery**: View, download, and delete recordings
- **Snapshots**: Capture current frame as JPEG

## Quick Commands

```bash
# Check if services are running
sudo systemctl status webcam-overlay webcam-overlay2

# View logs
sudo journalctl -u webcam-overlay -f

# Restart services
sudo systemctl restart webcam-overlay webcam-overlay2
```

## Troubleshooting

**Services won't start?**
```bash
# Check logs
sudo journalctl -u webcam-overlay -n 50

# Verify webcams
ls -l /dev/video*
```

**Can't access web interface?**
```bash
# Check nginx
sudo nginx -t
sudo systemctl status nginx
```

## Next Steps

- Configure weather overlay in `webcam_overlay.py`
- Adjust camera resolution/framerate
- Set up HTTPS with Let's Encrypt
- Add authentication to nginx

See [README.md](README.md) for full documentation.
