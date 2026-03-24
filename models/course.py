from sqlalchemy import Column, Integer, String, Boolean, Date, ForeignKey
from sqlalchemy.orm import relationship
from models import Base


class AcademicYear(Base):
    __tablename__ = 'academic_years'

    id = Column(Integer, primary_key=True)
    label = Column(String(20), nullable=False, unique=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    course_runs = relationship('CourseRun', back_populates='academic_year')

    def to_dict(self):
        return {
            'id': self.id,
            'label': self.label,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
        }


class Course(Base):
    __tablename__ = 'courses'

    id = Column(Integer, primary_key=True)
    code = Column(String(20), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    description = Column(String(500))
    total_weeks = Column(Integer, nullable=False)
    max_concurrent_runs = Column(Integer, default=2)

    modules = relationship('Module', back_populates='course', order_by='Module.sequence_order')
    course_runs = relationship('CourseRun', back_populates='course')

    def to_dict(self, include_modules=False):
        d = {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'description': self.description,
            'total_weeks': self.total_weeks,
            'max_concurrent_runs': self.max_concurrent_runs,
            'module_count': len(self.modules) if self.modules else 0,
        }
        if include_modules:
            d['modules'] = [m.to_dict() for m in self.modules]
        return d


class Module(Base):
    __tablename__ = 'modules'

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    code = Column(String(20), nullable=False)
    name = Column(String(200), nullable=False)
    duration_hours = Column(Integer, nullable=False)
    sequence_order = Column(Integer, nullable=False)
    requires_lab = Column(Boolean, default=False)
    max_class_size = Column(Integer, default=30)
    exam_duration_hours = Column(Integer, nullable=True)

    course = relationship('Course', back_populates='modules')
    qualifications = relationship('LecturerQualification', back_populates='module')

    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'code': self.code,
            'name': self.name,
            'duration_hours': self.duration_hours,
            'sequence_order': self.sequence_order,
            'requires_lab': self.requires_lab,
            'max_class_size': self.max_class_size,
            'exam_duration_hours': self.exam_duration_hours,
        }


class CourseRun(Base):
    __tablename__ = 'course_runs'

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    academic_year_id = Column(Integer, ForeignKey('academic_years.id'), nullable=False)
    cohort_label = Column(String(50), nullable=False)
    planned_start_date = Column(Date, nullable=False)
    planned_end_date = Column(Date, nullable=False)
    student_count = Column(Integer, default=20)
    status = Column(String(20), default='draft')

    course = relationship('Course', back_populates='course_runs')
    academic_year = relationship('AcademicYear', back_populates='course_runs')
    scheduled_sessions = relationship('ScheduledSession', back_populates='course_run')
    resits = relationship('Resit', back_populates='course_run')

    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'course_name': self.course.name if self.course else None,
            'course_code': self.course.code if self.course else None,
            'academic_year_id': self.academic_year_id,
            'cohort_label': self.cohort_label,
            'planned_start_date': self.planned_start_date.isoformat(),
            'planned_end_date': self.planned_end_date.isoformat(),
            'student_count': self.student_count,
            'status': self.status,
        }
