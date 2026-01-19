# scripts/generate_report.ps1

[CmdletBinding()]
param (
    [string]$JsonInputPath = "qualified_races.json",
    [string]$HtmlOutputPath = "race-report.html"
)

Write-Host "Generating HTML report from $JsonInputPath..." -ForegroundColor Cyan

if (-not (Test-Path $JsonInputPath)) {
    Write-Host "❌ ERROR: Input JSON file not found at $JsonInputPath" -ForegroundColor Red
    exit 1
}

$races = Get-Content $JsonInputPath | ConvertFrom-Json
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss UTC"

$html = @"
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🐴 Fortuna - Filtered Race Report</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html { scroll-behavior: smooth; }

    body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background: linear-gradient(135deg, #0f1419 0%, #1a1f2e 50%, #16213e 100%);
      color: #e2e8f0;
      padding: 2rem;
      line-height: 1.6;
      min-height: 100vh;
    }

    .container {
      max-width: 1400px;
      margin: 0 auto;
    }

    header {
      text-align: center;
      margin-bottom: 3rem;
      background: linear-gradient(135deg, rgba(15, 52, 96, 0.5), rgba(0, 255, 136, 0.1));
      border: 2px solid #00ff88;
      border-radius: 12px;
      padding: 3rem 2rem;
      box-shadow: 0 8px 32px rgba(0, 255, 136, 0.2);
    }

    h1 {
      color: #00ff88;
      font-size: 2.8rem;
      margin-bottom: 0.5rem;
      text-shadow: 0 0 10px rgba(0, 255, 136, 0.5);
    }

    .subtitle {
      color: #a0aec0;
      font-size: 1rem;
      margin-top: 0.5rem;
    }

    .summary-box {
      background: rgba(0, 255, 136, 0.1);
      border-left: 4px solid #00ff88;
      border-radius: 8px;
      padding: 1.5rem 2rem;
      margin: 2rem 0;
      font-size: 1.1rem;
      text-align: center;
      color: #00ff88;
      font-weight: bold;
    }

    .race-card {
      background: linear-gradient(135deg, #0f3460 0%, #1a4d7a 100%);
      border: 1px solid rgba(0, 255, 136, 0.2);
      border-left: 4px solid #00ff88;
      border-radius: 12px;
      padding: 2rem;
      margin-bottom: 2rem;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
      transition: all 0.3s ease;
    }

    .race-card:hover {
      transform: translateY(-4px);
      box-shadow: 0 8px 30px rgba(0, 255, 136, 0.25);
      border-color: rgba(0, 255, 136, 0.5);
    }

    .race-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 1.5rem;
      border-bottom: 2px solid #00ff88;
      padding-bottom: 1rem;
      flex-wrap: wrap;
      gap: 1rem;
    }

    .race-title {
      font-size: 1.4rem;
      font-weight: bold;
      color: #00ff88;
    }

    .race-meta {
      color: #a0aec0;
      font-size: 0.9rem;
    }

    .runners-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 1rem;
    }

    .runners-table thead {
      background: rgba(0, 255, 136, 0.15);
      border-bottom: 2px solid #00ff88;
    }

    .runners-table th {
      padding: 1rem;
      text-align: left;
      font-weight: bold;
      color: #00ff88;
      text-transform: uppercase;
      font-size: 0.85rem;
      letter-spacing: 1px;
    }

    .runners-table td {
      padding: 0.75rem 1rem;
      border-bottom: 1px solid #1a3a52;
    }

    .runners-table tbody tr:hover {
      background: rgba(0, 255, 136, 0.05);
    }

    .runner-name {
      font-weight: 600;
      color: #e2e8f0;
    }

    .odds {
      font-family: 'Courier New', monospace;
      color: #00ff88;
      font-weight: bold;
      font-size: 1.1rem;
    }

    .source {
      color: #718096;
      font-size: 0.9rem;
    }

    .no-races {
      text-align: center;
      padding: 3rem;
      background: #0f3460;
      border: 2px dashed #ff4444;
      border-radius: 12px;
      color: #a0aec0;
      font-size: 1.1rem;
    }

    footer {
      text-align: center;
      margin-top: 4rem;
      padding-top: 2rem;
      border-top: 1px solid #404060;
      color: #718096;
      font-size: 0.85rem;
    }

    footer a {
      color: #00ff88;
      text-decoration: none;
      transition: color 0.2s;
    }

    footer a:hover {
      color: #00ff88;
      text-decoration: underline;
    }

    @media (max-width: 768px) {
      h1 { font-size: 1.8rem; }
      header { padding: 2rem 1rem; }
      .race-card { padding: 1rem; }
      .runners-table th, .runners-table td { padding: 0.5rem; }
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>🐴 Fortuna Faucet Race Report</h1>
      <p class="subtitle">Filtered Trifecta Opportunities</p>
      <p class="subtitle">Generated: $timestamp</p>
    </header>

    <div class="summary-box">
      $($races.races.Count) qualified race(s) found
    </div>
"@

if ($races.races -and $races.races.Count -gt 0) {
    foreach ($race in $races.races) {
        $venue = $race.venue ?? "Unknown"
        $raceNum = $race.race_number ?? "?"
        $startTime = $race.startTime ?? "N/A"

        $html += @"
<div class="race-card">
<div class="race-header">
  <div>
    <div class="race-title">$venue - Race $raceNum</div>
    <div class="race-meta">Post Time: $startTime</div>
  </div>
</div>
<table class="runners-table">
  <thead>
    <tr>
      <th>Horse Name</th>
      <th>Win Odds</th>
      <th>Best Source</th>
    </tr>
  </thead>
  <tbody>
"@

        foreach ($runner in $race.runners) {
            $name = $runner.name ?? "Unknown"
            $odds = "N/A"
            $source = "N/A"

            if ($runner.odds) {
                $bestVal = 0
                foreach ($src in $runner.odds.PSObject.Properties) {
                    if ($src.Value.win -gt $bestVal) {
                        $bestVal = $src.Value.win
                        $odds = [math]::Round($bestVal, 2)
                        $source = $src.Name
                    }
                }
            }

            $html += @"
    <tr>
      <td class="runner-name">$name</td>
      <td class="odds">$odds</td>
      <td class="source">$source</td>
    </tr>
"@
        }

        $html += @"
  </tbody>
</table>
</div>
"@
    }
} else {
    $html += @"
<div class="no-races">
❌ No qualified races found at this time.
</div>
"@
}

$github_repository = $env:GITHUB_REPOSITORY
$html += @"
    <footer>
      <p>This report was automatically generated by Fortuna Faucet via GitHub Actions.</p>
      <p>Data sources: Multiple racing exchanges and bookmakers.</p>
      <p>🔗 <a href="https://github.com/$github_repository">View Repository</a></p>
    </footer>
  </div>
</body>
</html>
"@

$html | Out-File -FilePath $HtmlOutputPath -Encoding utf8
Write-Host "✅ HTML report generated successfully at $HtmlOutputPath" -ForegroundColor Green
