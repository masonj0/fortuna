import json
import re
from selectolax.parser import HTMLParser
import html

def test_greyhound_extraction():
    with open("scripts/atr_greyhound_race.html", "r") as f:
        content = f.read()

    parser = HTMLParser(content)
    page_content = parser.css_first("page-content")
    if not page_content:
        print("page-content not found")
        # Try finding the string manually
        match = re.search(r'<page-content[^>]+:modules="([^"]+)"', content)
        if match:
            modules_raw = match.group(1)
            print("Found modules via regex")
        else:
            print("Could not find modules via regex either")
            return
    else:
        print(f"Attributes: {list(page_content.attributes.keys())}")
        modules_raw = page_content.attributes.get(":modules") or page_content.attributes.get(":items")

    if not modules_raw:
        print(":modules or :items attribute not found")
        return

    # Unescape HTML entities
    modules_json = html.unescape(modules_raw)

    try:
        modules = json.loads(modules_json)
        print(f"Found {len(modules)} modules")

        for module in modules:
            m_type = module.get("type")
            print(f"Module Type: {m_type}")

            if m_type == "RacecardEntries":
                data = module.get("data", {})
                entries = data.get("entries", [])
                print(f"Found {len(entries)} entries in RacecardEntries")
                for entry in entries:
                    horse = entry.get("greyhound", entry.get("horse", {}))
                    name = horse.get("name")
                    trap = entry.get("trap")
                    print(f"  - Trap {trap}: {name}")

            if m_type == "OddsGrid":
                data = module.get("data", {})
                print(f"OddsGrid data keys: {list(data.keys())}")
                if 'oddsGrid' in data:
                    rows = data['oddsGrid'].get("rows", [])
                    print(f"Found {len(rows)} rows in data['oddsGrid']")
                    for row in rows:
                        greyhound = row.get("greyhound", {})
                        name = greyhound.get("name")
                        best_price = row.get("bestPrice", {}).get("decimal")
                        print(f"  - {name}: Best Price {best_price}")

    except Exception as e:
        print(f"Error parsing modules JSON: {e}")

if __name__ == "__main__":
    test_greyhound_extraction()
