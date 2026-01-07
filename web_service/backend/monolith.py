# web_service/backend/monolith.py
"""
Fortuna Monolith Entry Point
FIXED: Proper static file serving for Next.js exports
"""
import sys
import threading
import time
from pathlib import Path
import uvicorn
import webview
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and PyInstaller"""
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent.parent.parent
    return base_path / relative_path

def create_app():
    """Create FastAPI app with proper routing for Next.js export"""
    from web_service.backend.api import app as backend_app

    app = FastAPI(title="Fortuna Monolith")

    # CRITICAL: Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount backend API FIRST (higher priority)
    app.mount("/api", backend_app, name="backend")

    # Get frontend path
    frontend_path = get_resource_path('frontend_dist')
    print(f"[MONOLITH] Frontend path: {frontend_path}")
    print(f"[MONOLITH] Frontend exists: {frontend_path.exists()}")

    if frontend_path.exists():
        # List files to verify structure
        if (frontend_path / "index.html").exists():
            print("[MONOLITH] Found index.html")
        else:
            print("[MONOLITH] WARNING: index.html not found!")
            print(f"[MONOLITH] Contents: {list(frontend_path.iterdir())}")

        # Mount static files for assets (_next, images, etc.)
        app.mount("/_next", StaticFiles(directory=str(frontend_path / "_next")), name="next-static")

        # Serve root and all other routes with index.html (SPA behavior)
        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            """
            Serve Next.js static export
            - If file exists, serve it
            - Otherwise, serve index.html (for client-side routing)
            """
            # Don't interfere with API routes (already mounted at /api)
            if full_path.startswith("api/"):
                return {"error": "API route should be handled by backend"}

            # Try to serve the exact file
            file_path = frontend_path / full_path
            if file_path.is_file():
                return FileResponse(file_path)

            # Try with .html extension
            html_path = frontend_path / f"{full_path}.html"
            if html_path.is_file():
                return FileResponse(html_path)

            # Default to index.html for all other routes (SPA)
            index_path = frontend_path / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            else:
                return {"error": "index.html not found", "path": str(index_path)}

        print("[MONOLITH] Frontend routing configured")
    else:
        print("[MONOLITH] ERROR: Frontend files not found!")

        @app.get("/")
        async def root():
            return {
                "error": "Frontend not found",
                "path": str(frontend_path),
                "expected_files": ["index.html", "_next/"],
                "help": "Rebuild with 'npm run build' in web_platform/frontend"
            }

    return app

def run_backend():
    """Run the backend server"""
    app = create_app()
    print("[MONOLITH] Starting backend on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

def main():
    """Main entry point"""
    print("[MONOLITH] Starting Fortuna Monolith...")

    # Start backend thread
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()

    # Wait for backend
    print("[MONOLITH] Waiting for backend...")
    time.sleep(3)

    # Verify backend is ready
    import requests
    for i in range(10):
        try:
            # Try health endpoint (in your backend API)
            response = requests.get("http://127.0.0.1:8000/api/health", timeout=1)
            if response.status_code == 200:
                print("[MONOLITH] Backend ready!")
                break
        except:
            print(f"[MONOLITH] Waiting... ({i+1}/10)")
            time.sleep(1)

    # Launch webview
    print("[MONOLITH] Launching UI...")
    webview.create_window(
        title="Fortuna Faucet",
        url="http://127.0.0.1:8000",
        width=1400,
        height=900,
        resizable=True,
        fullscreen=False,
        min_size=(800, 600),
        background_color='#1a1a1a',
        debug=True  # Enable dev tools
    )

    webview.start()
    print("[MONOLITH] Closed")

if __name__ == "__main__":
    main()
