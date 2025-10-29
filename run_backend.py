#!/usr/bin/env python3
"""
Fortuna Faucet Quick Launcher
Fixes the relative import issue and starts the API server correctly
"""
import sys
import subprocess
from pathlib import Path

def main():
    # Get project root directory
    project_root = Path(__file__).parent.resolve()

    print("=" * 60)
    print("🐴 Fortuna Faucet - API Server Launcher")
    print("=" * 60)
    print(f"Project Root: {project_root}")

    # Check if virtual environment exists
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        # Try Linux/Mac path
        venv_python = project_root / ".venv" / "bin" / "python"

    if not venv_python.exists():
        print("\\n❌ ERROR: Virtual environment not found!")
        print("Please run setup_windows.bat first to create the environment.")
        sys.exit(1)

    print(f"✅ Using Python: {venv_python}")

    # Check if python_service package exists
    python_service_dir = project_root / "python_service"
    if not python_service_dir.exists():
        print(f"\\n❌ ERROR: python_service directory not found at {python_service_dir}")
        sys.exit(1)

    # Check for __init__.py
    init_file = python_service_dir / "__init__.py"
    if not init_file.exists():
        print(f"\\n⚠️  WARNING: {init_file} not found. Creating it...")
        init_file.touch()
        print("✅ Created __init__.py")

    # Check for required dependencies
    api_file = python_service_dir / "api.py"
    if not api_file.exists():
        print(f"\\n❌ ERROR: api.py not found at {api_file}")
        sys.exit(1)

    print("\\n📦 Checking uvicorn installation...")
    check_cmd = [str(venv_python), "-m", "pip", "show", "uvicorn"]
    result = subprocess.run(check_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("❌ uvicorn not installed. Installing now...")
        install_cmd = [str(venv_python), "-m", "pip", "install", "uvicorn[standard]"]
        subprocess.run(install_cmd)
    else:
        print("✅ uvicorn is installed")

    print("\\n" + "=" * 60)
    print("🚀 Starting FastAPI Server...")
    print("=" * 60)
    print("\\nAPI will be available at:")
    print("  • http://localhost:8000")
    print("  • http://localhost:8000/docs (Swagger UI)")
    print("  • http://localhost:8000/health (Health Check)")
    print("\\nPress Ctrl+C to stop the server\\n")

    # Start uvicorn with proper module path
    uvicorn_cmd = [
        str(venv_python),
        "-m", "uvicorn",
        "python_service.api:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--log-level", "info"
    ]

    try:
        # Run from project root
        subprocess.run(uvicorn_cmd, cwd=project_root)
    except KeyboardInterrupt:
        print("\\n\\n👋 Shutting down Fortuna Faucet...")
        print("Goodbye!")

if __name__ == "__main__":
    main()
