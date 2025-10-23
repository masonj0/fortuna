# 🎯 Fortuna Faucet: Complete User Guide for Windows Hobbyists

## What Is This Amazing Software?

**Fortuna Faucet** is a professional-grade horse racing analysis platform that:
- 📊 Aggregates data from **20+ global racing sources** simultaneously
- 🤖 Uses AI-powered analysis to find value betting opportunities
- 📈 Provides live odds monitoring via Betfair Exchange
- 🌐 Features a beautiful web dashboard for real-time insights
- 🔄 Runs automatically in the background like a professional service

Think of it as your personal racing intelligence agency!

---

## 🚀 Quick Start (15 Minutes to Racing!)

### Step 1: One-Click Installation
1. Extract all files to `C:\FortunaFaucet` (or your preferred location)
2. **Right-click** `INSTALL_FORTUNA.bat` → **Run as Administrator**
3. Wait 3-5 minutes while it automatically installs:
   - Python 3.11 (if needed)
   - Node.js (if needed)
   - All required packages

### Step 2: Quick Configuration
1. **Double-click** `setup_wizard.py` in your folder
2. Follow the friendly prompts to configure:
   - Your private API key (auto-generated)
   - Betfair credentials (optional, for live odds)
3. The wizard creates your `.env` file automatically!

### Step 3: Launch!
- **Double-click** the "Launch Fortuna" shortcut on your desktop
- Wait 10 seconds for services to start
- Your dashboard opens automatically in your browser! 🎉

---

## 🎮 Using Your New Command Center

### The Dashboard (http://localhost:3000)
Your racing command center features:

**📊 Statistics Panel** (Top of screen)
- **Qualified Races**: How many races meet your criteria
- **Premium Targets**: High-score opportunities (80%+)
- **Next Race**: Countdown to the next qualifying race
- **Avg Field Size**: Average number of horses

**🎛️ Smart Filters** (Middle section)
Customize what you see:
- **Min Score Slider**: Only show races above X% match
- **Max Field Size**: Filter by number of runners (8, 10, 12, or Any)
- **Sort By**: Order by score, time, or track name

**🏇 Race Cards** (Main display)
Each card shows:
- Track name and race number
- Qualification score (color-coded!)
- Race conditions (distance, surface)
- Top 3 contenders with best odds
- Data source count

### Color Coding System
- 🔴 **Red (80%+)**: Premium betting opportunity!
- 🟡 **Yellow (60-79%)**: Good value potential
- 🟢 **Green (<60%)**: Meets minimum criteria

---

## 🔧 Advanced Features

### Live Odds Monitoring
Once you've added Betfair credentials:
1. The system automatically tracks races approaching post time
2. Updates odds every 30 seconds for races within 5 minutes
3. Highlights dramatic odds movements

### Desktop Monitor Tool
Run `fortuna_monitor.py` for a real-time status window:
- Shows all data source health
- Performance graphs (with matplotlib)
- Success rates and fetch durations
- Quick "Refresh Now" button

### Auto-Start on Windows Boot
Run `SCHEDULE_FORTUNA.bat` (as Administrator):
- Fortuna starts when you log into Windows
- Daily 3 AM restart for fresh data
- Runs silently in the background

---

## 🎯 Understanding the "Trifecta Analyzer"

This is the brain! It scores races on three factors:

### Factor 1: Field Size (smaller is better)
- **Why**: Fewer horses = easier to predict
- **Default**: Maximum 10 runners

### Factor 2: Favorite's Odds (higher is better)
- **Why**: If the favorite is 2.5+, the race is wide open
- **Default**: Minimum 2.5

### Factor 3: Second Favorite's Odds (higher is better)
- **Why**: Confirms multiple horses are competitive
- **Default**: Minimum 4.0

**The Score**: Combines all three into a 0-100% match rating!

---

## 📚 System Architecture (Simplified)

```
┌─────────────────────────────────────────┐
│     🌐 Next.js Dashboard (Port 3000)    │
│     Your beautiful web interface        │
└──────────────────┬──────────────────────┘
                   │ API Calls
┌──────────────────▼──────────────────────┐
│   🐍 Python FastAPI Backend (Port 8000) │
│   - OddsEngine: Fetches from 20+ sources│
│   - TrifectaAnalyzer: Scores races      │
│   - LiveOddsMonitor: Betfair tracking   │
└──────────────────┬──────────────────────┘
                   │ Async Requests
┌──────────────────▼──────────────────────┐
│     🔌 Adapter Fleet (20+ sources)      │
│  TVG • Betfair • TimeForm • GBGB       │
│  RacingAndSports • USTA • And more!     │
└─────────────────────────────────────────┘
```

---

## 🔐 Security Notes

### API Keys
- **Your local API_KEY**: Only for communication between YOUR backend and frontend
- Never shared online, never exposed
- Auto-generated during setup

### External API Keys (Optional)
Add these to `.env` for more data sources:
```
TVG_API_KEY="your_tvg_key"
RACING_AND_SPORTS_TOKEN="your_ras_token"
THE_RACING_API_KEY="your_theracingapi_key"
```

Get keys from:
- TVG: https://www.tvg.com/promos/developer-api
- Racing and Sports: https://www.racingandsports.com/data-api/
- The Racing API: https://www.theracingapi.com/

---

## 🛠️ Troubleshooting

### "Backend Offline" Error
```batch
# Stop everything cleanly
STOP_FORTUNA.bat

# Wait 10 seconds, then restart
LAUNCH_FORTUNA.bat
```

### Dashboard Loads But No Data
1. Open `http://localhost:8000/health` in browser
2. Should show: `{"status": "OK"}`
3. If not, check Python backend window for errors

### "Port Already In Use" Error
Someone else is using port 8000 or 3000:
```batch
# Windows: Kill processes on those ports
netstat -ano | findstr :8000
taskkill /PID [number] /F

netstat -ano | findstr :3000
taskkill /PID [number] /F
```

### Reset Everything
```batch
# Nuclear option: Clean slate
STOP_FORTUNA.bat
del .env
setup_wizard.py
INSTALL_FORTUNA.bat
```

---

## 📖 File Structure Explained

### Critical Files (Don't Delete!)
- `.env` - Your configuration (API keys, settings)
- `requirements.txt` - Python packages list
- `package.json` - Node.js packages list

### Convenience Scripts
- `LAUNCH_FORTUNA.bat` - Start everything
- `STOP_FORTUNA.bat` - Stop everything
- `RESTART_FORTUNA.bat` - Clean restart
- `setup_wizard.py` - Interactive config tool

### Python Backend (`python_service/`)
- `api.py` - Web server (FastAPI)
- `engine.py` - Master data orchestrator
- `analyzer.py` - Race scoring logic
- `models.py` - Data structure definitions
- `adapters/` - Individual data source plugins

### Frontend (`web_platform/frontend/`)
- `src/app/page.tsx` - Main dashboard
- `src/components/RaceCard.tsx` - Individual race display
- `.env.local` - Frontend API key

---

## 🎓 Customization Ideas

### Change Analyzer Thresholds
Edit `python_service/analyzer.py`:
```python
class TrifectaAnalyzer(BaseAnalyzer):
    def __init__(self,
                 max_field_size: int = 8,      # ← Change this
                 min_favorite_odds: float = 3.0, # ← Or this
                 min_second_favorite_odds: float = 5.0): # ← Or this
```

### Add New Data Sources
1. Copy `python_service/adapters/template_adapter.py`
2. Rename and implement the `fetch_races()` method
3. Register in `python_service/adapters/__init__.py`
4. Add to `python_service/engine.py` adapter list

### Customize Dashboard Colors
Edit `web_platform/frontend/tailwind.config.ts`:
```typescript
theme: {
  extend: {
    colors: {
      'fortuna-primary': '#your-hex-color',
    }
  }
}
```

---

## 💡 Pro Tips

### Tip 1: Use Windows Task Scheduler
Run `SCHEDULE_FORTUNA.bat` for:
- Auto-start on login
- Daily 3 AM maintenance restart

### Tip 2: Monitor Multiple Days
The analyzer works for "today" by default, but you can query any date:
```
http://localhost:8000/api/races/qualified/trifecta?race_date=2025-10-25
```

### Tip 3: Export Data
The API returns pure JSON. Use tools like:
- **Postman** for testing
- **PowerShell** for scripting:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/races/qualified/trifecta" `
  -Headers @{"X-API-Key"="your_key"} | ConvertTo-Json -Depth 10
```

### Tip 4: Mobile Access
If you want to check from your phone on the same WiFi:
1. Find your PC's IP: `ipconfig` in Command Prompt
2. Open firewall port 3000
3. Access from phone: `http://192.168.1.X:3000`

---

## 🎉 You're Ready!

This is a **professional-grade** system that you now control. It was built with years of racing analytics experience and modern software practices.

### What You Can Do Now:
✅ Track races from 20+ global sources
✅ Identify value opportunities with AI scoring
✅ Monitor live odds movements
✅ Run 24/7 as a background service
✅ Customize thresholds and filters
✅ Expand with new data sources

**Welcome to the world of algorithmic racing analysis!** 🏇🚀

---

## 📞 Additional Resources

### Project Documentation
- `HISTORY.md` - Project evolution story
- `ARCHITECTURAL_MANDATE.md` - System design principles
- `WISDOM.md` - Developer best practices
- `ROADMAP_APPENDICES.md` - Future expansion ideas

### Useful Commands
```batch
# View all active Python processes
tasklist | findstr python

# Check if ports are available
netstat -ano | findstr :8000
netstat -ano | findstr :3000

# Update Python packages
.venv\Scripts\activate
pip install --upgrade -r requirements.txt
```

### Need Help?
1. Check `fortuna_restart.log` for error history
2. Run `fortuna_monitor.py` to see real-time system status
3. Verify `.env` file has all required keys

Happy Racing! 🎰🏆