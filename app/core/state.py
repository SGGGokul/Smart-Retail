import time

# Record process startup timestamp for uptime calculations
START_TIME: float = time.time()


def get_uptime_seconds() -> int:
    """Return integer seconds elapsed since backend startup."""
    return max(0, int(time.time() - START_TIME))
