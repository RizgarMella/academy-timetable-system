import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DATABASE_PATH = os.path.join(BASE_DIR, 'timetable.db')
DATABASE_URI = f'sqlite:///{DATABASE_PATH}'

# Solver parameters
SOLVER_TIMEOUT_SECONDS = 120
SLOTS_PER_DAY = 8  # 1-hour slots, 09:00-17:00
DAYS_PER_WEEK = 5  # Monday-Friday
SLOT_START_HOUR = 9

# Academic year
YEAR_START_MONTH = 9  # September
YEAR_END_MONTH = 7    # July (next calendar year)
