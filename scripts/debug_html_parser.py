"""
Analyze debug HTML files to diagnose scraping failures.
"""

import sys
import json
from pathlib import Path
from collections import Counter


def analyze_html(html_path: str, output_path: str):
    """Analyze HTML file and output diagnosis."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("Installing beautifulsoup4...")
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'beautifulsoup4', 'lxml'])
        from bs4 import BeautifulSoup

    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'lxml')

    analysis = {
        "file": html_path,
        "size_bytes": len(content),
        "title": soup.title.string if soup.title else None,
        "issues": [],
        "recommendations": [],
        "selector_matches": {},
        "structure_info": {},
    }

    # Check for blocking/challenges
    content_lower = content.lower()

    if 'captcha' in content_lower:
        analysis["issues"].append("CAPTCHA challenge detected")
        analysis["recommendations"].append("Enable solve_cloudflare=True or increase delays")

    if 'cloudflare' in content_lower or 'cf-browser-verification' in content_lower:
        analysis["issues"].append("CloudFlare protection detected")
        analysis["recommendations"].append("Use StealthyFetcher with google_search=True")

    if 'access denied' in content_lower or 'forbidden' in content_lower:
        analysis["issues"].append("Access denied response")
        analysis["recommendations"].append("Check IP reputation, try different user agent")

    if len(content) < 1000:
        analysis["issues"].append("Very small response - likely blocked")
        analysis["recommendations"].append("Check if IP is rate limited")

    if not soup.body or len(soup.body.get_text(strip=True)) < 100:
        analysis["issues"].append("Empty or minimal body content")

    # Check for race-related content
    race_indicators = ['race', 'horse', 'runner', 'odds', 'post time', 'track']
    found_indicators = [ind for ind in race_indicators if ind in content_lower]
    analysis["structure_info"]["race_indicators_found"] = found_indicators

    if not found_indicators:
        analysis["issues"].append("No race-related content found")
        analysis["recommendations"].append("Page may not be the race listings page")

    # Test common selectors
    test_selectors = [
        ('div[class*="race"]', 'race containers'),
        ('div[class*="Race"]', 'Race containers (capitalized)'),
        ('div[class*="card"]', 'card elements'),
        ('[class*="runner"]', 'runner elements'),
        ('[class*="horse"]', 'horse elements'),
        ('[class*="odds"]', 'odds elements'),
        ('table', 'tables'),
        ('tr', 'table rows'),
        ('time', 'time elements'),
    ]

    for selector, description in test_selectors:
        try:
            matches = soup.select(selector)
            if matches:
                analysis["selector_matches"][description] = {
                    "count": len(matches),
                    "selector": selector,
                    "sample_classes": list(set([
                        ' '.join(m.get('class', []))[:50]
                        for m in matches[:3]
                    ]))
                }
        except Exception as e:
            pass

    # Get unique class names
    all_classes = []
    for tag in soup.find_all(class_=True):
        all_classes.extend(tag.get('class', []))

    class_counts = Counter(all_classes)
    analysis["structure_info"]["top_classes"] = dict(class_counts.most_common(40))

    # Check for JavaScript-rendered content indicators
    if '<noscript>' in content:
        analysis["issues"].append("Page uses JavaScript rendering")
        analysis["recommendations"].append("Ensure network_idle=True and sufficient timeout")

    # Save analysis
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(analysis, f, indent=2)

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"Analysis: {html_path}")
    print(f"{'=' * 60}")
    print(f"Size: {analysis['size_bytes']:,} bytes")
    print(f"Title: {analysis['title']}")

    if analysis["issues"]:
        print(f"\n⚠️ Issues Found:")
        for issue in analysis["issues"]:
            print(f"  - {issue}")

    if analysis["recommendations"]:
        print(f"\n💡 Recommendations:")
        for rec in analysis["recommendations"]:
            print(f"  - {rec}")

    if analysis["selector_matches"]:
        print(f"\n✓ Selector Matches:")
        for desc, info in analysis["selector_matches"].items():
            print(f"  - {desc}: {info['count']} matches")

    print(f"\nFull analysis saved to: {output_path}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python debug_html_parser.py <html_file> <output_json>")
        sys.exit(1)

    analyze_html(sys.argv[1], sys.argv[2])
