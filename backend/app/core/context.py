from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    ip_address: str | None
    user_agent: str | None


# Set by the request middleware; read by the audit log.
request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)
