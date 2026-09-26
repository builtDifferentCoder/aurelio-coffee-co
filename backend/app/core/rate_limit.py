import logging
from collections import defaultdict
from typing import Dict, Tuple

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

logger = logging.getLogger("aurelio.rate_limit")

# 1. Per-IP daily rate limiter initialized from settings
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_IP_DAILY}/day"],
)

# 2. In-memory session message tracking (session_id -> message_count)
session_message_counts: Dict[str, int] = defaultdict(int)


def check_session_limit(session_id: str) -> Tuple[bool, int]:
    """
    Check and enforce MAX_MESSAGES_PER_SESSION for a session_id.
    
    Returns:
        Tuple of (is_allowed: bool, count: int)
        If limit is reached, returns (False, current_count) without incrementing.
        If within limit, increments count and returns (True, new_count).
    """
    current_count = session_message_counts[session_id]
    if current_count >= settings.MAX_MESSAGES_PER_SESSION:
        logger.warning(
            f"Session '{session_id}' exceeded max messages ({current_count}/{settings.MAX_MESSAGES_PER_SESSION})"
        )
        return False, current_count

    session_message_counts[session_id] += 1
    return True, session_message_counts[session_id]


def reset_session_counts():
    """Reset session counters (primarily for testing)."""
    session_message_counts.clear()
