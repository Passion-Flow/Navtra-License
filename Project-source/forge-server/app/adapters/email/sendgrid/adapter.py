"""SendGrid email via its v3 REST API (httpx async; no extra SDK dependency)."""

from __future__ import annotations

from app.adapters.email.base import EmailAdapter, EmailMessage

_API = "https://api.sendgrid.com/v3/mail/send"


class SendGridEmail(EmailAdapter):
    async def send(self, msg: EmailMessage) -> None:
        import httpx

        payload = {
            "personalizations": [{
                "to": [{"email": a} for a in msg.to],
                **({"cc": [{"email": a} for a in msg.cc]} if msg.cc else {}),
                "subject": msg.subject,
            }],
            "from": {"email": self.from_address, "name": self.from_name},
            "reply_to": {"email": msg.reply_to or self.settings.EMAIL_REPLY_TO},
            "content": [
                {"type": "text/plain", "value": msg.text},
                {"type": "text/html", "value": msg.html},
            ],
        }
        headers = {"Authorization": f"Bearer {self.settings.EMAIL_API_KEY}",
                   "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(_API, json=payload, headers=headers)
            if r.status_code >= 300:
                raise RuntimeError(f"sendgrid send failed: {r.status_code} {r.text}")
