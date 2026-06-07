"""Tencent Cloud SES — official tencentcloud-sdk-python (lazy-imported).

Requires: pip install tencentcloud-sdk-python-ses
Uses Simple content (base64 Html/Text). A registered sending domain is required by SES.
"""

from __future__ import annotations

import asyncio
import base64

from app.adapters.email.base import EmailAdapter, EmailMessage


class TencentSesEmail(EmailAdapter):
    async def send(self, msg: EmailMessage) -> None:
        def _do():
            from tencentcloud.common import credential
            from tencentcloud.ses.v20201002 import models, ses_client

            s = self.settings
            # Tencent-specific creds win; otherwise fall back to the generic EMAIL_ACCESS_KEY/SECRET_KEY
            # so the unified deployment env (helm/compose) works for every cloud-email provider.
            cred = credential.Credential(
                s.EMAIL_TENCENT_SECRET_ID or s.EMAIL_ACCESS_KEY,
                s.EMAIL_TENCENT_SECRET_KEY or s.EMAIL_SECRET_KEY,
            )
            client = ses_client.SesClient(cred, s.EMAIL_REGION or "ap-hongkong")
            req = models.SendEmailRequest()
            req.FromEmailAddress = self.from_header
            req.Destination = msg.to + msg.cc
            req.Subject = msg.subject
            req.ReplyToAddresses = msg.reply_to or s.EMAIL_REPLY_TO
            b64 = lambda v: base64.b64encode(v.encode("utf-8")).decode("ascii")  # noqa: E731
            req.Simple = models.Simple()
            req.Simple.Html = b64(msg.html)
            req.Simple.Text = b64(msg.text)
            client.SendEmail(req)
        await asyncio.to_thread(_do)
