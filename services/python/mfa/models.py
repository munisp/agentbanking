from sqlalchemy import Column, String, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class MFASetting(Base):
    __tablename__ = "mfa_settings"

    user_id = Column(String, primary_key=True, index=True)
    mfa_enabled = Column(Boolean, default=False)
    mfa_type = Column(String, nullable=True)
    mfa_secret = Column(String, nullable=True)

    def __repr__(self):
        return f"<MFASetting(user_id='{self.user_id}', mfa_enabled={self.mfa_enabled}, mfa_type='{self.mfa_type}')>"

