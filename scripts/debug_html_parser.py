import sys
import json
from bs4 import BeautifulSoup

def analyze_html_structure(html_content, selector='a[href*="racecard"]'):
    """
    Parses HTML to find potential race links and returns their structure.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    links_data = []

    # Use the provided selector or the default
    possible_links = soup.select(selector)

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
    Main function to read an HTML file, parse it, and save the JSON structure to an output file.
    """
    if len(sys.argv) < 3:
        print("Usage: python debug_html_parser.py <input_html_path> <output_json_path> [css_selector]", file=sys.stderr)
        sys.exit(1)

    input_filepath = sys.argv[1]
    output_filepath = sys.argv[2]
    selector = sys.argv[3] if len(sys.argv) > 3 else 'a[href*="racecard"]'

    output_data = {"links": [], "error": None}

    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            html_content = f.read()
            if not html_content.strip():
                output_data["error"] = f"File is empty: {input_filepath}"
            else:
                output_data["links"] = analyze_html_structure(html_content, selector)

    except FileNotFoundError:
        output_data["error"] = f"File not found: {input_filepath}"
    except Exception as e:
        output_data["error"] = f"An unexpected error occurred while reading {input_filepath}: {e}"

    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)
    except Exception as e:
        # If we can't write the file, print the error to stderr as a last resort
        print(f"Critical error: Could not write to output file {output_filepath}. Reason: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
