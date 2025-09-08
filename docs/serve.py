#!/usr/bin/env python3
"""
Simple HTTP server for serving the prediction dashboard locally.

This server serves the static files and JSON data, allowing the dashboard
to load data via HTTP requests instead of file:// protocol.
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

def serve_dashboard(port=8080):
    """Serve the dashboard on the specified port."""
    # Change to the docs directory
    docs_dir = Path(__file__).parent
    os.chdir(docs_dir)
    
    # Create a custom handler that serves JSON files with correct MIME type
    class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            # Add CORS headers to allow local development
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            super().end_headers()
        
        def guess_type(self, path):
            # Ensure JSON files are served with correct MIME type
            if path.endswith('.json'):
                return 'application/json'
            return super().guess_type(path)
        
        def do_GET(self):
            # Redirect root to index.html
            if self.path == '/':
                self.path = '/index.html'
            super().do_GET()
    
    # Start the server
    with socketserver.TCPServer(("", port), CustomHTTPRequestHandler) as httpd:
        print(f"🌐 Serving prediction dashboard at http://localhost:{port}")
        print(f"📁 Serving files from: {docs_dir}")
        print(f"🔗 Dashboard URL: http://localhost:{port}/index.html")
        print(f"📊 Data URL: http://localhost:{port}/data/")
        print("\nPress Ctrl+C to stop the server")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped")

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    serve_dashboard(port)
