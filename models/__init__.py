from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()
engine = None
Session = None


def init_db(database_uri):
    global engine, Session
    engine = create_engine(database_uri, echo=False)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    return engine


def get_session():
    return Session()


from models.lecturer import Lecturer, LecturerAvailability
from models.course import Course, Module, CourseRun, AcademicYear
from models.classroom import Classroom, ClassroomAvailability
from models.qualification import LecturerQualification
from models.schedule import ScheduledSession
from models.resit import Resit
from models.rule import Rule
