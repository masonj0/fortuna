import json
import html
from typing import Any, List, Optional
from selectolax.parser import HTMLParser

class JSONParsingMixin:
    """Mixin for safe JSON extraction from HTML and scripts."""

    def _parse_json_from_script(self, parser: HTMLParser, selector: str, context: str = "script") -> Optional[Any]:
        script = parser.css_first(selector)
        if not script:
            return None
        try:
            return json.loads(script.text())
        except json.JSONDecodeError as e:
            if hasattr(self, 'logger'):
                self.logger.error("failed_parsing_json", context=context, selector=selector, error=str(e))
            return None

    def _parse_json_from_attribute(self, parser: HTMLParser, selector: str, attribute: str, context: str = "attribute") -> Optional[Any]:
        el = parser.css_first(selector)
        if not el:
            return None
        raw = el.attributes.get(attribute)
        if not raw:
            return None
        try:
            return json.loads(html.unescape(raw))
        except json.JSONDecodeError as e:
            if hasattr(self, 'logger'):
                self.logger.error("failed_parsing_json", context=context, selector=selector, attribute=attribute, error=str(e))
            return None

    def _parse_all_jsons_from_scripts(self, parser: HTMLParser, selector: str, context: str = "scripts") -> List[Any]:
        results = []
        for script in parser.css(selector):
            try:
                results.append(json.loads(script.text()))
            except json.JSONDecodeError as e:
                if hasattr(self, 'logger'):
                    self.logger.error("failed_parsing_json_in_list", context=context, selector=selector, error=str(e))
        return results
