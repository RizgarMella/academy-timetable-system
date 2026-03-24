from sqlalchemy import Column, Integer, String, Boolean
from models import Base


class Rule(Base):
    __tablename__ = 'rules'

    id = Column(Integer, primary_key=True)
    key = Column(String(50), nullable=False, unique=True)
    value = Column(String(500), default='true')
    description = Column(String(300))
    enabled = Column(Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'description': self.description,
            'enabled': self.enabled,
        }
