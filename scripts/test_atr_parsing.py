import os
from datetime import datetime
from selectolax.parser import HTMLParser
from python_service.adapters.at_the_races_adapter import AtTheRacesAdapter

def test_atr_parsing():
    adapter = AtTheRacesAdapter()
    snapshot_path = "debug-snapshots/attheraces/20260128_101537_709387_atr_index_2026-01-28.html"

    with open(snapshot_path, "r") as f:
        html = f.read()

    parser = HTMLParser(html)
    links = adapter._find_links_with_fallback(parser)
    print(f"Found {len(links)} links")

    # Let's see some links
    for i, link in enumerate(list(links)[:5]):
        print(f"Link {i}: {link}")

if __name__ == "__main__":
    test_atr_parsing()
