# Academy Timetable System

A web-based scheduling system for training academies that automatically generates optimised timetables for courses, lecturers, and classrooms across academic years.

## Features

- **Automated Scheduling** -- Greedy heuristic solver that assigns lecturers and classrooms to course modules while respecting constraints (qualifications, availability, capacity, prep/wind-down time, load balancing)
- **Interactive Gantt Chart** -- Timeline view of the full schedule, groupable by course run, lecturer, or classroom. Supports year/quarter/month zoom, filtering, and multi-year view
- **Lecturer Loading Heatmap** -- Weekly hour heatmap per lecturer with expandable course breakdowns, balance score, and capacity utilisation bars
- **Course Manager** -- Browse courses and their runs with per-run schedule mini-Gantt, lecturer loading overlay, and resit tracking
- **Rules Engine** -- Toggle scheduling rules (e.g. "teacher cannot examine own students") from the UI
- **Resit Scheduling** -- Automatic placement of resit exams respecting the teacher-cannot-examine rule

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask 3.1 (Python) |
| Database | SQLite via SQLAlchemy 2.0 |
| Solver | Google OR-Tools 9.11 (greedy heuristic scheduler) |
| Frontend | Vanilla JavaScript, HTML, CSS |

## Quick Start

```bash
# Clone the repo
git clone https://github.com/RizgarMella/academy-timetable-system.git
cd academy-timetable-system

# Install dependencies (Python 3.10+)
pip install -r requirements.txt

# Run the app
python app.py
```

Open **http://localhost:5000** in your browser. On first run the database is auto-seeded with sample data (courses, lecturers, classrooms, and a pre-solved schedule).

## Project Structure

```
├── app.py                  # Flask application entry point
├── config.py               # Global configuration (slots, academic year dates)
├── seed_data.py            # Sample data seeder (runs on first launch)
├── models/                 # SQLAlchemy data models
│   ├── course.py           #   AcademicYear, Course, Module, CourseRun
│   ├── lecturer.py         #   Lecturer, LecturerAvailability
│   ├── classroom.py        #   Classroom, ClassroomAvailability
│   ├── qualification.py    #   LecturerQualification
│   ├── schedule.py         #   ScheduledSession
│   ├── resit.py            #   Resit
│   └── rule.py             #   Rule
├── solver/                 # Scheduling engine
│   ├── engine.py           #   TimetableSolver (greedy heuristic)
│   ├── utils.py            #   Date/slot conversion helpers
│   ├── constraints.py      #   Constraint definitions (CP-SAT, not yet integrated)
│   └── objectives.py       #   Soft objectives (not yet integrated)
├── routes/                 # Flask blueprints
│   ├── views.py            #   HTML page routes
│   ├── api_data.py         #   CRUD REST endpoints
│   ├── api_schedule.py     #   Schedule & Gantt endpoints
│   └── api_solver.py       #   Solver job endpoints
├── templates/              # Jinja2 HTML templates
│   ├── base.html           #   Layout shell
│   ├── index.html          #   Dashboard
│   ├── gantt.html          #   Gantt chart
│   ├── courses.html        #   Course manager
│   ├── lecturers.html      #   Lecturer loading heatmap
│   ├── solver.html         #   Solver control panel
│   └── rules.html          #   Rules configuration
└── static/
    ├── css/                # Stylesheets
    └── js/                 # Frontend JavaScript (api.js, app.js)
```

## API Endpoints

### Data (CRUD)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/lecturers` | List all lecturers |
| GET | `/api/lecturers/<id>` | Lecturer detail with qualifications |
| GET | `/api/courses` | List all courses |
| GET | `/api/courses/<id>` | Course detail with modules |
| GET | `/api/modules` | List modules (filter by `course_id`) |
| GET | `/api/classrooms` | List all classrooms |
| GET | `/api/course-runs` | List course runs (filter by `year_id`, `course_id`) |
| GET | `/api/qualifications` | List qualifications (filter by `lecturer_id`) |
| GET | `/api/resits` | List resits (filter by `course_run_id`, `status`) |
| GET | `/api/rules` | List rules |
| PUT | `/api/rules/<id>` | Update rule |
| GET | `/api/academic-years` | List academic years |

### Schedule
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/schedule` | List sessions (many filters) |
| GET | `/api/schedule/gantt` | Gantt data grouped by course_run/lecturer/classroom |
| GET | `/api/schedule/loading` | Lecturer weekly loading heatmap data |
| POST | `/api/schedule/confirm` | Confirm all proposals for an academic year |

### Solver
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/solver/run` | Start solver (returns `job_id`) |
| GET | `/api/solver/status/<job_id>` | Poll solver progress |

## Configuration

Key settings in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `SLOTS_PER_DAY` | 8 | Teaching slots per day (09:00-17:00) |
| `DAYS_PER_WEEK` | 5 | Monday to Friday |
| `SOLVER_TIMEOUT_SECONDS` | 120 | Max solver runtime |
| `YEAR_START_MONTH` | 9 | Academic year starts September |
| `YEAR_END_MONTH` | 7 | Academic year ends July |

## License

MIT
