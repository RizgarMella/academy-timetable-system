from sqlalchemy import Column, Integer, String, Boolean, Date, ForeignKey
from sqlalchemy.orm import relationship
from models import Base


class Classroom(Base):
    __tablename__ = 'classrooms'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    building = Column(String(100))
    capacity = Column(Integer, nullable=False)
    has_lab_equipment = Column(Boolean, default=False)
    has_projector = Column(Boolean, default=True)

    availability = relationship('ClassroomAvailability', back_populates='classroom')
    scheduled_sessions = relationship('ScheduledSession', back_populates='classroom')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'building': self.building,
            'capacity': self.capacity,
            'has_lab_equipment': self.has_lab_equipment,
            'has_projector': self.has_projector,
        }


class ClassroomAvailability(Base):
    __tablename__ = 'classroom_availability'

    id = Column(Integer, primary_key=True)
    classroom_id = Column(Integer, ForeignKey('classrooms.id'), nullable=False)
    date = Column(Date, nullable=False)
    available = Column(Boolean, default=True)
    reason = Column(String(200))

    classroom = relationship('Classroom', back_populates='availability')
