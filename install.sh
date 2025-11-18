#!/bin/bash
#
# Dual Webcam DVR System - Installation Script
# For Ubuntu/Debian-based Linux systems
#

set -e

echo "======================================"
echo "Dual Webcam DVR System - Installer"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root or with sudo"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INSTALL_USER="${SUDO_USER:-$USER}"

echo "Installation directory: $SCRIPT_DIR"
echo "Running as user: $INSTALL_USER"
echo ""

# Install system dependencies
echo "[1/6] Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-opencv ffmpeg v4l-utils nginx

# Install Python dependencies
echo "[2/6] Installing Python dependencies..."
pip3 install --break-system-packages opencv-python numpy requests 2>/dev/null || pip3 install opencv-python numpy requests

# Detect webcams
echo "[3/6] Detecting webcams..."
WEBCAMS=()
for i in {0..9}; do
    if [ -e "/dev/video$i" ]; then
        CARD=$(v4l2-ctl --device=/dev/video$i --info 2>/dev/null | grep "Card type" | cut -d: -f2 | xargs || echo "Unknown")
        # Skip metadata devices
        if [[ ! "$CARD" =~ "Metadata" ]]; then
            echo "  Found: /dev/video$i - $CARD"
            WEBCAMS+=("$i:$CARD")
        fi
    fi
done

if [ ${#WEBCAMS[@]} -eq 0 ]; then
    echo "ERROR: No webcams detected!"
    exit 1
fi

# Configure OpenWeatherMap API key
echo ""
echo "[4/6] Weather overlay configuration..."
read -p "Enter your OpenWeatherMap API key (or press Enter to skip): " WEATHER_API
read -p "Enter your city (e.g., 'New York,NY,US'): " CITY_NAME

if [ -n "$WEATHER_API" ]; then
    sed -i "s/WEATHER_API_KEY = .*/WEATHER_API_KEY = \"$WEATHER_API\"/" "$SCRIPT_DIR/webcam_overlay.py"
    sed -i "s/WEATHER_API_KEY = .*/WEATHER_API_KEY = \"$WEATHER_API\"/" "$SCRIPT_DIR/webcam_overlay2.py"
fi

if [ -n "$CITY_NAME" ]; then
    sed -i "s/CITY = .*/CITY = \"$CITY_NAME\"/" "$SCRIPT_DIR/webcam_overlay.py"
    sed -i "s/CITY = .*/CITY = \"$CITY_NAME\"/" "$SCRIPT_DIR/webcam_overlay2.py"
fi

# Create systemd services
echo ""
echo "[5/6] Creating systemd services..."

# Service for Camera 1
cat > /etc/systemd/system/webcam-overlay.service << EOF
[Unit]
Description=Webcam Stream 1 with DVR
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$SCRIPT_DIR
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 -u $SCRIPT_DIR/webcam_overlay.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Service for Camera 2 (if available)
if [ ${#WEBCAMS[@]} -ge 2 ]; then
    cat > /etc/systemd/system/webcam-overlay2.service << EOF
[Unit]
Description=Webcam Stream 2 with DVR
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$SCRIPT_DIR
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 -u $SCRIPT_DIR/webcam_overlay2.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
fi

# Reload systemd
systemctl daemon-reload

# Enable and start services
systemctl enable webcam-overlay.service
systemctl start webcam-overlay.service

if [ ${#WEBCAMS[@]} -ge 2 ]; then
    systemctl enable webcam-overlay2.service
    systemctl start webcam-overlay2.service
fi

# Configure nginx
echo ""
echo "[6/6] Configuring nginx..."

# Create web directory
mkdir -p /var/www/webcam-dvr
cp "$SCRIPT_DIR/index_dual.html" /var/www/webcam-dvr/index.html
chown -R www-data:www-data /var/www/webcam-dvr

# Create nginx configuration
cat > /etc/nginx/sites-available/webcam-dvr << 'EOF'
server {
    listen 80;
    server_name _;
    
    # Main page
    location / {
        root /var/www/webcam-dvr;
        index index.html;
    }
    
    # Camera 1 endpoints
    location = /webcam/stream {
        proxy_pass http://localhost:8090/?action=stream;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_request_buffering off;
        keepalive_timeout 3600s;
        chunked_transfer_encoding on;
    }
    
    location = /webcam/snapshot {
        proxy_pass http://localhost:8090/?action=snapshot;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location = /webcam/status {
        proxy_pass http://localhost:8090/status;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /dvr/ {
        proxy_pass http://localhost:8090/dvr/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }
    
    # Camera 2 endpoints
    location = /webcam2/stream {
        proxy_pass http://localhost:8091/?action=stream;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_request_buffering off;
        keepalive_timeout 3600s;
        chunked_transfer_encoding on;
    }
    
    location = /webcam2/snapshot {
        proxy_pass http://localhost:8091/?action=snapshot;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location = /webcam2/status {
        proxy_pass http://localhost:8091/status;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /dvr2/ {
        proxy_pass http://localhost:8091/dvr/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }
}
EOF

# Enable the site
ln -sf /etc/nginx/sites-available/webcam-dvr /etc/nginx/sites-enabled/webcam-dvr
rm -f /etc/nginx/sites-enabled/default

# Test and reload nginx
nginx -t && systemctl reload nginx

echo ""
echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""
echo "Services Status:"
systemctl status webcam-overlay.service --no-pager -l | grep "Active:"
if [ ${#WEBCAMS[@]} -ge 2 ]; then
    systemctl status webcam-overlay2.service --no-pager -l | grep "Active:"
fi
echo ""
echo "Access your webcam system at:"
echo "  http://$(hostname -I | awk '{print $1}')"
echo ""
echo "DVR Galleries:"
echo "  Camera 1: http://$(hostname -I | awk '{print $1}')/dvr/gallery"
if [ ${#WEBCAMS[@]} -ge 2 ]; then
    echo "  Camera 2: http://$(hostname -I | awk '{print $1}')/dvr2/gallery"
fi
echo ""
echo "Logs:"
echo "  sudo journalctl -u webcam-overlay -f"
if [ ${#WEBCAMS[@]} -ge 2 ]; then
    echo "  sudo journalctl -u webcam-overlay2 -f"
fi
echo ""
