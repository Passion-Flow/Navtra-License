"""Aliyun DirectMail (DM) — Alibaba Cloud SDK v2 `alibabacloud_dm20151123` (Python 3).

The classic `aliyun-python-sdk-dm` is Python-2-only, so Python-3 deployments must use the v2 SDK.
The sender address (EMAIL_FROM_ADDRESS) must be a verified DM sender account. xinchuang.md §5.
"""

from __future__ import annotations

import asyncio

from app.adapters.email.base import EmailAdapter, EmailMessage


class AliyunDmEmail(EmailAdapter):
    def _client(self):
        from alibabacloud_dm20151123.client import Client
        from alibabacloud_tea_openapi import models as open_api_models

        s = self.settings
        config = open_api_models.Config(
            access_key_id=s.EMAIL_ACCESS_KEY,
            access_key_secret=s.EMAIL_SECRET_KEY,
            region_id=s.EMAIL_REGION or "cn-hangzhou",
        )
        config.endpoint = f"dm.{s.EMAIL_REGION}.aliyuncs.com" if s.EMAIL_REGION else "dm.aliyuncs.com"
        return Client(config)

    async def send(self, msg: EmailMessage) -> None:
        def _do():
            from alibabacloud_dm20151123 import models as dm_models

            req = dm_models.SingleSendMailRequest(
                account_name=self.from_address,
                from_alias=self.from_name,
                address_type=1,            # 1 = sender address from the DM console
                reply_to_address=True,
                to_address=",".join(msg.to + msg.cc),
                subject=msg.subject,
                html_body=msg.html,
                text_body=msg.text,
            )
            self._client().single_send_mail(req)
        await asyncio.to_thread(_do)
