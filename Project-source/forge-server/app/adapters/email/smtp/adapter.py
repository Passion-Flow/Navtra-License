"""SMTP email (default; dev = MailHog). Stdlib smtplib off-loaded to a thread."""

from __future__ import annotations

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.adapters.email.base import EmailAdapter, EmailMessage


class SMTPEmail(EmailAdapter):
    async def send(self, msg: EmailMessage) -> None:
        def _do():
            mime = MIMEMultipart("alternative")
            mime["Subject"] = msg.subject
            mime["From"] = self.from_header
            mime["To"] = ", ".join(msg.to)
            if msg.cc:
                mime["Cc"] = ", ".join(msg.cc)
            mime["Reply-To"] = msg.reply_to or self.settings.EMAIL_REPLY_TO
            mime.attach(MIMEText(msg.text, "plain", "utf-8"))
            mime.attach(MIMEText(msg.html, "html", "utf-8"))

            s = self.settings
            with smtplib.SMTP(s.EMAIL_HOST, s.EMAIL_PORT, timeout=15) as server:
                if s.EMAIL_USE_TLS:
                    server.starttls()
                if s.EMAIL_USERNAME:
                    server.login(s.EMAIL_USERNAME, s.EMAIL_PASSWORD)
                server.sendmail(self.from_address, msg.to + msg.cc, mime.as_string())
        await asyncio.to_thread(_do)
