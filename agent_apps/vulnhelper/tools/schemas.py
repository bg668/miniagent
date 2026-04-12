QUERY_VULNS_SCHEMA = {
    "type": "object",
    "properties": {
        "session_id": {"type": "string"},
        "plan": {"type": "object"},
    },
    "required": ["session_id", "plan"],
    "additionalProperties": False,
}


FILTER_CACHED_RESULTS_SCHEMA = {
    "type": "object",
    "properties": {
        "session_id": {"type": "string"},
        "filter_spec": {"type": "object"},
    },
    "required": ["session_id", "filter_spec"],
    "additionalProperties": False,
}

