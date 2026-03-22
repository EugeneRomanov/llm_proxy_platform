from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.models import SessionLocal, AgentCard

router = APIRouter(prefix="/agents", tags=["agents"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register")
async def register_agent(
    name: str,
    description: str = "",
    supported_methods: str = "chat.completions",
    endpoint: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Регистрация нового A2A агента"""
    existing = db.query(AgentCard).filter(AgentCard.name == name).first()
    if existing:
        existing.description = description
        existing.supported_methods = supported_methods
        existing.endpoint = endpoint
        existing.is_active = True
        db.commit()
        return {"status": "updated", "agent": existing.to_dict()}
    
    agent = AgentCard(
        name=name,
        description=description,
        supported_methods=supported_methods,
        endpoint=endpoint
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return {"status": "registered", "agent": agent.to_dict()}

@router.get("/list")
async def list_agents(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """Получение списка всех агентов"""
    query = db.query(AgentCard)
    if active_only:
        query = query.filter(AgentCard.is_active == True)
    
    agents = query.all()
    return {"agents": [agent.to_dict() for agent in agents]}

@router.get("/{agent_id}")
async def get_agent(
    agent_id: int,
    db: Session = Depends(get_db)
):
    """Получение карточки конкретного агента"""
    agent = db.query(AgentCard).filter(AgentCard.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.to_dict()

@router.delete("/{agent_id}")
async def unregister_agent(
    agent_id: int,
    soft_delete: bool = True,
    db: Session = Depends(get_db)
):
    """Удаление/деактивация агента"""
    agent = db.query(AgentCard).filter(AgentCard.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if soft_delete:
        agent.is_active = False
        db.commit()
        return {"status": "deactivated", "agent_id": agent_id}
    else:
        db.delete(agent)
        db.commit()
        return {"status": "deleted", "agent_id": agent_id}