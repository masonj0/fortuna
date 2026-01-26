"""
JSON Schema definitions for pipeline output validation.
"""

from typing import Dict, Any

# Schema for individual race
RACE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["id", "venue", "race_number", "start_time", "runners", "source"],
    "properties": {
        "id": {"type": "string", "minLength": 1},
        "venue": {"type": "string", "minLength": 1},
        "race_number": {"type": "integer", "minimum": 1},
        "start_time": {"type": "string", "format": "date-time"},
        "discipline": {"type": "string"},
        "distance": {"type": ["string", "null"]},
        "surface": {"type": ["string", "null"]},
        "purse": {"type": ["number", "null"]},
        "source": {"type": "string"},
        "runners": {
            "type": "array",
            "minItems": 0,
            "items": {
                "type": "object",
                "required": ["number", "name"],
                "properties": {
                    "number": {"type": "integer", "minimum": 1},
                    "name": {"type": "string", "minLength": 1},
                    "scratched": {"type": "boolean"},
                    "jockey": {"type": ["string", "null"]},
                    "trainer": {"type": ["string", "null"]},
                    "weight": {"type": ["number", "null"]},
                    "odds": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "win": {"type": "number"},
                                "place": {"type": ["number", "null"]},
                                "show": {"type": ["number", "null"]},
                                "source": {"type": "string"},
                                "last_updated": {"type": "string"}
                            }
                        }
                    }
                }
            }
        }
    }
}

# Schema for qualified races output
QUALIFIED_RACES_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["races", "generated_at", "analyzer"],
    "properties": {
        "races": {
            "type": "array",
            "items": RACE_SCHEMA
        },
        "generated_at": {"type": "string", "format": "date-time"},
        "analyzer": {"type": "string"},
        "filter_criteria": {"type": "object"},
        "statistics": {
            "type": "object",
            "properties": {
                "total_races_analyzed": {"type": "integer"},
                "qualified_count": {"type": "integer"},
                "sources_used": {"type": "array", "items": {"type": "string"}}
            }
        }
    }
}

# Schema for raw race data
RAW_RACE_DATA_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["races", "fetch_timestamp"],
    "properties": {
        "races": {
            "type": "array",
            "items": RACE_SCHEMA
        },
        "fetch_timestamp": {"type": "string", "format": "date-time"},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "status": {"type": "string", "enum": ["success", "partial", "failed"]},
                    "race_count": {"type": "integer"},
                    "error": {"type": ["string", "null"]}
                }
            }
        }
    }
}
