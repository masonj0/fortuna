
import webview
import uvicorn
import threading
import sys
from web_service.backend.api import app
from web_service.backend.config import get_settings

def run_server():
    settings = get_settings()
    uvicorn.run(app, host=settings.UVICORN_HOST, port=settings.FORTUNA_PORT)

if __name__ == '__main__':
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    webview.create_window('Fortuna Faucet', 'http://127.0.0.1:8000', width=1200, height=800)
    webview.start()
    sys.exit()
