from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()
engine = None
Session = None


def init_db(database_uri):
    global engine, Session
    engine = create_engine(database_uri, echo=False)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    _migrate(engine)
    return engine


def _migrate(eng):
    """Add columns that may be missing from older databases."""
    inspector = inspect(eng)

    migrations = {
        'modules': {
            'delivery_mode': "ALTER TABLE modules ADD COLUMN delivery_mode VARCHAR(20) DEFAULT 'single'",
            'team_size': "ALTER TABLE modules ADD COLUMN team_size INTEGER DEFAULT 1",
            'split_count': "ALTER TABLE modules ADD COLUMN split_count INTEGER DEFAULT 1",
            'min_segment_hours': "ALTER TABLE modules ADD COLUMN min_segment_hours INTEGER",
        },
        'scheduled_sessions': {
            'secondary_lecturer_id': "ALTER TABLE scheduled_sessions ADD COLUMN secondary_lecturer_id INTEGER REFERENCES lecturers(id)",
            'split_segment': "ALTER TABLE scheduled_sessions ADD COLUMN split_segment INTEGER",
        },
    }

    with eng.begin() as conn:
        for table, columns in migrations.items():
            if not inspector.has_table(table):
                continue
            existing = {c['name'] for c in inspector.get_columns(table)}
            for col_name, sql in columns.items():
                if col_name not in existing:
                    try:
                        conn.execute(text(sql))
                    except Exception:
                        pass  # column may already exist


def get_session():
    return Session()


from models.lecturer import Lecturer, LecturerAvailability
from models.course import Course, Module, ModuleRule, CourseRun, AcademicYear
from models.classroom import Classroom, ClassroomAvailability
from models.qualification import LecturerQualification
from models.schedule import ScheduledSession
from models.resit import Resit
from models.rule import Rule
