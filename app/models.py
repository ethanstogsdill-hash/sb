from pydantic import BaseModel


class AgentUpdate(BaseModel):
    real_name: str


class PaymentLink(BaseModel):
    linked_agent_id: int | None = None
    match_status: str = "matched"


class ScrapeStatus(BaseModel):
    status: str
    message: str = ""
    last_run: str | None = None
    records_affected: int = 0


class DashboardSummary(BaseModel):
    total_agents: int = 0
    total_action: float = 0
    net_win_loss: float = 0
    unmatched_payments: int = 0
