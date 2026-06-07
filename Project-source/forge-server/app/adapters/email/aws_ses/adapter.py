"""AWS SES email (boto3 ses client, lazy-imported)."""

from __future__ import annotations

import asyncio

from app.adapters.email.base import EmailAdapter, EmailMessage


class AwsSesEmail(EmailAdapter):
    def _client(self):
        import boto3
        s = self.settings
        return boto3.client(
            "ses",
            region_name=s.EMAIL_REGION or None,
            aws_access_key_id=s.EMAIL_ACCESS_KEY or None,
            aws_secret_access_key=s.EMAIL_SECRET_KEY or None,
        )

    async def send(self, msg: EmailMessage) -> None:
        def _do():
            self._client().send_email(
                Source=self.from_header,
                Destination={"ToAddresses": msg.to, "CcAddresses": msg.cc},
                Message={
                    "Subject": {"Data": msg.subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": msg.text, "Charset": "UTF-8"},
                        "Html": {"Data": msg.html, "Charset": "UTF-8"},
                    },
                },
                ReplyToAddresses=[msg.reply_to or self.settings.EMAIL_REPLY_TO],
            )
        await asyncio.to_thread(_do)
