from datetime import date, timedelta


def compute_week_start() -> str:
    """Return the Monday of the most recently completed Mon-Sun cycle.

    The scraper clicks "Last Week", so this returns the Monday of the
    previous full week (not the current in-progress week).
    """
    today = date.today()
    # Monday = 0. days_since_monday gives offset into current week.
    days_since_monday = today.weekday()
    # Current week's Monday
    this_monday = today - timedelta(days=days_since_monday)
    # Last completed week's Monday
    last_monday = this_monday - timedelta(days=7)
    return last_monday.isoformat()
