# Copyright (c) 2026 Jérémy Rotzetter

"""ArtStation HTTP fetching, URL parsing, and JSON helpers."""

import json
import logging
import re
import time

logger = logging.getLogger(__name__)

RETRYABLE = {403, 500, 502, 503, 504}


def fetch_with_retry(session, url, max_retries=3, delay=1.5):
    """Retry on 403 and common transient 5xx. Raise on 429 and other 4xx."""
    for attempt in range(1, max_retries + 1):
        response = session.get(url)
        if response.status_code in RETRYABLE and attempt < max_retries:
            logger.warning(
                "HTTP %d on attempt %d/%d, retrying in %.1fs",
                response.status_code,
                attempt,
                max_retries,
                delay,
            )
            time.sleep(delay)
            continue
        response.raise_for_status()
        return response


def extract_hashid(raw_input: str) -> str | None:
    """
    Extract and validate a project hash ID from raw input.
    Accepts either a raw hash ID or a full ArtStation project URL.

    Returns:
        str: The valid alphanumeric hash ID.
        None: If validation fails.
    """
    raw_input = raw_input.strip()

    # Handle empty strings
    if not raw_input:
        return None

    match = re.search(r"artstation\.com/artwork/([a-zA-Z0-9]+)", raw_input)

    # Assume the input is already just the hash ID if no URL pattern is found
    hashid = match.group(1) if match else raw_input

    # Validate hashid format (should only be alphanumeric)
    if not re.match(r"^[a-zA-Z0-9]+$", hashid):
        return None

    return hashid


def load_json(json_string: str):
    """Parse a JSON string. Returns the parsed object or None on failure."""
    try:
        result = json.loads(json_string)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse failed at position %s: %s", e.pos, e.msg)
        return None
    if result is None:
        logger.debug("JSON body was null")
    return result


def fetch_project(session, hashid: str) -> dict:
    """Fetch and parse a project's JSON data from ArtStation."""
    url = f"https://www.artstation.com/projects/{hashid}.json"
    logger.debug("Fetching %s", url)
    response = fetch_with_retry(session, url)
    return response.json()
