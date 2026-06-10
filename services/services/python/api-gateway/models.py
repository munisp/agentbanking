from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, index=True)
    
    # Core Routing Information
    service_name = Column(String, index=True, nullable=False, unique=True)
    source_path_prefix = Column(String, index=True, nullable=False, unique=True)
    target_url = Column(String, nullable=False)
    
    # Status and Metadata
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Security and Policy
    auth_required = Column(Boolean, default=False, nullable=False)
    rate_limit_per_minute = Column(Integer, default=0, nullable=False) # 0 means no rate limit
    
    # Advanced Configuration (e.g., headers to add, timeouts, etc.)
    config = Column(JSON, default={}, nullable=False)

    def __repr__(self):
        return f"<Route(service_name='{self.service_name}', source_path_prefix='{self.source_path_prefix}')>"