import uuid

from sqlalchemy import Column, Text, Integer, Boolean, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    slug = Column(Text, unique=True, nullable=False)
    plan = Column(Text, nullable=False, default="free")
    max_workflows = Column(Integer, nullable=False, default=2)
    max_agents_per_workflow = Column(Integer, nullable=False, default=3)
    monthly_token_budget = Column(Integer, nullable=False, default=100000)
    tokens_used_this_month = Column(Integer, nullable=False, default=0)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
