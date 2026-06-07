"""Permission registry — central P.* constants (HARD RULE: rbac.md).

Naming: <domain>.<resource>.<action>, lowercase, dot-separated, singular resource.
Business code references P.* constants only — never bare permission strings.
Startup self-check asserts every decorator-referenced permission is registered.
"""

from __future__ import annotations


class P:
    # platform.license.*
    LICENSE_READ = "platform.license.read"
    LICENSE_ISSUE = "platform.license.issue"
    LICENSE_UPDATE = "platform.license.update"   # renew / replace
    LICENSE_REVOKE = "platform.license.revoke"
    LICENSE_DELETE = "platform.license.delete"

    # platform.product.* / platform.customer.*
    PRODUCT_READ = "platform.product.read"
    PRODUCT_WRITE = "platform.product.write"
    PRODUCT_DELETE = "platform.product.delete"
    CUSTOMER_READ = "platform.customer.read"
    CUSTOMER_WRITE = "platform.customer.write"
    CUSTOMER_DELETE = "platform.customer.delete"

    # platform.user.* (operator management)
    USER_READ = "platform.user.read"
    USER_WRITE = "platform.user.write"
    USER_DELETE = "platform.user.delete"

    # platform.audit.*
    AUDIT_READ = "platform.audit.read"
    AUDIT_EXPORT = "platform.audit.export"

    # system.* (keys + settings)
    KEY_READ = "system.key.read"
    KEY_MANAGE = "system.key.manage"        # rotate / export public
    SETTINGS_READ = "system.settings.read"
    SETTINGS_WRITE = "system.settings.write"
    CRL_GENERATE = "platform.crl.generate"


ALL_PERMISSIONS: set[str] = {
    v for k, v in vars(P).items() if not k.startswith("_") and isinstance(v, str)
}
