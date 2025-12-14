"""
The Auditor: Real-Time Race Verification System

This module runs as a background thread within the Python Backend.
It verifies predictions against official results and calculates profitability.

Requirements:
    pip install aiosqlite httpx beautifulsoup4 lxml structlog
"""

import asyncio
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import httpx
from bs4 import BeautifulSoup
import structlog
import re

logger = structlog.get_logger()


@dataclass
class OfficialResult:
    """Represents official race results from Equibase/GBGB"""
    race_id: str
    finishers: List[Dict[str, Any]]  # List of {name, position, place_payout}


class AuditorEngine:
    """
    Real-time verification engine that tracks predictions and verifies them
    against official results.
    """

    def __init__(self, db_path: str = "audit.db"):
        self.db_path = db_path
        self.http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self.TOTE_UNIT = 2.00  # Standard $2.00 bet unit
        self._running = False
        self._init_database()

        # Simple mapping for UK racecourses
        self.TRACK_CODE_MAP = {
            "DON": "Doncaster",
            "LING": "Lingfield",
            "NCLE": "Newcastle",
            "WOLV": "Wolverhampton",
            "CHELT": "Cheltenham",
        }

    def _init_database(self):
        """Initialize the SQLite database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                race_id TEXT PRIMARY KEY,
                track_code TEXT NOT NULL,
                race_number INTEGER NOT NULL,
                predicted_horse TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                official_payout REAL DEFAULT 0.00,
                net_profit REAL DEFAULT 0.00,
                CHECK (status IN ('PENDING', 'CASHED', 'BURNED'))
            )
        """)

        # Index for faster pending race queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status_timestamp
            ON audit_log(status, timestamp)
        """)

        conn.commit()
        conn.close()
        logger.info("Database initialized", db_path=self.db_path)

    async def snapshot_qualifier(
        self,
        venue_code: str,
        race_date: str,
        race_number: int,
        predicted_horse: str
    ) -> bool:
        """
        Phase 1: The Snapshot
        Called by OddsEngine when a race qualifies as a bet.

        Args:
            venue_code: Track code (e.g., "GP", "SA")
            race_date: Date in YYYYMMDD format
            race_number: Race number
            predicted_horse: Name of predicted horse

        Returns:
            True if snapshot saved, False if already exists
        """
        race_id = self._generate_race_id(venue_code, race_date, race_number)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO audit_log
                (race_id, track_code, race_number, predicted_horse, timestamp, status)
                VALUES (?, ?, ?, ?, ?, 'PENDING')
            """, (race_id, venue_code, race_number, predicted_horse, datetime.now()))

            conn.commit()
            conn.close()

            logger.info(
                "Snapshot saved for verification",
                race_id=race_id,
                horse=predicted_horse
            )
            return True

        except sqlite3.IntegrityError:
            logger.warning("Race already tracked", race_id=race_id)
            return False

    async def run_audit_loop(self):
        """
        Phase 2: The Fetcher
        Runs continuously to check results for pending races.
        """
        self._running = True
        logger.info("Audit loop started")

        while self._running:
            try:
                # Find pending races from the last 60 minutes
                cutoff_time = datetime.now() - timedelta(minutes=60)
                pending_races = self._get_pending_races(cutoff_time)

                if not pending_races:
                    logger.debug("No pending races to audit")
                    await asyncio.sleep(120)
                    continue

                logger.info(f"Found {len(pending_races)} pending races to verify")

                # Fetch official results (batch by track to be polite)
                tracks_to_check = set(race['track_code'] for race in pending_races)

                for track_code in tracks_to_check:
                    track_races = [r for r in pending_races if r['track_code'] == track_code]

                    for race in track_races:
                        official_result = await self._fetch_official_result(
                            race['track_code'],
                            race['race_number']
                        )

                        if official_result:
                            self._determine_verdict(race, official_result)

                        # Be polite to the server
                        await asyncio.sleep(2)

            except Exception as e:
                logger.error("Error in audit loop", error=str(e), exc_info=True)

            await asyncio.sleep(120)

    def stop_audit_loop(self):
        """Stop the audit loop gracefully"""
        self._running = False
        logger.info("Audit loop stopped")

    def _get_pending_races(self, cutoff_time: datetime) -> List[Dict]:
        """Get all pending races after cutoff time"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM audit_log
            WHERE status = 'PENDING' AND timestamp > ?
            ORDER BY timestamp ASC
        """, (cutoff_time,))

        races = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return races

    def _determine_verdict(self, prediction: Dict, official_result: OfficialResult):
        """
        Phase 3: The Verdict & Economics
        Determine if prediction was correct and calculate profit/loss.
        """
        did_place = False
        payout = 0.00

        # Check if our horse is in the official "Place" payouts
        # Note: "Place" in US racing covers 1st and 2nd
        for finisher in official_result.finishers:
            if (finisher['name'].upper() == prediction['predicted_horse'].upper() and
                finisher.get('place_payout', 0) > 0):
                did_place = True
                payout = finisher['place_payout']
                break

        # Calculate Net Profit based on $2.00 Unit
        if did_place:
            new_status = 'CASHED'
            net_profit = payout - self.TOTE_UNIT
            logger.info(
                "💰 CASHED",
                race_id=prediction['race_id'],
                horse=prediction['predicted_horse'],
                payout=payout,
                profit=net_profit
            )
        else:
            new_status = 'BURNED'
            net_profit = -self.TOTE_UNIT  # Lost the $2.00 stake
            logger.warning(
                "🔥 BURNED",
                race_id=prediction['race_id'],
                horse=prediction['predicted_horse'],
                loss=net_profit
            )

        # Update the Source of Truth
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE audit_log
            SET status = ?, official_payout = ?, net_profit = ?
            WHERE race_id = ?
        """, (new_status, payout, net_profit, prediction['race_id']))

        conn.commit()
        conn.close()

    async def _find_race_url(self, track_code: str, race_number: int) -> Optional[str]:
        """Finds the specific race URL from the main results page."""
        try:
            base_url = "https://www.attheraces.com"
            results_url = f"{base_url}/results"

            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = await self.http_client.get(results_url, headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')
            track_name = self.TRACK_CODE_MAP.get(track_code.upper())
            if not track_name:
                logger.warning("Track code not mapped", track_code=track_code)
                return None

            # Use a case-insensitive regex to make the search more robust
            track_header = soup.find('h2', string=re.compile(track_name, re.IGNORECASE))
            if not track_header:
                logger.debug("Track not found on results page", track_name=track_name)
                return None

            # Find the parent container of the track's results
            track_container = track_header.find_parent(class_='panel')
            if not track_container:
                logger.debug("Could not find track container", track_name=track_name)
                return None

            # Get all race links for that track and select by index
            race_links = track_container.select('a[href*="/racecard/"]')
            if len(race_links) >= race_number:
                race_path = race_links[race_number - 1]['href']
                return f"{base_url}{race_path}"
            else:
                logger.debug("Race number out of bounds for track", race_number=race_number, track_name=track_name)
                return None

        except Exception as e:
            logger.error("Error finding race URL", error=str(e), exc_info=True)
            return None

    async def _fetch_official_result(
        self,
        track_code: str,
        race_number: int
    ) -> Optional[OfficialResult]:
        """
        Helper: Scraper Logic for attheraces.com
        """
        try:
            race_url = await self._find_race_url(track_code, race_number)
            if not race_url:
                return None

            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = await self.http_client.get(race_url, headers=headers)

            if response.status_code == 404:
                logger.debug("Results page not found (404)", url=race_url)
                return None

            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')
            race_result = self._parse_attheraces_results(soup, track_code, race_number)

            if race_result:
                logger.info("Official results fetched", track=track_code, race=race_number)
                return race_result
            else:
                logger.debug("Results not yet posted or parsed", track=track_code, race=race_number)
                return None

        except httpx.HTTPError as e:
            logger.warning("Failed to fetch results page", url=getattr(e.request, 'url', ''), error=str(e))
            return None
        except Exception as e:
            logger.error("Error parsing results", track=track_code, race=race_number, error=str(e), exc_info=True)
            return None

    def _parse_attheraces_results(
        self,
        soup: BeautifulSoup,
        track_code: str,
        race_number: int
    ) -> Optional[OfficialResult]:
        """
        Parse attheraces.com HTML to extract race results using a table-based approach.
        """
        results_table = None
        all_tables = soup.find_all('table')
        for table in all_tables:
            header_cells = table.select('thead th')
            if any("Horse" in cell.text for cell in header_cells):
                results_table = table
                break

        if not results_table:
            logger.debug("Could not find a suitable results table on the page.")
            return None

        finishers = []
        rows = results_table.select('tbody tr')

        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 3:
                continue

            try:
                pos_text = cells[0].text.strip()
                try:
                    position = int(pos_text)
                except ValueError:
                    position = 99

                horse_name_el = cells[2].select_one('a[href*="/form/horse/"]')
                if not horse_name_el:
                    continue

                horse_name = horse_name_el.text.strip()

                finisher = {
                    'name': horse_name,
                    'position': position,
                    'place_payout': 0.0,
                }
                finishers.append(finisher)

            except (ValueError, IndexError) as e:
                logger.warning("Could not parse a result row", error=str(e))
                continue

        if not finishers:
            logger.debug("Table found, but could not parse any finishers.")
            return None

        win_payout = 0.0
        try:
            betting_returns_header = soup.find('h3', string=re.compile(r'Betting returns'))
            if betting_returns_header:
                betting_returns_table = betting_returns_header.find_next('table')
                if betting_returns_table:
                    win_row = betting_returns_table.find('td', string=re.compile(r'Win'))
                    if win_row:
                        payout_str = win_row.find_next_sibling('td').text
                        payout_match = re.search(r'[\d\.]+', payout_str)
                        if payout_match:
                            win_payout = float(payout_match.group(0))
        except Exception as e:
            logger.warning("Could not parse win payout", error=str(e))

        for f in finishers:
            if f['position'] == 1:
                f['place_payout'] = win_payout
                break

        race_id = self._generate_race_id(track_code, datetime.now().strftime("%Y%m%d"), race_number)
        return OfficialResult(race_id=race_id, finishers=finishers)

    def _generate_race_id(self, venue_code: str, race_date: str, race_number: int) -> str:
        """Generate unique race ID"""
        return f"{venue_code.upper()}-{race_date}-{race_number:02d}"

    def get_rolling_metrics(self, minutes: int = 60) -> Dict[str, Any]:
        """
        Phase 4: Dashboard Metrics
        Returns stats for the UI "Last Hour" overlay.

        Args:
            minutes: Rolling window in minutes (default 60)

        Returns:
            Dictionary with strike_rate, net_profit, and volume
        """
        cutoff = datetime.now() - timedelta(minutes=minutes)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'CASHED' THEN 1 ELSE 0 END) as wins,
                SUM(net_profit) as profit
            FROM audit_log
            WHERE timestamp > ? AND status != 'PENDING'
        """, (cutoff,))

        row = cursor.fetchone()
        conn.close()

        total = row[0] or 0
        wins = row[1] or 0
        profit = row[2] or 0.0

        strike_rate = (wins / total * 100) if total > 0 else 0.0

        return {
            "strike_rate": round(strike_rate, 2),
            "net_profit": round(profit, 2),
            "volume": total,
            "window_minutes": minutes
        }

    def get_recent_activity(self, limit: int = 10) -> List[Dict]:
        """Get recent audit activity for display"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM audit_log
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        activity = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return activity

    async def cleanup(self):
        """Cleanup resources"""
        self.stop_audit_loop()
        await self.http_client.aclose()
        logger.info("Auditor engine cleaned up")


async def smoke_test_auditor():
    """A simple test to verify the new scraper logic."""
    logger.info("Starting Auditor smoke test...")
    auditor = AuditorEngine(db_path="smoke_test_audit.db")

    # We need a race that has results. Let's assume Doncaster, Race 1.
    track_code = "DON"
    race_number = 1

    logger.info(f"Attempting to fetch results for {track_code} Race {race_number}")

    # Directly call the fetcher
    official_result = await auditor._fetch_official_result(track_code, race_number)

    if official_result and official_result.finishers:
        logger.info("Smoke test PASSED. Successfully fetched and parsed results.")
        print("\n--- SMOKE TEST RESULTS ---")
        print(f"Race ID: {official_result.race_id}")
        print("Finishers:")
        for finisher in official_result.finishers:
            print(f"  Position: {finisher['position']}, Name: {finisher['name']}, Payout: {finisher['place_payout']}")
        print("------------------------\n")
    else:
        logger.error("Smoke test FAILED. Could not fetch or parse results.")
        print("\n--- SMOKE TEST FAILED ---")
        print("No results were returned. Check the logs for errors.")
        print("-----------------------\n")

    await auditor.cleanup()
    # Clean up the test database
    import os
    if os.path.exists("smoke_test_audit.db"):
        os.remove("smoke_test_audit.db")

if __name__ == "__main__":
    # To run the smoke test: python -m python_service.auditor
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )
    asyncio.run(smoke_test_auditor())
