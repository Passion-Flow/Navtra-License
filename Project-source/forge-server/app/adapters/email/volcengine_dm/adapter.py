"""Volcengine DirectMail (邮件推送) via the volcengine signed OpenAPI SDK (lazy-imported).

Requires: pip install volcengine
Uses the generic Service signer; the SendEmail action/version follow Volcengine Email Push.
EMAIL_FROM_ADDRESS must be a verified Volcengine DM sender.
"""

from __future__ import annotations

import asyncio
import json

from app.adapters.email.base import EmailAdapter, EmailMessage

_SERVICE = "volc_email"
_VERSION = "2021-01-01"
_HOST = "open.volcengineapi.com"


class VolcengineDmEmail(EmailAdapter):
    async def send(self, msg: EmailMessage) -> None:
        def _do():
            from volcengine.base.Service import Service
            from volcengine.ServiceInfo import ServiceInfo
            from volcengine.ApiInfo import ApiInfo
            from volcengine.Credentials import Credentials

            s = self.settings
            region = s.EMAIL_REGION or "cn-north-1"
            svc_info = ServiceInfo(
                _HOST, {"Accept": "application/json"},
                Credentials(s.EMAIL_ACCESS_KEY, s.EMAIL_SECRET_KEY, _SERVICE, region),
                10, 10, "https",
            )
            api_info = {
                "SendEmail": ApiInfo("POST", "/", {"Action": "SendEmail", "Version": _VERSION}, {}, {}),
            }
            service = Service(svc_info, api_info)
            body = {
                "FromEmail": self.from_address,
                "FromName": self.from_name,
                "ReplyTo": msg.reply_to or s.EMAIL_REPLY_TO,
                "To": msg.to + msg.cc,
                "Subject": msg.subject,
                "Html": msg.html,
                "Text": msg.text,
            }
            resp = service.json("SendEmail", {}, json.dumps(body))
            if isinstance(resp, (bytes, str)):
                parsed = json.loads(resp)
                if parsed.get("ResponseMetadata", {}).get("Error"):
                    raise RuntimeError(f"volcengine dm error: {parsed['ResponseMetadata']['Error']}")
        await asyncio.to_thread(_do)
