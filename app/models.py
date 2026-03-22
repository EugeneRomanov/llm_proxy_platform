import time
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class Provider(Base):
    __tablename__ = "providers"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    url = Column(String)
    priority = Column(Integer, default=1)
    latency_ema = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    
    # Новые поля для Level 2
    price_per_1k_input_tokens = Column(Float, default=0.0)
    price_per_1k_output_tokens = Column(Float, default=0.0)
    rate_limit_rpm = Column(Integer, default=60)
    rate_limit_tpm = Column(Integer, default=100000)
    timeout_seconds = Column(Integer, default=60)
    
    # Для health-aware routing
    consecutive_errors = Column(Integer, default=0)
    last_error_time = Column(Integer, default=0)
    blocked_until = Column(Integer, default=0)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "priority": self.priority,
            "latency_ema": self.latency_ema,
            "is_active": self.is_active,
            "price_per_1k_input_tokens": self.price_per_1k_input_tokens,
            "price_per_1k_output_tokens": self.price_per_1k_output_tokens,
            "rate_limit_rpm": self.rate_limit_rpm,
            "timeout_seconds": self.timeout_seconds
        }

class AgentCard(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)
    supported_methods = Column(String, default="chat.completions")
    endpoint = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(Integer, default=lambda: int(time.time()))
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "supported_methods": self.supported_methods.split(",") if self.supported_methods else [],
            "endpoint": self.endpoint,
            "is_active": self.is_active,
            "created_at": self.created_at
        }

engine = create_engine(
    "sqlite:///./platform.db",
    connect_args={"check_same_thread": False, "timeout": 30}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)