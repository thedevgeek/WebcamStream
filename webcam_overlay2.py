#!/usr/bin/env python3
"""
Webcam Overlay Server
Captures webcam, adds date/time/weather overlay, and streams via HTTP
"""

import cv2
import numpy as np
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time
import requests
import json
from urllib.parse import quote
import os
import glob
import subprocess

# Configuration
WEBCAM_DEVICE = 2
STREAM_WIDTH = 1280
STREAM_HEIGHT = 720
STREAM_FPS = 30
STREAM_PORT = 8091
RECORDINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'recordings2')

# Weather Configuration
WEATHER_API_KEY = "54cf460559d9ccbe6032cd031ddb4ee3"  # Get free key from openweathermap.org
CITY = "Inver Grove Heights,MN,US"
WEATHER_UPDATE_INTERVAL = 900  # Update every 15 minutes (well within free tier: 2,880 calls/month)

# Global variables
latest_frame = None
frame_lock = threading.Lock()
weather_update_lock = threading.Lock()
weather_data = {"temp": "N/A", "desc": ""}
last_weather_update = 0
api_call_count = 0  # Track API calls for monitoring
weather_update_in_progress = False  # Prevent multiple simultaneous calls
connected_clients = {}  # Track connected clients
client_counter = 0  # Unique client ID counter
client_lock = threading.Lock()

# DVR Recording variables
is_recording = False
recording_writer = None  # Will be subprocess.Popen for ffmpeg
recording_filename = None
recording_lock = threading.Lock()
recording_start_time = None
recording_frame_count = 0

def get_weather():
    """Fetch weather data from OpenWeatherMap API with rate limiting"""
    global weather_data, last_weather_update, api_call_count, weather_update_in_progress
    
    # Check if update is already in progress
    if weather_update_in_progress:
        return
    
    if not WEATHER_API_KEY:
        weather_data = {"temp": "N/A", "desc": "No API Key"}
        return
    
    # Enforce minimum time between calls (safety check)
    time_since_last = time.time() - last_weather_update
    if time_since_last < WEATHER_UPDATE_INTERVAL:
        return  # Skip if called too soon
    
    # Acquire lock to prevent multiple simultaneous calls
    if not weather_update_lock.acquire(blocking=False):
        return  # Another thread is already updating
    
    try:
        weather_update_in_progress = True
        # URL encode city name to handle spaces properly
        city_encoded = quote(CITY)
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city_encoded}&appid={WEATHER_API_KEY}&units=imperial"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        api_call_count += 1
        
        if response.status_code == 200:
            weather_data = {
                "temp": f"{int(data['main']['temp'])}F",
                "desc": data['weather'][0]['description'].title(),
                "feels_like": f"{int(data['main']['feels_like'])}F",
                "humidity": f"{data['main']['humidity']}%"
            }
            last_weather_update = time.time()
            print(f"Weather updated (API call #{api_call_count}): {weather_data['temp']} - {weather_data['desc']}")
        elif response.status_code == 429:
            print(f"WARNING: API rate limit exceeded! Call #{api_call_count}")
            weather_data = {"temp": "N/A", "desc": "Rate Limited"}
            last_weather_update = time.time()  # Mark as updated to prevent retry spam
        elif response.status_code == 401:
            print(f"ERROR: Invalid API key! Call #{api_call_count}")
            weather_data = {"temp": "N/A", "desc": "Invalid API Key"}
            last_weather_update = time.time()  # Mark as updated to prevent retry spam
        else:
            print(f"Weather API error: Status {response.status_code}, Call #{api_call_count}")
            last_weather_update = time.time() - WEATHER_UPDATE_INTERVAL + 60  # Retry in 1 minute
            
    except requests.exceptions.Timeout:
        print(f"Weather API timeout (call #{api_call_count})")
        last_weather_update = time.time() - WEATHER_UPDATE_INTERVAL + 60  # Retry in 1 minute
    except Exception as e:
        print(f"Weather fetch error (call #{api_call_count}): {e}")
        weather_data = {"temp": "N/A", "desc": "API Error"}
        last_weather_update = time.time() - WEATHER_UPDATE_INTERVAL + 60  # Retry in 1 minute
    finally:
        weather_update_in_progress = False
        weather_update_lock.release()

def draw_overlay(frame):
    """Draw date, time, and weather overlay on frame (bottom-right corner)"""
    # Get current date and time
    now = datetime.now()
    date_str = now.strftime("%B %d, %Y")
    time_str = now.strftime("%H:%M:%S")
    
    # Update weather if needed
    if time.time() - last_weather_update > WEATHER_UPDATE_INTERVAL:
        threading.Thread(target=get_weather, daemon=True).start()
    
    # Font settings - Using FONT_HERSHEY_TRIPLEX (clean, similar to Calibri)
    font = cv2.FONT_HERSHEY_TRIPLEX
    font_scale = 0.6
    font_thickness = 1
    text_color = (255, 255, 255)  # White
    # Semi-transparent black background (30% opacity)
    bg_color = (0, 0, 0)
    bg_opacity = 0.3
    padding = 10
    line_height = 28
    
    # Prepare all text lines
    lines = []
    lines.append(date_str)
    lines.append(time_str)
    
    weather_line = f"{weather_data['temp']}"
    if 'desc' in weather_data and weather_data['desc']:
        weather_line += f" - {weather_data['desc']}"
    lines.append(weather_line)
    
    if 'feels_like' in weather_data:
        lines.append(f"Feels: {weather_data['feels_like']} | Humidity: {weather_data['humidity']}")
    
    # Calculate total height and max width
    frame_height, frame_width = frame.shape[:2]
    max_width = 0
    text_sizes = []
    
    for i, text in enumerate(lines):
        scale = font_scale if i < 2 else font_scale * 0.85
        thickness = font_thickness if i < 2 else 1
        (text_width, text_height), baseline = cv2.getTextSize(text, font, scale, thickness)
        text_sizes.append((text_width, text_height, scale, thickness, baseline))
        max_width = max(max_width, text_width)
    
    # Calculate starting position (bottom-right corner)
    total_height = len(lines) * line_height
    x_start = frame_width - max_width - padding * 3
    y_start = frame_height - total_height - padding
    
    # Draw semi-transparent background rectangle
    overlay = frame.copy()
    cv2.rectangle(overlay, 
                  (x_start - padding, y_start - padding),
                  (frame_width - padding, frame_height - padding),
                  bg_color, -1)
    frame = cv2.addWeighted(overlay, bg_opacity, frame, 1 - bg_opacity, 0)
    
    # Draw each line of text
    y_position = y_start + 20
    for i, (text, (text_width, text_height, scale, thickness, baseline)) in enumerate(zip(lines, text_sizes)):
        x_position = frame_width - text_width - padding * 2
        cv2.putText(frame, text, (x_position, y_position), font, scale, text_color, thickness, cv2.LINE_AA)
        y_position += line_height
    
    return frame

def capture_frames():
    """Capture frames from webcam and add overlay"""
    global latest_frame, is_recording, recording_writer, recording_filename, recording_frame_count, STREAM_WIDTH, STREAM_HEIGHT
    
    cap = cv2.VideoCapture(WEBCAM_DEVICE, cv2.CAP_V4L2)
    
    # Set buffer size to 1 to avoid stale frames
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    # Use YUYV format instead of MJPEG for eMeet C960
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y', 'U', 'Y', 'V'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, STREAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, STREAM_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, STREAM_FPS)
    
    if not cap.isOpened():
        print("Error: Cannot open webcam")
        return
    
    # Get actual capture dimensions and update globals
    STREAM_WIDTH = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    STREAM_HEIGHT = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = int(cap.get(cv2.CAP_PROP_FPS))
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
    
    print(f"Webcam opened: {STREAM_WIDTH}x{STREAM_HEIGHT} @ {actual_fps}fps (Format: {fourcc_str})")
    
    # Initial weather fetch
    get_weather()
    
    last_log_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Cannot read frame")
            time.sleep(0.1)
            continue
        
        # Add overlay to frame
        frame_with_overlay = draw_overlay(frame.copy())
        
        # Write frame WITH overlay to recording
        with recording_lock:
            if is_recording and recording_writer is not None:
                try:
                    # Write BGR24 frame with overlay to ffmpeg stdin
                    recording_writer.stdin.write(frame_with_overlay.tobytes())
                    recording_frame_count += 1
                    
                    # Log every 5 seconds during recording
                    if time.time() - last_log_time >= 5.0:
                        print(f"[DVR] Frames written: {recording_frame_count}")
                        last_log_time = time.time()
                except (BrokenPipeError, IOError) as e:
                    print(f"[DVR] Error writing frame: {e}")
                    is_recording = False
        
        # Encode as JPEG for streaming (use same overlay frame)
        _, jpeg = cv2.imencode('.jpg', frame_with_overlay, [cv2.IMWRITE_JPEG_QUALITY, 85])
        
        with frame_lock:
            latest_frame = jpeg.tobytes()
        
        time.sleep(1.0 / STREAM_FPS)
    
    cap.release()

def start_recording():
    """Start DVR recording"""
    global is_recording, recording_writer, recording_filename, recording_start_time, recording_frame_count
    
    with recording_lock:
        if is_recording:
            return {"success": False, "error": "Already recording"}
        
        # Create recordings2 directory if it doesn't exist
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        recording_filename = os.path.join(RECORDINGS_DIR, f"recording_{timestamp}.mp4")
        
        # Start ffmpeg process to write MP4 directly
        # Accept raw BGR24 frames via stdin and encode to H.264 MP4
        try:
            recording_writer = subprocess.Popen([
                'ffmpeg',
                '-y',  # Overwrite output file
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f'{STREAM_WIDTH}x{STREAM_HEIGHT}',
                '-r', str(STREAM_FPS),
                '-i', '-',  # Read from stdin
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '23',
                '-pix_fmt', 'yuv420p',
                recording_filename
            ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            is_recording = True
            recording_start_time = time.time()
            recording_frame_count = 0
            print(f"[DVR] Recording started: {recording_filename}")
            return {"success": True, "filename": os.path.basename(recording_filename)}
            
        except Exception as e:
            print(f"[DVR] Failed to start ffmpeg: {e}")
            recording_writer = None
            return {"success": False, "error": f"Failed to start recording: {e}"}

def stop_recording():
    """Stop DVR recording"""
    global is_recording, recording_writer, recording_filename, recording_start_time, recording_frame_count
    
    with recording_lock:
        if not is_recording:
            return {"success": False, "error": "Not currently recording"}
        
        is_recording = False
        
        # Close ffmpeg stdin and wait for it to finish
        if recording_writer is not None:
            try:
                recording_writer.stdin.close()
                recording_writer.wait(timeout=10)
                recording_writer = None
            except Exception as e:
                print(f"[DVR] Error closing ffmpeg: {e}")
                if recording_writer:
                    recording_writer.kill()
                    recording_writer = None
        
        duration = time.time() - recording_start_time if recording_start_time else 0
        
        # Check if file was created successfully
        if recording_filename and os.path.exists(recording_filename):
            file_size = os.path.getsize(recording_filename)
            print(f"[DVR] Recording completed: {os.path.basename(recording_filename)} (duration: {duration:.1f}s, frames: {recording_frame_count}, size: {file_size} bytes)")
        else:
            print(f"[DVR] Recording stopped but file not found!")
        
        result = {
            "success": True, 
            "filename": os.path.basename(recording_filename) if recording_filename else "unknown",
            "duration": f"{duration:.1f}s"
        }
        
        recording_filename = None
        recording_start_time = None
        recording_frame_count = 0
        
        return result

def get_recordings2():
    """Get list of all recordings2"""
    if not os.path.exists(RECORDINGS_DIR):
        return []
    
    recordings2 = []
    # Only show MP4 files (skip temp AVI files)
    for filepath in sorted(glob.glob(os.path.join(RECORDINGS_DIR, "*.mp4")), reverse=True):
        stat = os.stat(filepath)
        size_mb = stat.st_size / (1024*1024)
        recordings2.append({
            "filename": os.path.basename(filepath),
            "size": stat.st_size,
            "size_mb": f"{size_mb:.2f}" if size_mb >= 0.01 else "<0.01",
            "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": stat.st_ctime
        })
    
    return recordings2

class StreamHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Suppress default log messages"""
        pass
    
    def do_GET(self):
        global client_counter
        
        if self.path == '/' or self.path.startswith('/?action=stream'):
            # Log client connection
            client_ip = self.client_address[0]
            user_agent = self.headers.get('User-Agent', 'Unknown')
            
            with client_lock:
                client_counter += 1
                client_id = client_counter
                connected_clients[client_id] = {
                    'ip': client_ip,
                    'user_agent': user_agent,
                    'connected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'type': 'stream'
                }
                stream_count = len([c for c in connected_clients.values() if c['type'] == 'stream'])
            
            print(f"[CLIENT #{client_id}] Connected: {client_ip} | {user_agent}")
            print(f"[STATS] Total clients served: {client_counter} | Currently streaming: {stream_count}")
            
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            
            try:
                while True:
                    with frame_lock:
                        if latest_frame is not None:
                            self.wfile.write(b'--frame\r\n')
                            self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                            self.wfile.write(latest_frame)
                            self.wfile.write(b'\r\n')
                    time.sleep(1.0 / STREAM_FPS)
            except:
                pass
            finally:
                with client_lock:
                    if client_id in connected_clients:
                        del connected_clients[client_id]
                print(f"[CLIENT #{client_id}] Disconnected: {client_ip}")
        
        elif self.path.startswith('/?action=snapshot'):
            # Log snapshot request
            client_ip = self.client_address[0]
            user_agent = self.headers.get('User-Agent', 'Unknown')
            print(f"[SNAPSHOT] {client_ip} | {user_agent}")
            
            with frame_lock:
                if latest_frame is not None:
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Disposition', 
                                   f'attachment; filename="webcam_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg"')
                    self.end_headers()
                    self.wfile.write(latest_frame)
                else:
                    self.send_error(503, "No frame available")
        
        elif self.path == '/status' or self.path == '/status/':
            # Display connected clients and statistics
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            
            with client_lock:
                active_clients = list(connected_clients.items())
                total_served = client_counter
            
            html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Webcam Stream Status</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        h1 {{
            color: #333;
            margin-bottom: 10px;
            font-size: 2em;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .stat-label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        .clients-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        .clients-table th {{
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        .clients-table td {{
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
        }}
        .clients-table tr:hover {{
            background: #f8f9fa;
        }}
        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }}
        .status-active {{
            background: #22c55e;
            color: white;
        }}
        .no-clients {{
            text-align: center;
            padding: 40px;
            color: #999;
            font-size: 1.1em;
        }}
        .refresh-info {{
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 0.9em;
        }}
        .back-link {{
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 5px;
        }}
        .back-link:hover {{
            background: #764ba2;
        }}
        @media (max-width: 768px) {{
            .container {{ padding: 15px; }}
            h1 {{ font-size: 1.5em; }}
            .stat-value {{ font-size: 2em; }}
            .clients-table {{ font-size: 0.9em; }}
            .clients-table th, .clients-table td {{ padding: 8px; }}
        }}
    </style>
    <script>
        // Auto-refresh every 5 seconds
        setTimeout(function() {{
            location.reload();
        }}, 5000);
    </script>
</head>
<body>
    <div class="container">
        <h1>📊 Webcam Stream Status</h1>
        <p style="color: #666; margin-bottom: 20px;">Real-time connection monitoring</p>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{len(active_clients)}</div>
                <div class="stat-label">Active Connections</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_served}</div>
                <div class="stat-label">Total Clients Served</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{api_call_count}</div>
                <div class="stat-label">Weather API Calls</div>
            </div>
        </div>
        
        <h2 style="margin-top: 30px; color: #333;">Connected Clients</h2>
''';
            
            if active_clients:
                html += '''<table class="clients-table">
                    <thead>
                        <tr>
                            <th>Client ID</th>
                            <th>IP Address</th>
                            <th>Connected At</th>
                            <th>User Agent</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>''';
                
                for client_id, info in active_clients:
                    html += f'''<tr>
                        <td><strong>#{client_id}</strong></td>
                        <td>{info['ip']}</td>
                        <td>{info['connected_at']}</td>
                        <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis;">{info['user_agent']}</td>
                        <td><span class="status-badge status-active">ACTIVE</span></td>
                    </tr>''';
                
                html += '</tbody></table>';
            else:
                html += '<div class="no-clients">No clients currently connected</div>';
            
            html += f'''<div class="refresh-info">
                🔄 Auto-refreshing every 5 seconds<br>
                Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </div>
            <a href="/webcam-viewer/" class="back-link">← Back to Webcam Stream</a>
        </div>
    </body>
    </html>''';
            
            self.wfile.write(html.encode('utf-8'))
        
        elif self.path == '/dvr/start':
            # Start recording
            result = start_recording()
            self.send_response(200 if result['success'] else 400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))
        
        elif self.path == '/dvr/stop':
            # Stop recording
            result = stop_recording()
            self.send_response(200 if result['success'] else 400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))
        
        elif self.path == '/dvr/status':
            # Get recording status
            with recording_lock:
                duration = time.time() - recording_start_time if is_recording and recording_start_time else 0
                status = {
                    "recording": is_recording,
                    "filename": os.path.basename(recording_filename) if recording_filename else None,
                    "duration": f"{duration:.1f}s" if is_recording else None
                }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(status).encode('utf-8'))
        
        elif self.path == '/dvr/list':
            # List all recordings2
            recordings2 = get_recordings2()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(recordings2).encode('utf-8'))
        
        elif self.path.startswith('/dvr/download/'):
            # Download a recording
            filename = self.path.split('/dvr/download/')[-1]
            filepath = os.path.join(RECORDINGS_DIR, filename)
            
            # Only allow MP4 downloads
            if not filename.endswith('.mp4'):
                self.send_error(400, "Only MP4 files can be downloaded")
                return
            
            if os.path.exists(filepath) and filepath.startswith(RECORDINGS_DIR):
                self.send_response(200)
                self.send_header('Content-Type', 'video/mp4')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.end_headers()
                
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "Recording not found")
        
        elif self.path.startswith('/dvr/delete/'):
            # Delete a recording
            filename = self.path.split('/dvr/delete/')[-1]
            filepath = os.path.join(RECORDINGS_DIR, filename)
            
            if os.path.exists(filepath) and filepath.startswith(RECORDINGS_DIR):
                try:
                    os.remove(filepath)
                    print(f"[DVR] Deleted recording: {filename}")
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
                except Exception as e:
                    self.send_error(500, f"Delete failed: {e}")
            else:
                self.send_error(404, "Recording not found")
        
        elif self.path == '/dvr/gallery' or self.path == '/dvr/gallery/':
            # Display recordings2 gallery
            recordings2 = get_recordings2()
            
            # Determine base path based on port
            dvr_base = '/dvr' if STREAM_PORT == 8090 else '/dvr2'
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            
            html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎬 DVR Recordings Gallery</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        h1 {{
            color: #333;
            margin-bottom: 20px;
        }}
        .recordings2-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .recording-card {{
            background: #f8f9fa;
            border-radius: 10px;
            padding: 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.2s;
            overflow: hidden;
        }}
        .recording-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.2);
        }}
        .video-preview {{
            width: 100%;
            height: 200px;
            background: #000;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }}
        .video-preview video {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        .play-overlay {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(102, 126, 234, 0.9);
            color: white;
            padding: 20px;
            border-radius: 50%;
            font-size: 2em;
            pointer-events: none;
        }}
        .recording-info {{
            padding: 15px;
        }}
        .recording-name {{
            font-weight: 600;
            color: #333;
            margin-bottom: 8px;
            font-size: 1.1em;
        }}
        .recording-meta {{
            color: #666;
            font-size: 0.9em;
            line-height: 1.6;
        }}
        .recording-actions {{
            display: flex;
            gap: 10px;
        }}
        .btn {{
            flex: 1;
            padding: 10px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.9em;
            transition: opacity 0.2s;
            text-decoration: none;
            text-align: center;
            display: inline-block;
        }}
        .btn:hover {{
            opacity: 0.8;
        }}
        .btn-download {{
            background: #667eea;
            color: white;
        }}
        .btn-delete {{
            background: #ef4444;
            color: white;
        }}
        .no-recordings2 {{
            text-align: center;
            padding: 60px 20px;
            color: #999;
        }}
        .no-recordings2-icon {{
            font-size: 4em;
            margin-bottom: 20px;
        }}
        .back-link {{
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 5px;
        }}
        .back-link:hover {{
            background: #764ba2;
        }}
        @media (max-width: 768px) {{
            .container {{ padding: 15px; }}
            .recordings2-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
    <script>
        function deleteRecording(filename) {{
            if (!confirm('Delete ' + filename + '?')) return;
            
            fetch('{dvr_base}/delete/' + filename)
                .then(r => r.json())
                .then(data => {{
                    if (data.success) {{
                        location.reload();
                    }} else {{
                        alert('Delete failed');
                    }}
                }})
                .catch(err => alert('Error: ' + err));
        }}
        
        // Video preview controls
        document.addEventListener('DOMContentLoaded', function() {{
            const videos = document.querySelectorAll('.video-preview video');
            videos.forEach(video => {{
                const overlay = video.parentElement.querySelector('.play-overlay');
                
                video.addEventListener('play', () => {{
                    overlay.style.display = 'none';
                }});
                
                video.addEventListener('pause', () => {{
                    overlay.style.display = 'block';
                }});
                
                video.addEventListener('ended', () => {{
                    overlay.style.display = 'block';
                }});
            }});
        }});
    </script>
</head>
<body>
    <div class="container">
        <h1>🎬 DVR Recordings Gallery</h1>
        <p style="color: #666; margin-bottom: 20px;">Your saved webcam recordings2</p>
        
        <div class="recordings2-grid">
''';
            
            if recordings2:
                for rec in recordings2:
                    html += f'''
            <div class="recording-card">
                <div class="video-preview">
                    <video preload="metadata" onclick="this.paused ? this.play() : this.pause()">
                        <source src="{dvr_base}/download/{rec['filename']}" type="video/mp4">
                    </video>
                    <div class="play-overlay">▶</div>
                </div>
                <div class="recording-info">
                    <div class="recording-name">📹 {rec['filename']}</div>
                    <div class="recording-meta">
                        <div>📅 {rec['created']}</div>
                        <div>💾 {rec['size_mb']} MB</div>
                    </div>
                    <div class="recording-actions" style="margin-top: 15px;">
                        <a href="{dvr_base}/download/{rec['filename']}" class="btn btn-download">⬇️ Download</a>
                        <button onclick="deleteRecording('{rec['filename']}')" class="btn btn-delete">🗑️ Delete</button>
                    </div>
                </div>
            </div>
''';
            else:
                html += '''
            <div class="no-recordings2">
                <div class="no-recordings2-icon">📹</div>
                <h2>No Recordings Yet</h2>
                <p>Start recording from the webcam viewer to see your videos here.</p>
            </div>
''';
            
            html += f'''
        </div>
        
        <a href="/webcam-viewer/" class="back-link">← Back to Webcam Stream</a>
    </div>
</body>
</html>''';
            
            self.wfile.write(html.encode('utf-8'))
        
        else:
            self.send_error(404)

def main():
    print("=" * 70)
    print("Webcam Stream Server with Overlay")
    print("=" * 70)
    print(f"Location: {CITY}")
    print(f"Resolution: {STREAM_WIDTH}x{STREAM_HEIGHT}")
    print(f"FPS: {STREAM_FPS}")
    print(f"Port: {STREAM_PORT}")
    if WEATHER_API_KEY:
        print("Weather: API Key configured")
    else:
        print("Weather: No API key (set WEATHER_API_KEY in script)")
        print("         Get free key at: https://openweathermap.org/api")
    print("=" * 70)
    print(f"\nStream URL: http://localhost:{STREAM_PORT}/?action=stream")
    print("Press Ctrl+C to stop\n")
    
    # Start capture thread
    capture_thread = threading.Thread(target=capture_frames, daemon=True)
    capture_thread.start()
    
    # Wait for first frame
    while latest_frame is None:
        time.sleep(0.1)
    
    # Start HTTP server (threaded to handle multiple clients)
    server = ThreadingHTTPServer(('0.0.0.0', STREAM_PORT), StreamHandler)
    print("Server started successfully!")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        server.shutdown()

if __name__ == "__main__":
    main()
