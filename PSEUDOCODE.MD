# Fortuna Faucet - Comprehensive Pseudocode Blueprint
## Table of Contents

---

## 1. SYSTEM ARCHITECTURE & OVERVIEW
**Pages: 1-3**

- Global System Overview
- Two-Pillar Architecture (Python Backend + TypeScript Frontend)
- Supporting Artifacts & Tooling Infrastructure
- Deployment Model (Windows Service via MSI)
- High-Level Data Flow Diagram

**Key Topics:**
- System purpose and design philosophy
- Project structure overview
- Technology stack summary
- Integration points between pillars

---

## 2. BACKEND CORE PILLAR (python_service)
**Pages: 4-22**

### 2.1 Configuration & Logging
- Settings module (Pydantic-based environment loading)
- Logging configuration (structlog + JSON output)
- Credential management (API keys, Betfair auth, adapter tokens)

### 2.2 Data Contracts & Models
- OddsData (individual odds quotes)
- Runner (race participant with metadata)
- Race (complete race record)
- SourceInfo & FetchMetadata (audit trail)
- AggregatedResponse & QualifiedRacesResponse

### 2.3 Adapter Framework
- BaseAdapter abstract class
- Resilience patterns (tenacity retry, exponential backoff)
- Authentication mixin (Betfair token management)
- Odds parsing utility (fractional, decimal, "evens" handling)

### 2.4 Adapter Inventory (12+ Active, 20+ Templates)
- **Core Adapters**
  - BetfairAdapter (API + auth)
  - BetfairGreyhoundAdapter (API + auth)

- **Active Data Providers**
  - TVGAdapter (API)
  - RacingAndSportsAdapter (API)
  - RacingAndSportsGreyhoundAdapter (API)
  - TheRacingApiAdapter (API)
  - HarnessAdapter (API)
  - GreyhoundAdapter (API)
  - GbgbApiAdapter (API)

- **HTML Scrapers**
  - AtTheRacesAdapter
  - SportingLifeAdapter
  - TimeformAdapter
  - OddscheckerAdapter

- **Placeholder/Stubs**
  - PointsBetGreyhoundAdapter
  - BrisnetAdapter, DRFAdapter, EquibaseAdapter, FanDuelAdapter, etc.

### 2.5 Analyzer Layer
- BaseAnalyzer abstract class
- TrifectaAnalyzer implementation
  - Filtering logic (field size, favorite odds, second favorite odds)
  - Scoring algorithm (weighted combination)
  - Parameterized configuration
- AnalyzerEngine registry

### 2.6 Engine Orchestration
- OddsEngine class
  - Adapter management
  - Redis integration
  - Race deduplication
  - Parallel fetch orchestration
  - Caching strategy (5-minute TTL)

### 2.7 API Layer (FastAPI)
- Application initialization (lifespan context manager)
- Middleware (Rate limiting, CORS)
- Security dependencies (API key verification)
- Endpoints:
  - `GET /health`
  - `GET /api/adapters/status`
  - `GET /api/races`
  - `GET /api/races/qualified/{analyzer_name}`

### 2.8 Security Module
- X-API-Key header validation
- Secure comparison via secrets.compare_digest
- Error handling (HTTP 403 for invalid keys)

### 2.9 Testing Infrastructure
- Test scenarios for TrifectaAnalyzer
- Mock race generation
- FastAPI TestClient usage
- Legacy scenario validation

---

## 3. FRONTEND PILLAR (web_platform/frontend)
**Pages: 23-30**

### 3.1 Technology Stack & Configuration
- Next.js 14 + React 18
- TypeScript strict mode
- Tailwind CSS styling
- Environment variables (.env.local)
- Build configuration (next.config.mjs)
- Package management (npm with lock file)

### 3.2 LiveRaceDashboard Component
- State management (races, criteria, loading, error, params)
- LocalStorage persistence (user preferences)
- Effect hooks (mount initialization, 30-second polling)
- fetchQualifiedRaces() logic
- Parameter adjustment handlers

### 3.3 RaceCard Component
- Props interface (Race data structure)
- Filtering & sorting (remove scratched, order by number)
- Data enrichment (best odds, sources count, time-to-post)
- Styling & color coding (qualification score badges)
- Runner list with source-specific odds display

### 3.4 Build & Deployment
- Development workflow (npm run dev, hot reload)
- Production build (npm run build, npm start)
- Static export option
- Next.js API rewrites proxy (`/api/*` → backend:8000)
- Browser auto-launch for user convenience

---

## 4. SUPPORTING INFRASTRUCTURE & AUTOMATION
**Pages: 31-40**

### 4.1 Command Deck (Streamlit Dashboard)
- Alternative developer/operator interface
- 30-second cached API calls
- Manual cache clear functionality
- DataFrame visualization (races, adapter status)
- Low-overhead monitoring tool

### 4.2 Data Processing Utilities
- **ChartScraper** (Equibase pipeline)
  - PDF download & decryption (pikepdf)
  - Table extraction (tabula)
  - CSV generation
  - Throttling (1-second delays for courtesy)

- **ChartParser** (results_parser.py)
  - Runner count extraction
  - Text pattern matching
  - Past performance analysis

### 4.3 Live Monitoring Tools
- **LiveOddsMonitor** class
  - Real-time odds augmentation from Betfair
  - Race filtering (Betfair-sourced only)
  - Market ID extraction
  - Runner odds update logic

- **Fortuna Watchman** orchestrator
  - Daily protocol executor
  - Initial target acquisition
  - Tactical monitoring loop
  - Race lifecycle management (5-minute window)
  - Graceful shutdown

### 4.4 Windows Automation Scripts
- **setup_windows.bat**
  - Python environment verification
  - Virtual environment creation
  - Dependency installation (backend + frontend)
  - Post-installation instructions

- **run_fortuna.bat**
  - Dual-window process launch (backend + frontend)
  - Auto-browser opening
  - Development convenience automation

### 4.5 Redis & Caching Infrastructure
- Async Redis client (redis.asyncio)
- Namespace strategy (`fortuna:races:{date}`)
- TTL management (300 seconds)
- Validation on retrieval (Pydantic)
- Error resilience (fallback to live fetch)

---

## 5. DOCUMENTATION & OPERATIONAL REFERENCE
**Pages: 41-46**

### 5.1 Architectural Documents
- **ARCHITECTURAL_MANDATE.md**
  - Two-Pillar design rationale
  - Prime Directive principles
  - Core component responsibilities

- **HISTORY.md**
  - Project evolution ("Utopian" → "Liberation" eras)
  - Environmental constraints & adaptations
  - Shift toward portable architecture

- **ROADMAP_APPENDICES.md**
  - Adapter backlog categories
  - Intelligence leads pipeline
  - Future expansion campaigns
  - Analyst role & responsibilities

### 5.2 Operational Protocols
- **WISDOM.md**
  - Agent virtues (verification, incremental commits, deference to leadership)
  - Operational best practices
  - Debugging methodologies

- **README.md**
  - Quick start (setup_windows.bat, run_fortuna.bat)
  - API usage notes
  - Credential configuration
  - Frontend access instructions

### 5.3 Configuration Reference
- **.env.example**
  - Template for all credential fields
  - Optional vs. required settings
  - Default values & override examples

### 5.4 Windows Service Deployment
- MSI installation instructions
- Service registration details
- Environment variable mapping
- Firewall configuration
- Permission model (NetworkService account)
- Post-installation verification checklist

---

## 6. END-TO-END OPERATIONS & WORKFLOWS
**Pages: 47-52**

### 6.1 Daily Operation Flow
- Settings initialization
- Engine instantiation
- HTTP client setup
- Redis connection
- API request cycle

### 6.2 Data Aggregation Pipeline
- Multi-adapter parallel fetch
- Race deduplication
- Odds merging strategy
- Cache storage (conditional)
- Response serialization

### 6.3 Analysis & Qualification
- Analyzer selection
- Parameter override application
- Race scoring algorithm
- Filtering & ranking
- Response composition

### 6.4 Frontend User Experience
- Dashboard initialization
- Periodic polling (30-second intervals)
- Parameter adjustment workflow
- Real-time card rendering
- Error recovery & fallbacks

### 6.5 Automation Workflows
- **Watchman Daily Protocol**
  - Morning initialization
  - Target acquisition
  - Tactical monitoring loop
  - Post-time odds refresh
  - Graceful shutdown

- **Chart Pipeline** (optional offline)
  - Scheduled PDF scraping
  - Historical CSV archival
  - Text extraction for analysis

### 6.6 Operational Troubleshooting
- Service startup issues
- Redis connection failures
- Adapter authentication problems
- Port/firewall conflicts
- API rate limiting recovery
- Database persistence strategies

### 6.7 Extensibility Patterns
- Adding new adapters
- Creating custom analyzers
- Integrating new data sources
- Extending the frontend dashboard
- Creating scheduled tasks

---

## APPENDICES (Supporting References)

### Appendix A: Glossary
- Key terminology (OddsEngine, Adapter, Analyzer, etc.)
- Acronyms (TVG, R&S, GBGB, etc.)
- Technical concepts

### Appendix B: Configuration Quick Reference
- Environment variable matrix
- Default values table
- Required credentials checklist

### Appendix C: API Reference Summary
- Endpoint specifications
- Request/response examples
- Error codes & handling

### Appendix D: Windows Service Reference
- Service registration details
- Registry entries
- Performance monitoring
- Log file locations

### Appendix E: Frontend Component Tree
- Component hierarchy
- Props interface specifications
- State management patterns

---

## 📊 Document Statistics

| Section | Pages | Topics | Code Examples |
|---------|-------|--------|---------------|
| 1. Architecture | 3 | 5 | 2 |
| 2. Backend Core | 19 | 28 | 40+ |
| 3. Frontend | 8 | 4 | 8 |
| 4. Infrastructure | 10 | 9 | 12+ |
| 5. Documentation | 6 | 8 | 3 |
| 6. Operations | 6 | 7 | 10+ |
| **TOTAL** | **52** | **61** | **75+** |

---

## 🎯 How to Use This TOC

**For System Overview:**
→ Start with Chapter 1 (Global context)

**For Backend Development:**
→ Deep dive into Chapter 2 (all adapter logic, engine design, API routes)

**For Frontend Development:**
→ Focus on Chapter 3 (component structure, state management)

**For Operations/Deployment:**
→ Chapters 4, 5, 6 (infrastructure, docs, workflows)

**For Adding Features:**
→ Chapter 6 (extensibility patterns) + relevant sections in 2 or 3

**For Troubleshooting:**
→ Chapter 5 (documentation), Chapter 6 (troubleshooting section)

---

## 🔗 Cross-Reference Guide

| Need | Location |
|------|----------|
| How OddsEngine works | 2.6 + 6.2 |
| Adding a new adapter | 2.3, 2.4 + 6.7 |
| Frontend state flow | 3.2 + 6.4 |
| Windows Service setup | 5.4 + 6.1 |
| API endpoints | 2.7 + Appendix C |
| Troubleshooting | 6.6 |
| Performance tuning | 4.5 + 6.5 |
| Credential config | 2.1 + 5.3 |

---

## Summary: The Fortuna Blueprint

This 52-page pseudocode document comprehensively covers:

✅ **What** Fortuna does (racing data aggregation & analysis)
✅ **How** it's architected (two pillars + infrastructure)
✅ **Where** everything lives (backend, frontend, utilities)
✅ **When** to use each component (deployment, monitoring, extension)
✅ **Why** specific design decisions were made (history, constraints)

**It's a complete specification for understanding, operating, extending, and deploying the entire Fortuna Faucet system.**