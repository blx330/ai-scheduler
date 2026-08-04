from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    demo_mode: bool = False


class MessageResponse(BaseModel):
    message: str
