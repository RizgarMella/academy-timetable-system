"""Time discretization helpers for the timetable solver.

The solver works in discrete day indices relative to the academic year start
date. Each day has SLOTS_PER_DAY teaching slots (8 slots = 8 hours, 09:00-17:00).
Only weekdays (Mon-Fri) are used, so DAYS_PER_WEEK=5.
"""

import math
from datetime import date, timedelta

SLOTS_PER_DAY = 8
DAYS_PER_WEEK = 5
CALENDAR_DAYS_PER_WEEK = 7


def date_to_day_index(d, year_start_date):
    """Convert a calendar date to a day index relative to the academic year start.

    The day index counts only weekdays. Day 0 is the year_start_date (which
    should itself be a weekday).

    Args:
        d: The target date.
        year_start_date: The first day of the academic year.

    Returns:
        Integer day index (weekday-only count from year_start_date).
    """
    if d < year_start_date:
        raise ValueError(
            f"Date {d} is before the academic year start {year_start_date}"
        )
    weekday_count = 0
    current = year_start_date
    while current < d:
        if current.weekday() < 5:  # Mon-Fri
            weekday_count += 1
        current += timedelta(days=1)
    return weekday_count


def day_index_to_date(day_index, year_start_date):
    """Convert a weekday-only day index back to a calendar date.

    Args:
        day_index: The weekday-only index (0 = year_start_date).
        year_start_date: The first day of the academic year.

    Returns:
        The corresponding calendar date.
    """
    if day_index < 0:
        raise ValueError(f"Day index must be non-negative, got {day_index}")
    weekdays_counted = 0
    current = year_start_date
    while weekdays_counted < day_index:
        current += timedelta(days=1)
        if current.weekday() < 5:
            weekdays_counted += 1
    return current


def get_week_number(day_index):
    """Return the zero-based week number for a given weekday day index.

    Week 0 contains day indices 0-4, week 1 contains 5-9, etc.
    """
    return day_index // DAYS_PER_WEEK


def is_weekday(d):
    """Check whether a date falls on a weekday (Monday-Friday)."""
    return d.weekday() < 5


def duration_hours_to_days(duration_hours):
    """Convert a module's duration in hours to the number of full teaching days.

    A module with 16 hours takes ceil(16/8) = 2 full days.
    """
    return math.ceil(duration_hours / SLOTS_PER_DAY)


def get_total_weekdays(start_date, end_date):
    """Count the total number of weekdays between two dates (inclusive)."""
    count = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count
