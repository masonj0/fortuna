import sys
import json
from bs4 import BeautifulSoup

def analyze_html_structure(html_content):
    """
    Parses HTML to find potential race links and returns their structure.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    links_data = []

    # A broad but targeted search for links that are likely racecards
    possible_links = soup.select('a[href*="racecard"]')

    for link in possible_links:
        parent = link.parent
        grandparent = parent.parent if parent else None

        link_info = {
            'href': link.get('href', ''),
            'text': link.get_text(strip=True),
            'parent_tag': parent.name if parent else None,
            'parent_classes': parent.get('class', []) if parent else [],
            'grandparent_tag': grandparent.name if grandparent else None,
            'grandparent_classes': grandparent.get('class', []) if grandparent else [],
        }
        links_data.append(link_info)

    return links_data

def main():
    """
    Main function to read file, parse it, and print JSON structure.
    """
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No HTML file path provided."}), file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(json.dumps({"error": f"File not found: {filepath}"}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Error reading file: {e}"}), file=sys.stderr)
        sys.exit(1)

    if not html_content.strip():
        print(json.dumps({"error": f"File is empty: {filepath}"}))
        return

    extracted_data = analyze_html_structure(html_content)

    print(json.dumps(extracted_data, indent=2))

if __name__ == "__main__":
    main()
