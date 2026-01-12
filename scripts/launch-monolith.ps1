# launch-monolith.ps1 - Lightweight launcher for fortuna-monolith.exe
param(
    [string]$ExePath = "dist/fortuna-monolith/fortuna-monolith.exe",  # Path to your PyInstaller EXE
    [int]$Port = 8000,
    [switch]$AutoRestart
)

# Set environment variables (equivalent to Docker env)
$env:FORTUNA_PORT = $Port
$env:FORTUNA_MODE = "monolith"  # Custom flag for your app

# Pre-launch checks (lightweight health check)
function Test-PortFree {
    param([int]$Port)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", $Port)
        $tcp.Close()
        return $false  # Port in use
    } catch {
        return $true   # Port free
    }
}

if (!(Test-Path $ExePath)) {
    Write-Error "Monolith EXE not found at $ExePath. Build it first with PyInstaller."
    exit 1
}

if (!(Test-PortFree $Port)) {
    Write-Error "Port $Port is in use. Close conflicting app or change port."
    exit 1
}

# Launch the EXE (in background, with logging)
Write-Host "Launching Fortuna Monolith on port $Port..."
$process = Start-Process -FilePath $ExePath -ArgumentList "--host 127.0.0.1 --port $Port" -NoNewWindow -PassThru -RedirectStandardOutput "monolith.log" -RedirectStandardError "monolith-error.log"

# Optional auto-restart loop (mimics Docker restart policies)
if ($AutoRestart) {
    while ($true) {
        Start-Sleep 5  # Poll every 5 seconds
        if ($process.HasExited) {
            Write-Warning "Monolith crashed (exit code $($process.ExitCode)). Restarting..."
            $process = Start-Process -FilePath $ExePath -ArgumentList "--host 127.0.0.1 --port $Port" -NoNewWindow -PassThru
        }
    }
} else {
    Write-Host "Monolith launched. Press Ctrl+C to stop."
    Wait-Process -Id $process.Id
}
