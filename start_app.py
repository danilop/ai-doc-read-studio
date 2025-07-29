#!/usr/bin/env python3
"""
AI Doc Read Studio - Unified Startup Script
Starts both backend and frontend servers with proper configuration
"""

import subprocess
import sys
import time
import signal
import json
import os
import threading
import queue
import shutil
from datetime import datetime

class AppLauncher:
    def __init__(self, config_file="config.json"):
        self.config = self.load_config(config_file)
        self.backend_process = None
        self.frontend_process = None
        self.running = True
        
    def load_config(self, config_file):
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Config file {config_file} not found!")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in config file: {e}")
            sys.exit(1)
    
    def rotate_logs(self):
        """Rotate existing log files by adding timestamp and keeping history"""
        # Check for logs in main directory and logs/ subdirectory
        log_locations = [
            'startup.log',
            'backend.log', 
            'frontend.log',
            'logs/backend.log',
            'logs/frontend.log'
        ]
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        print("🔄 Rotating log files...")
        
        # Create logs directory if it doesn't exist
        logs_dir = 'logs'
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        
        for log_file in log_locations:
            if os.path.exists(log_file):
                # Get the base name (e.g., backend.log from logs/backend.log)
                base_name = os.path.basename(log_file)
                log_type = base_name.replace('.log', '')
                
                # Move old log to timestamped archive in logs directory
                archived_name = f"{logs_dir}/{log_type}_{timestamp}.log"
                try:
                    shutil.move(log_file, archived_name)
                    print(f"   📋 {log_file} → {archived_name}")
                except Exception as e:
                    print(f"   ⚠️  Could not rotate {log_file}: {e}")
        
        # Clean up old log files (keep only last 10 for each type)
        try:
            if os.path.exists('logs'):
                for log_type in ['startup', 'backend', 'frontend']:
                    # Get all archived logs for this type
                    archived_logs = [f for f in os.listdir('logs') if f.startswith(f'{log_type}_') and f.endswith('.log')]
                    archived_logs.sort(reverse=True)  # Most recent first
                    
                    # Remove old logs (keep only 10 most recent)
                    for old_log in archived_logs[10:]:
                        try:
                            os.remove(os.path.join('logs', old_log))
                            print(f"   🗑️  Removed old log: {old_log}")
                        except Exception as e:
                            print(f"   ⚠️  Could not remove {old_log}: {e}")
        except Exception as e:
            print(f"   ⚠️  Error during log cleanup: {e}")
        
        print("✅ Log rotation complete")
    
    def update_frontend_config(self):
        """Update frontend config.js with backend API URL and model configuration"""
        frontend_config_path = "frontend/config.js"
        
        try:
            # Create the complete frontend configuration
            config_content = f"""// Frontend Configuration
// This file is dynamically updated by the startup script
window.APP_CONFIG = {{
    API_BASE_URL: '{self.config['api']['base_url']}',
    APP_NAME: '{self.config['app']['name']}',
    VERSION: '{self.config['app']['version']}',
    frontend: {{
        log_level: '{self.config['frontend']['log_level']}',
        log_file: '{self.config['frontend']['log_file']}'
    }},
    models: {{
        available: {json.dumps(self.config['models']['available'], indent=8)},
        default_team: '{self.config['models']['default_team']}',
        default_summary: '{self.config['models']['default_summary']}'
    }}
}};"""
            
            with open(frontend_config_path, 'w') as f:
                f.write(config_content)
                
            print(f"✅ Updated frontend configuration:")
            print(f"   API URL: {self.config['api']['base_url']}")
            print(f"   Models: {len(self.config['models']['available'])} available")
            
        except Exception as e:
            print(f"⚠️  Warning: Could not update frontend config: {e}")
    
    def print_startup_banner(self):
        """Print application startup banner"""
        config = self.config
        print("\n" + "="*60)
        print(f"🚀 {config['app']['name']} v{config['app']['version']}")
        print(f"   {config['app']['description']}")
        print("="*60)
        print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    
    def start_backend(self):
        """Start the backend server"""
        backend_config = self.config['backend']
        
        print(f"🔧 Starting backend server...")
        print(f"   Host: {backend_config['host']}")
        print(f"   Port: {backend_config['port']}")
        
        cmd = [
            sys.executable, "-m", "uvicorn", 
            "backend.main:app",
            "--host", backend_config['host'],
            "--port", str(backend_config['port']),
            "--log-level", backend_config['log_level']
        ]
        
        if backend_config.get('reload', False):
            cmd.append("--reload")
        
        try:
            # Use UV to run with proper environment from project root
            uv_cmd = ["uv", "run", "uvicorn", "backend.main:app",
                     "--host", backend_config['host'],
                     "--port", str(backend_config['port']),
                     "--log-level", backend_config['log_level']]
            
            if backend_config.get('reload', False):
                uv_cmd.append("--reload")
            
            self.backend_process = subprocess.Popen(
                uv_cmd,
                cwd=".",  # Run from project root directory
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            return True
        except Exception as e:
            print(f"❌ Failed to start backend: {e}")
            return False
    
    def start_frontend(self):
        """Start the frontend server"""
        frontend_config = self.config['frontend']
        
        print(f"📖 Starting frontend server...")
        print(f"   Host: {frontend_config['host']}")
        print(f"   Port: {frontend_config['port']}")
        
        # Create a simple HTTP server script for the frontend
        server_script = f"""
import http.server
import socketserver
import os
import sys

# Check if frontend directory exists
if not os.path.exists('frontend'):
    print("ERROR: frontend directory not found")
    sys.exit(1)

try:
    os.chdir('frontend')
    PORT = {frontend_config['port']}

    class CustomHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            # Aggressive cache-busting headers
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            super().end_headers()
        
        def log_message(self, format, *args):
            # Reduce logging noise
            pass

    print(f"Frontend server running on http://{frontend_config['host']}:{{PORT}}")
    with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
        httpd.serve_forever()
        
except KeyboardInterrupt:
    print("Frontend server stopped")
    sys.exit(0)
except Exception as e:
    print(f"Frontend server error: {{e}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
"""
        
        try:
            self.frontend_process = subprocess.Popen(
                [sys.executable, "-c", server_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            return True
        except Exception as e:
            print(f"❌ Failed to start frontend: {e}")
            return False
    
    def wait_for_backend(self, timeout=30):
        """Wait for backend to be ready"""
        try:
            import requests
        except ImportError:
            print("⚠️  Requests not available, skipping backend health check")
            time.sleep(5)  # Just wait a bit
            return True
        
        backend_url = self.config['api']['base_url']
        print(f"⏳ Waiting for backend to be ready at {backend_url}...")
        
        for i in range(timeout):
            try:
                response = requests.get(f"{backend_url}/", timeout=1)
                if response.status_code == 200:
                    print("✅ Backend is ready!")
                    return True
            except:
                pass
            time.sleep(1)
            if i % 5 == 0 and i > 0:
                print(f"   Still waiting... ({i}s)")
        
        print("❌ Backend failed to start within timeout")
        return False
    
    def monitor_processes(self):
        """Monitor both processes and handle output"""
        # Setup startup log file
        startup_log_file = 'startup.log'
        
        def read_output(process, name):
            while self.running and process and process.poll() is None:
                try:
                    line = process.stdout.readline()
                    if line:
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        log_line = f"[{timestamp}] {name}: {line.rstrip()}"
                        print(log_line)
                        
                        # Also write to startup log file
                        try:
                            with open(startup_log_file, 'a') as f:
                                f.write(log_line + '\n')
                        except Exception as e:
                            print(f"Warning: Could not write to startup log: {e}")
                        
                        # Look for specific startup indicators
                        if "Uvicorn running on" in line and name == "BACKEND":
                            print(f"✅ {name} server is ready!")
                        elif "Frontend server running on" in line and name == "FRONTEND":
                            print(f"✅ {name} server is ready!")
                except Exception as e:
                    if self.running:  # Only print error if we're still running
                        print(f"Error reading {name} output: {e}")
                    break
        
        # Start monitoring threads
        if self.backend_process:
            backend_thread = threading.Thread(
                target=read_output, 
                args=(self.backend_process, "BACKEND"),
                daemon=True
            )
            backend_thread.start()
        
        if self.frontend_process:
            frontend_thread = threading.Thread(
                target=read_output, 
                args=(self.frontend_process, "FRONTEND"),
                daemon=True
            )
            frontend_thread.start()
    
    def print_access_info(self):
        """Print access information"""
        frontend_url = f"http://{self.config['frontend']['host']}:{self.config['frontend']['port']}"
        backend_url = self.config['api']['base_url']
        
        print("\n" + "="*60)
        print("🎉 APPLICATION READY!")
        print("="*60)
        print(f"📖 Frontend (Web UI):     {frontend_url}")
        print(f"🔧 Backend API:           {backend_url}")
        print(f"📚 API Documentation:     {backend_url}/docs")
        print("="*60)
        print("💡 Usage:")
        print("   1. Open the Frontend URL in your browser")
        print("   2. Upload the sample_doc.md or your own document")
        print("   3. Configure your team (defaults provided)")
        print("   4. Start discussing!")
        print()
        print("📝 Sample document: sample_doc.md")
        print("🛑 Press Ctrl+C to stop both servers")
        print("="*60)
        print()
    
    def cleanup(self):
        """Clean up processes"""
        print("\n🛑 Shutting down servers...")
        self.running = False
        
        if self.backend_process:
            try:
                self.backend_process.terminate()
                self.backend_process.wait(timeout=5)
                print("✅ Backend stopped")
            except:
                self.backend_process.kill()
                print("⚠️  Backend force killed")
        
        if self.frontend_process:
            try:
                self.frontend_process.terminate()
                self.frontend_process.wait(timeout=5)
                print("✅ Frontend stopped")
            except:
                self.frontend_process.kill()
                print("⚠️  Frontend force killed")
    
    def run(self):
        """Main run method"""
        try:
            # Setup signal handlers
            signal.signal(signal.SIGINT, lambda s, f: self.cleanup() or sys.exit(0))
            signal.signal(signal.SIGTERM, lambda s, f: self.cleanup() or sys.exit(0))
            
            # Rotate old logs before starting
            self.rotate_logs()
            
            self.print_startup_banner()
            
            # Update frontend configuration
            self.update_frontend_config()
            
            # Start backend
            if not self.start_backend():
                return 1
            
            # Wait for backend to be ready
            time.sleep(2)  # Give it a moment to start
            
            # Check if requests is available for health check
            try:
                import requests
            except ImportError:
                print("⚠️  Requests not available, skipping health check")
                requests = None
            
            if not self.wait_for_backend():
                self.cleanup()
                return 1
            
            # Start frontend
            if not self.start_frontend():
                self.cleanup()
                return 1
            
            # Give frontend a moment to start
            time.sleep(2)
            
            # Start monitoring
            self.monitor_processes()
            
            # Print access information
            self.print_access_info()
            
            # Keep running until interrupted
            try:
                while self.running:
                    time.sleep(2)
                    
                    # Check if processes are still alive - but be more tolerant
                    if self.backend_process:
                        poll_result = self.backend_process.poll()
                        if poll_result is not None:
                            print(f"❌ Backend process died with exit code: {poll_result}")
                            # Try to get any remaining output
                            try:
                                remaining_output = self.backend_process.stdout.read()
                                if remaining_output:
                                    print(f"Backend final output: {remaining_output}")
                            except:
                                pass
                            break
                    if self.frontend_process:
                        poll_result = self.frontend_process.poll()
                        if poll_result is not None:
                            print(f"❌ Frontend process died with exit code: {poll_result}")
                            break
                        
            except KeyboardInterrupt:
                pass
            
            return 0
            
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return 1
        finally:
            self.cleanup()

def main():
    """Main entry point"""
    launcher = AppLauncher()
    sys.exit(launcher.run())

if __name__ == "__main__":
    main()