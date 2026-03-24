from sqlalchemy import Column, Integer, String, Boolean, Date, ForeignKey
from sqlalchemy.orm import relationship
from models import Base


class ScheduledSession(Base):
    __tablename__ = 'scheduled_sessions'

    id = Column(Integer, primary_key=True)
    course_run_id = Column(Integer, ForeignKey('course_runs.id'), nullable=False)
    module_id = Column(Integer, ForeignKey('modules.id'), nullable=False)
    lecturer_id = Column(Integer, ForeignKey('lecturers.id'), nullable=False)
    classroom_id = Column(Integer, ForeignKey('classrooms.id'), nullable=False)
    date = Column(Date, nullable=False)
    start_slot = Column(Integer, nullable=False)  # 0-7 for 09:00-17:00
    duration_slots = Column(Integer, nullable=False, default=1)
    session_type = Column(String(20), default='lecture')  # lecture, lab, exam, resit, prep, marking
    is_proposal = Column(Boolean, default=True)

    # For team teaching: optional second (or more) lecturer
    secondary_lecturer_id = Column(Integer, ForeignKey('lecturers.id'), nullable=True)
    # For split/handover tracking: which segment of the split this is (1, 2, ...)
    split_segment = Column(Integer, nullable=True)

    course_run = relationship('CourseRun', back_populates='scheduled_sessions')
    module = relationship('Module')
    lecturer = relationship('Lecturer', foreign_keys=[lecturer_id], back_populates='scheduled_sessions')
    secondary_lecturer = relationship('Lecturer', foreign_keys=[secondary_lecturer_id])
    classroom = relationship('Classroom', back_populates='scheduled_sessions')

    def to_dict(self):
        return {
            'id': self.id,
            'course_run_id': self.course_run_id,
            'module_id': self.module_id,
            'module_name': self.module.name if self.module else None,
            'module_code': self.module.code if self.module else None,
            'lecturer_id': self.lecturer_id,
            'lecturer_name': self.lecturer.name if self.lecturer else None,
            'secondary_lecturer_id': self.secondary_lecturer_id,
            'secondary_lecturer_name': self.secondary_lecturer.name if self.secondary_lecturer else None,
            'classroom_id': self.classroom_id,
            'classroom_name': self.classroom.name if self.classroom else None,
            'course_name': self.course_run.course.name if self.course_run and self.course_run.course else None,
            'course_code': self.course_run.course.code if self.course_run and self.course_run.course else None,
            'cohort_label': self.course_run.cohort_label if self.course_run else None,
            'date': self.date.isoformat(),
            'start_slot': self.start_slot,
            'duration_slots': self.duration_slots,
            'session_type': self.session_type,
            'is_proposal': self.is_proposal,
            'split_segment': self.split_segment,
        }
