from sqlalchemy import Column, Integer, String, Float, Boolean, Date, ForeignKey
from sqlalchemy.orm import relationship
from models import Base


class Lecturer(Base):
    __tablename__ = 'lecturers'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150))
    max_weekly_hours = Column(Integer, default=25)
    max_consecutive_days = Column(Integer, default=5)
    prep_time_hours = Column(Float, default=4.0)
    marking_hours_per_student = Column(Float, default=0.5)
    wind_down_hours = Column(Float, default=2.0)

    qualifications = relationship('LecturerQualification', back_populates='lecturer')
    availability = relationship('LecturerAvailability', back_populates='lecturer')
    scheduled_sessions = relationship('ScheduledSession', back_populates='lecturer')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'max_weekly_hours': self.max_weekly_hours,
            'max_consecutive_days': self.max_consecutive_days,
            'prep_time_hours': self.prep_time_hours,
            'marking_hours_per_student': self.marking_hours_per_student,
            'wind_down_hours': self.wind_down_hours,
        }


class LecturerAvailability(Base):
    __tablename__ = 'lecturer_availability'

    id = Column(Integer, primary_key=True)
    lecturer_id = Column(Integer, ForeignKey('lecturers.id'), nullable=False)
    date = Column(Date, nullable=False)
    available = Column(Boolean, default=True)
    reason = Column(String(200))

    lecturer = relationship('Lecturer', back_populates='availability')
