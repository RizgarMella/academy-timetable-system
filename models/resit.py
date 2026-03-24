from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from models import Base


class Resit(Base):
    __tablename__ = 'resits'

    id = Column(Integer, primary_key=True)
    course_run_id = Column(Integer, ForeignKey('course_runs.id'), nullable=False)
    module_id = Column(Integer, ForeignKey('modules.id'), nullable=False)
    student_name = Column(String(100), nullable=False)
    required_by_date = Column(Date, nullable=False)
    original_lecturer_id = Column(Integer, ForeignKey('lecturers.id'), nullable=False)
    examiner_id = Column(Integer, ForeignKey('lecturers.id'), nullable=True)
    scheduled_session_id = Column(Integer, ForeignKey('scheduled_sessions.id'), nullable=True)
    status = Column(String(20), default='pending')  # pending, scheduled, completed

    course_run = relationship('CourseRun', back_populates='resits')
    module = relationship('Module')
    original_lecturer = relationship('Lecturer', foreign_keys=[original_lecturer_id])
    examiner = relationship('Lecturer', foreign_keys=[examiner_id])
    scheduled_session = relationship('ScheduledSession')

    def to_dict(self):
        return {
            'id': self.id,
            'course_run_id': self.course_run_id,
            'module_id': self.module_id,
            'module_name': self.module.name if self.module else None,
            'student_name': self.student_name,
            'required_by_date': self.required_by_date.isoformat(),
            'original_lecturer_id': self.original_lecturer_id,
            'original_lecturer_name': self.original_lecturer.name if self.original_lecturer else None,
            'examiner_id': self.examiner_id,
            'examiner_name': self.examiner.name if self.examiner else None,
            'status': self.status,
        }
