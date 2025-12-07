"""
LLM State Management

مدیریت وضعیت LLM ها (up/down) برای جلوگیری از تلاش‌های بیهوده
"""

import structlog

logger = structlog.get_logger()

# Global flag to track if primary LLM is down (used to skip primary in subsequent calls)
_primary_llm_down: bool = False


def is_primary_llm_down() -> bool:
    """Check if primary LLM is marked as down."""
    return _primary_llm_down


def set_primary_llm_down(down: bool = True):
    """Mark primary LLM as down or up."""
    global _primary_llm_down
    _primary_llm_down = down
    if down:
        logger.warning("Primary LLM marked as DOWN - will use fallback directly")
    else:
        logger.info("Primary LLM marked as UP")


def reset_primary_llm_state():
    """Reset primary LLM state to UP (for testing or recovery)."""
    global _primary_llm_down
    _primary_llm_down = False
    logger.info("Primary LLM state reset to UP")
