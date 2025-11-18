# Dual Webcam DVR System

A professional webcam streaming and DVR recording system with live MJPEG streaming, MP4 recording, and weather overlay. Supports dual cameras with independent controls.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)

## Features

### Live Streaming
- 📹 **MJPEG Streaming** - Real-time webcam stream via HTTP
- 🌡️ **Weather Overlay** - Date, time, and weather information
- 📸 **Snapshot Capture** - Download current frame as JPEG
- 📊 **Status Monitoring** - View connected clients and stream stats

### DVR Recording
- ⏺️ **Start/Stop Recording** - Independent control for each camera
- 🎬 **H.264 MP4 Output** - High-quality video compression
- 📂 **Gallery View** - Browse, preview, and manage recordings
- ⬇️ **Download** - Save recordings to your device
- 🗑️ **Delete** - Remove unwanted recordings

### Dual Camera Support
- 🎥 **Two Simultaneous Cameras** - Stream and record from both cameras
- 🔄 **Independent Controls** - Separate recording, snapshot, and gallery for each
- 📱 **Responsive Interface** - Works on desktop and mobile devices

## System Requirements

### Hardware
- Linux system (Ubuntu 20.04+ recommended)
- 1-2 USB webcams (UVC compatible)
- 2GB+ RAM recommended
- Sufficient storage for recordings

### Software
- Python 3.8 or higher
- OpenCV (cv2)
- FFmpeg with libx264 support
- Nginx web server

## Quick Installation

### 1. Clone or Download
```bash
git clone <repository-url>
cd WebcamStream
```

Or download and extract the ZIP file.

### 2. Run Installer
```bash
sudo ./install.sh
```

The installer will:
- Install all required dependencies
- Detect connected webcams
- Configure weather API (optional)
- Create systemd services
- Configure nginx reverse proxy
- Start the services automatically

### 3. Access the System
Open your browser and navigate to:
```
http://<your-server-ip>
```

## Manual Installation

If you prefer to install manually:

### 1. Install Dependencies
```bash
# Update package list
sudo apt-get update

# Install system packages
sudo apt-get install -y python3 python3-pip python3-opencv ffmpeg v4l-utils nginx

# Install Python packages
sudo pip3 install opencv-python numpy requests
```

### 2. Configure Weather API (Optional)
Get a free API key from [OpenWeatherMap](https://openweathermap.org/api)

Edit `webcam_overlay.py` and `webcam_overlay2.py`:
```python
WEATHER_API_KEY = "your_api_key_here"
CITY = "Your City,State,Country"
```

### 3. Verify Webcams
```bash
# List available video devices
ls -l /dev/video*

# Check webcam details
v4l2-ctl --device=/dev/video0 --info
v4l2-ctl --device=/dev/video2 --info
```

### 4. Create Systemd Services

**Camera 1 Service** (`/etc/systemd/system/webcam-overlay.service`):
```ini
[Unit]
Description=Webcam Stream 1 with DVR
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/WebcamStream
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 -u /path/to/WebcamStream/webcam_overlay.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Camera 2 Service** (`/etc/systemd/system/webcam-overlay2.service`):
```ini
[Unit]
Description=Webcam Stream 2 with DVR
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/WebcamStream
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 -u /path/to/WebcamStream/webcam_overlay2.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable webcam-overlay webcam-overlay2
sudo systemctl start webcam-overlay webcam-overlay2
```

### 5. Configure Nginx

Create `/etc/nginx/sites-available/webcam-dvr` (see `install.sh` for full configuration)

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/webcam-dvr /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 6. Copy Web Interface
```bash
sudo mkdir -p /var/www/webcam-dvr
sudo cp index_dual.html /var/www/webcam-dvr/index.html
sudo chown -R www-data:www-data /var/www/webcam-dvr
```

## Configuration

### Camera Settings
Edit `webcam_overlay.py` for Camera 1 or `webcam_overlay2.py` for Camera 2:

```python
# Camera device (0 for /dev/video0, 2 for /dev/video2)
WEBCAM_DEVICE = 0

# Resolution
STREAM_WIDTH = 1280
STREAM_HEIGHT = 720

# Frame rate
STREAM_FPS = 30

# Port (8090 for camera 1, 8091 for camera 2)
STREAM_PORT = 8090

# Recordings directory
RECORDINGS_DIR = '/path/to/recordings'
```

### Weather Configuration
```python
# OpenWeatherMap API key (free tier: 1000 calls/day)
WEATHER_API_KEY = "your_api_key"

# Location
CITY = "City,State,Country"

# Update interval (seconds) - 900s = 15 minutes
WEATHER_UPDATE_INTERVAL = 900
```

## Usage

### Web Interface
Access the main page: `http://<server-ip>/`

**Camera Controls:**
- **Snapshot** - Download current frame as JPEG
- **Start Recording** - Begin MP4 recording
- **Stop Recording** - End recording and save file
- **Gallery** - View and manage recordings

### Direct API Access

**Camera 1:**
- Stream: `http://<server-ip>/webcam/stream`
- Snapshot: `http://<server-ip>/webcam/snapshot`
- Status: `http://<server-ip>/webcam/status`
- Start Recording: `http://<server-ip>/dvr/start`
- Stop Recording: `http://<server-ip>/dvr/stop`
- DVR Status: `http://<server-ip>/dvr/status`
- Gallery: `http://<server-ip>/dvr/gallery`

**Camera 2:**
- Stream: `http://<server-ip>/webcam2/stream`
- Snapshot: `http://<server-ip>/webcam2/snapshot`
- Status: `http://<server-ip>/webcam2/status`
- Start Recording: `http://<server-ip>/dvr2/start`
- Stop Recording: `http://<server-ip>/dvr2/stop`
- DVR Status: `http://<server-ip>/dvr2/status`
- Gallery: `http://<server-ip>/dvr2/gallery`

### Command Line

```bash
# Check service status
sudo systemctl status webcam-overlay
sudo systemctl status webcam-overlay2

# View logs
sudo journalctl -u webcam-overlay -f
sudo journalctl -u webcam-overlay2 -f

# Restart services
sudo systemctl restart webcam-overlay
sudo systemctl restart webcam-overlay2

# Start/stop recording via curl
curl http://localhost:8090/dvr/start
curl http://localhost:8090/dvr/stop
```

## Troubleshooting

### No Webcam Detected
```bash
# List USB devices
lsusb | grep -i camera

# Check video devices
ls -l /dev/video*

# Verify camera is accessible
v4l2-ctl --device=/dev/video0 --all
```

### Service Won't Start
```bash
# Check logs for errors
sudo journalctl -u webcam-overlay -n 50

# Verify Python script runs
python3 webcam_overlay.py

# Check permissions
ls -l /dev/video*
```

### Recording Issues
- Ensure FFmpeg is installed with H.264 support: `ffmpeg -codecs | grep h264`
- Check disk space: `df -h`
- Verify recordings directory permissions

### Stream Not Accessible
```bash
# Test local connection
curl http://localhost:8090/?action=stream

# Check nginx configuration
sudo nginx -t

# View nginx logs
sudo tail -f /var/log/nginx/error.log
```

### Weather Not Updating
- Verify API key is valid
- Check API call limit (1000 calls/day on free tier)
- View logs: `sudo journalctl -u webcam-overlay | grep Weather`

## File Structure

```
WebcamStream/
├── install.sh              # Automated installation script
├── webcam_overlay.py       # Camera 1 service (port 8090)
├── webcam_overlay2.py      # Camera 2 service (port 8091)
├── index_dual.html         # Dual camera web interface
├── recordings/             # Camera 1 recordings storage
├── recordings2/            # Camera 2 recordings storage
├── README.md               # This file
├── DVR_GUIDE.md           # Detailed DVR usage guide
└── API_RATE_LIMITING.md   # Weather API information
```

## Technical Details

### Video Pipeline
1. **Capture** - OpenCV reads frames from V4L2 device
2. **Overlay** - Date/time/weather added using cv2.putText()
3. **Stream** - JPEG encoding for MJPEG HTTP stream
4. **Record** - Raw BGR24 frames → FFmpeg stdin → H.264 MP4

### Recording Format
- **Container**: MP4
- **Video Codec**: H.264 (libx264)
- **Pixel Format**: yuv420p
- **Preset**: ultrafast (low CPU usage)
- **Quality**: CRF 23 (good quality/size balance)

### Network Ports
- **8090** - Camera 1 Python service
- **8091** - Camera 2 Python service
- **80** - Nginx reverse proxy

## Security Considerations

⚠️ **Important**: This system currently has no authentication. Recommendations:

1. **Use behind firewall** - Don't expose directly to internet
2. **Add nginx authentication** - Use HTTP basic auth
3. **Use SSL/TLS** - Configure HTTPS with Let's Encrypt
4. **Restrict access** - Configure nginx IP whitelisting

Example nginx authentication:
```nginx
location / {
    auth_basic "Webcam Access";
    auth_basic_user_file /etc/nginx/.htpasswd;
}
```

## Performance

### Resource Usage (per camera)
- **CPU**: 5-15% (varies with resolution/framerate)
- **RAM**: 50-100 MB
- **Disk**: ~10-20 MB per minute of recording (H.264)
- **Network**: ~1-5 Mbps per stream viewer

### Optimization Tips
- Lower resolution for lower bandwidth/CPU usage
- Reduce FPS (20-25 instead of 30)
- Use MJPEG camera format when available
- Adjust H.264 CRF value (higher = smaller files, lower quality)

## License

MIT License - Feel free to use and modify for your needs.

## Credits

- **OpenCV** - Computer vision library
- **FFmpeg** - Video encoding
- **OpenWeatherMap** - Weather data API
- **Nginx** - Web server and reverse proxy

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review logs: `sudo journalctl -u webcam-overlay -n 100`
3. Verify webcam compatibility with V4L2

## Changelog

### Version 2.0 (Current)
- ✅ Dual camera support
- ✅ Independent DVR controls per camera
- ✅ Automated installation script
- ✅ Gallery with video preview
- ✅ Delete recordings functionality
- ✅ Responsive web interface

### Version 1.0
- Initial release with single camera support
- MJPEG streaming
- Basic DVR functionality
