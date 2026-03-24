from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from models import Base


class LecturerQualification(Base):
    __tablename__ = 'lecturer_qualifications'
    __table_args__ = (
        UniqueConstraint('lecturer_id', 'module_id', name='uq_lecturer_module'),
    )

    id = Column(Integer, primary_key=True)
    lecturer_id = Column(Integer, ForeignKey('lecturers.id'), nullable=False)
    module_id = Column(Integer, ForeignKey('modules.id'), nullable=False)
    proficiency_level = Column(String(20), default='primary')  # primary, secondary, emergency
    can_examine = Column(Boolean, default=True)

    lecturer = relationship('Lecturer', back_populates='qualifications')
    module = relationship('Module', back_populates='qualifications')

    def to_dict(self):
        return {
            'id': self.id,
            'lecturer_id': self.lecturer_id,
            'lecturer_name': self.lecturer.name if self.lecturer else None,
            'module_id': self.module_id,
            'module_name': self.module.name if self.module else None,
            'proficiency_level': self.proficiency_level,
            'can_examine': self.can_examine,
        }
