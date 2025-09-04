#!/usr/bin/env python3
"""
Simple Browser Viewer for testing LiveViewService
Based on the Bedrock-AgentCore sample code
"""

import time
import threading
import webbrowser
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn
from rich.console import Console

from services.live_view_service import get_live_view_service

console = Console()

class SimpleBrowserViewer:
    """Simple browser viewer for testing live view functionality"""
    
    def __init__(self, order_id: str, port: int = 8001):
        self.order_id = order_id
        self.port = port
        self.app = FastAPI(title="Simple Browser Viewer")
        self.server_thread = None
        self.is_running = False
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            """Serve the main viewer page"""
            try:
                # Get live view service
                config = {"agentcore_region": "us-west-2"}
                live_view_service = get_live_view_service(config, None)
                
                # Get or create session for order
                session_id = live_view_service.get_session_for_order(self.order_id)
                if not session_id:
                    session_id = live_view_service.create_live_session(
                        self.order_id, "strands_playwright_mcp"
                    )
                
                if not session_id:
                    raise HTTPException(status_code=500, detail="Failed to create live session")
                
                # Get presigned URL
                presigned_url = live_view_service.get_presigned_url(session_id, expires=300)
                
                if not presigned_url:
                    raise HTTPException(status_code=500, detail="Failed to generate presigned URL")
                
                # Generate HTML
                html = self._generate_html(presigned_url, session_id)
                return HTMLResponse(content=html)
                
            except Exception as e:
                console.print(f"[red]Error: {str(e)}[/red]")
                raise HTTPException(status_code=500, detail=str(e))
    
    def _generate_html(self, presigned_url: str, session_id: str) -> str:
        """Generate simple viewer HTML"""
        return f'''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Simple Browser Viewer</title>
            <style>
                body {{ 
                    margin: 0; 
                    padding: 20px; 
                    font-family: Arial, sans-serif; 
                    background: #f5f5f5;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .header {{
                    border-bottom: 1px solid #eee;
                    padding-bottom: 15px;
                    margin-bottom: 20px;
                }}
                .info {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 4px;
                    margin-bottom: 20px;
                }}
                .url-display {{
                    background: #e9ecef;
                    padding: 10px;
                    border-radius: 4px;
                    font-family: monospace;
                    font-size: 12px;
                    word-break: break-all;
                    margin-top: 10px;
                }}
                .status {{
                    padding: 10px;
                    border-radius: 4px;
                    margin-top: 15px;
                }}
                .success {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
                .error {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Simple Browser Viewer</h1>
                    <p>Testing LiveViewService functionality</p>
                </div>
                
                <div class="info">
                    <h3>Session Information</h3>
                    <p><strong>Order ID:</strong> {self.order_id}</p>
                    <p><strong>Session ID:</strong> {session_id}</p>
                    <p><strong>Status:</strong> <span id="status">Active</span></p>
                </div>
                
                <div class="info">
                    <h3>Presigned URL Generated</h3>
                    <p>Successfully generated presigned URL for live viewing:</p>
                    <div class="url-display">{presigned_url[:100]}...</div>
                </div>
                
                <div class="status success">
                    <strong>✅ Success!</strong> LiveViewService is working correctly.
                    <ul>
                        <li>AgentCore session created</li>
                        <li>Presigned URL generated</li>
                        <li>Ready for DCV connection</li>
                    </ul>
                </div>
                
                <div class="info">
                    <h3>Next Steps</h3>
                    <p>To implement full DCV viewing:</p>
                    <ol>
                        <li>Install Amazon DCV Web Client SDK</li>
                        <li>Use the presigned URL with DCV.js</li>
                        <li>Implement display layout callbacks</li>
                    </ol>
                </div>
            </div>
            
            <script>
                console.log('Presigned URL:', '{presigned_url}');
                console.log('Session ID:', '{session_id}');
                
                // Test URL validity
                try {{
                    const url = new URL('{presigned_url}');
                    console.log('URL is valid:', url.hostname);
                }} catch (e) {{
                    console.error('Invalid URL:', e);
                }}
            </script>
        </body>
        </html>
        '''
    
    def start(self, open_browser: bool = True) -> str:
        """Start the viewer server"""
        def run_server():
            uvicorn.run(self.app, host="0.0.0.0", port=self.port, log_level="error")
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.is_running = True
        
        time.sleep(1)
        viewer_url = f"http://localhost:{self.port}"
        
        console.print(f"\n[green]✅ Simple viewer running at: {viewer_url}[/green]")
        
        if open_browser:
            console.print("[cyan]Opening browser...[/cyan]")
            webbrowser.open(viewer_url)
        
        return viewer_url

def main():
    """Run the simple browser viewer"""
    console.print("[bold cyan]Simple Browser Viewer Test[/bold cyan]\n")
    
    try:
        # Use a test order ID
        order_id = "test-order-123"
        
        console.print(f"[cyan]Testing with order ID: {order_id}[/cyan]")
        
        # Create and start viewer
        viewer = SimpleBrowserViewer(order_id, port=8001)
        viewer_url = viewer.start(open_browser=True)
        
        console.print("\n[yellow]Press Ctrl+C to stop[/yellow]")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Shutting down...[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()