"""Email adapter interface — business code stays SDK-free; every provider implements this
(HARD RULE 03-Services: all 6 providers ship adapters). Provider chosen via EMAIL_TYPE.

A primary→fallback failover wrapper (circuit breaker) is layered on top so a flaky primary
degrades to the configured EMAIL_FALLBACK_TYPE instead of dropping expiry reminders.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.settings import AppSettings


@dataclass
class EmailMessage:
    to: list[str]
    subject: str
    html: str
    text: str
    reply_to: str | None = None
    cc: list[str] = field(default_factory=list)


class EmailAdapter(ABC):
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    @property
    def from_name(self) -> str:
        return self.settings.EMAIL_FROM_NAME

    @property
    def from_address(self) -> str:
        return self.settings.EMAIL_FROM_ADDRESS

    @property
    def from_header(self) -> str:
        return f"{self.from_name} <{self.from_address}>"

    @abstractmethod
    async def send(self, msg: EmailMessage) -> None: ...

    async def health_check(self) -> bool:
        return True


class FailoverEmailService(EmailAdapter):
    """Tries the primary; after `threshold` consecutive failures the breaker OPENs and traffic
    routes to the fallback. A single later success on the primary closes it again."""

    def __init__(self, primary: EmailAdapter, fallback: EmailAdapter, threshold: int) -> None:
        super().__init__(primary.settings)
        self.primary = primary
        self.fallback = fallback
        self.threshold = max(1, threshold)
        self._consecutive_failures = 0

    @property
    def _open(self) -> bool:
        return self._consecutive_failures >= self.threshold

    async def send(self, msg: EmailMessage) -> None:
        if self._open:
            await self.fallback.send(msg)
            return
        try:
            await self.primary.send(msg)
            self._consecutive_failures = 0
        except Exception:
            self._consecutive_failures += 1
            # Don't lose this message: immediately retry via the fallback.
            await self.fallback.send(msg)


def get_email_adapter(settings: AppSettings, type_: str | None = None) -> EmailAdapter:
    t = type_ or settings.EMAIL_TYPE
    if t == "smtp":
        from app.adapters.email.smtp.adapter import SMTPEmail
        return SMTPEmail(settings)
    if t == "aws_ses":
        from app.adapters.email.aws_ses.adapter import AwsSesEmail
        return AwsSesEmail(settings)
    if t == "sendgrid":
        from app.adapters.email.sendgrid.adapter import SendGridEmail
        return SendGridEmail(settings)
    if t == "aliyun_dm":
        from app.adapters.email.aliyun_dm.adapter import AliyunDmEmail
        return AliyunDmEmail(settings)
    if t == "tencent_ses":
        from app.adapters.email.tencent_ses.adapter import TencentSesEmail
        return TencentSesEmail(settings)
    if t == "volcengine_dm":
        from app.adapters.email.volcengine_dm.adapter import VolcengineDmEmail
        return VolcengineDmEmail(settings)
    raise ValueError(f"unknown EMAIL_TYPE: {t}")


def get_email_service(settings: AppSettings) -> EmailAdapter:
    """Production entrypoint: primary adapter, optionally wrapped with failover."""
    primary = get_email_adapter(settings)
    if settings.EMAIL_FALLBACK_TYPE and settings.EMAIL_FALLBACK_TYPE != settings.EMAIL_TYPE:
        fallback = get_email_adapter(settings, settings.EMAIL_FALLBACK_TYPE)
        return FailoverEmailService(primary, fallback, settings.EMAIL_FAILOVER_THRESHOLD)
    return primary
