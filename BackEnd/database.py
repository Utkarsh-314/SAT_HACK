
import os

from dotenv import load_dotenv

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    func,
    JSON
)

from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing from .env")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


# USERS TABLE
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    user_id = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    disabilities = Column(
    JSON,
    nullable=True,
    default=list
)

    created_at = Column(
        DateTime,
        server_default=func.now()
    )


# REVOKED TOKENS TABLE
class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti = Column(String(100), primary_key=True)
    expires_at = Column(DateTime, nullable=False)


# MEETINGS TABLE
class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)

    meeting_code = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True
    )

    meeting_name = Column(String(100), nullable=False)

    description = Column(Text, nullable=True)

    host_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at = Column(
        DateTime,
        server_default=func.now()
    )


# DATABASE SESSION
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# CREATE TABLES
def create_tables():
    Base.metadata.create_all(bind=engine)
