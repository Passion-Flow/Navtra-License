from app.adapters.email.base import (
    EmailAdapter,
    EmailMessage,
    FailoverEmailService,
    get_email_adapter,
    get_email_service,
)

__all__ = [
    "EmailAdapter", "EmailMessage", "FailoverEmailService",
    "get_email_adapter", "get_email_service",
]
