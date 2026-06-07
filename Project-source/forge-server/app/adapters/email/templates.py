"""Bilingual (zh-CN + en) email templates — HTML + plain text (03-Services §2.4).

Templates are provider-agnostic; an adapter only transports the rendered EmailMessage.
The license-expiry reminder is rendered in the recipient's language, falling back to a
stacked bilingual body when the language is unknown.
"""

from __future__ import annotations

from app.adapters.email.base import EmailMessage

# ctx keys: customer, product, days_left, expiry_date, license_id
_EXPIRY = {
    "zh-CN": {
        "subject": "【Forge】许可证将于 {days_left} 天后到期 · {product}",
        "html": (
            "<div style=\"font-family:system-ui,Arial;color:#18181b\">"
            "<h2 style=\"margin:0 0 12px\">许可证到期提醒</h2>"
            "<p>尊敬的 {customer}：</p>"
            "<p>您的产品 <b>{product}</b> 许可证将于 <b>{expiry_date}</b> 到期"
            "（剩余 <b>{days_left}</b> 天）。请及时联系我们续期，以免服务中断。</p>"
            "<p style=\"color:#71717a;font-size:13px\">License ID: {license_id}</p>"
            "</div>"
        ),
        "text": (
            "许可证到期提醒\n\n尊敬的 {customer}：\n\n"
            "您的产品 {product} 许可证将于 {expiry_date} 到期（剩余 {days_left} 天）。\n"
            "请及时联系我们续期，以免服务中断。\n\nLicense ID: {license_id}\n"
        ),
    },
    "en": {
        "subject": "[Forge] License expires in {days_left} days · {product}",
        "html": (
            "<div style=\"font-family:system-ui,Arial;color:#18181b\">"
            "<h2 style=\"margin:0 0 12px\">License expiry reminder</h2>"
            "<p>Dear {customer},</p>"
            "<p>Your license for <b>{product}</b> will expire on <b>{expiry_date}</b> "
            "(<b>{days_left}</b> days left). Please contact us to renew before service is interrupted.</p>"
            "<p style=\"color:#71717a;font-size:13px\">License ID: {license_id}</p>"
            "</div>"
        ),
        "text": (
            "License expiry reminder\n\nDear {customer},\n\n"
            "Your license for {product} will expire on {expiry_date} ({days_left} days left).\n"
            "Please contact us to renew before service is interrupted.\n\nLicense ID: {license_id}\n"
        ),
    },
}


def render_expiry_reminder(to: list[str], ctx: dict, lang: str | None = None,
                           reply_to: str | None = None) -> EmailMessage:
    langs = [lang] if lang in _EXPIRY else ["zh-CN", "en"]  # unknown -> stacked bilingual
    subject = _EXPIRY[langs[0]]["subject"].format(**ctx)
    html = "<hr/>".join(_EXPIRY[lg]["html"].format(**ctx) for lg in langs)
    text = "\n\n----\n\n".join(_EXPIRY[lg]["text"].format(**ctx) for lg in langs)
    return EmailMessage(to=to, subject=subject, html=html, text=text, reply_to=reply_to)
