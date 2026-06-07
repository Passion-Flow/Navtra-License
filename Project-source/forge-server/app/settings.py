"""Forge runtime configuration — Pydantic Settings, env field-ized (no connection strings).

HARD RULE (Project-Docs/02-Backend/tech-stack.md, 03-Services/overview.md):
connection-strings are forbidden; every service is described by discrete
<SERVICE>_TYPE / HOST / PORT / USERNAME / PASSWORD / DATABASE fields. The adapter
layer assembles the SDK-specific connection from these fields.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)

    # ---- runtime role: which process this is ----------------------------------
    # api = signing core + admin backend (holds private key, internal-only)
    # edge = public validation relay (NO private key)
    # worker / scheduler = celery
    APP_ROLE: Literal["api", "edge", "worker", "scheduler"] = "api"
    APP_ENV: str = "production"
    APP_NAME: str = "forge"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8080
    APP_DEBUG: bool = False
    APP_BASE_URL: str = "http://localhost:13001"
    APP_EDGE_BASE_URL: str = "http://localhost:13002"

    # ---- i18n ----------------------------------------------------------------
    DEFAULT_LANG: str = "zh-CN"
    SUPPORTED_LANGS: str = "zh-CN,en"

    # ---- Database (field-ized; provider via DATABASE_TYPE) -------------------
    # 信创 additions: opengauss/kingbase reuse PG wire (asyncpg); oceanbase/polardb-x reuse
    # MySQL wire (aiomysql); polardb-pg is 100% PG. (达梦 DM8 is sync-only → needs the planned
    # sync-session bridge before it can join this async-engine set; tracked in xinchuang.md §2.)
    DATABASE_TYPE: Literal[
        "postgres", "mysql", "oracle", "tidb",
        "opengauss", "kingbase", "oceanbase", "polardb-pg", "polardb-x", "dameng",
    ] = "postgres"
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 15432
    DATABASE_USERNAME: str = "forge_app"
    DATABASE_PASSWORD: str = "change-me"
    DATABASE_NAME: str = "forge_main"
    DATABASE_SSL_MODE: str = "prefer"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_POOL_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_ECHO: bool = False
    # oracle-specific
    DATABASE_ORACLE_SERVICE_NAME: str = "XEPDB1"

    # ---- Cache / Redis (field-ized; db split) --------------------------------
    CACHE_TYPE: Literal["redis", "valkey"] = "redis"  # valkey = BSD-3 Redis-compatible drop-in
    CACHE_HOST: str = "localhost"
    CACHE_PORT: int = 16379
    CACHE_PASSWORD: str = "change-me"
    CACHE_USE_SSL: bool = False
    CACHE_DB_APP: int = 0       # business cache + online lease hot-path
    CACHE_DB_SESSION: int = 1   # admin session
    CACHE_DB_BROKER: int = 2    # celery broker
    CACHE_DB_RESULT: int = 3    # celery result
    CACHE_DB_RATELIMIT: int = 4
    CACHE_DB_LOCK: int = 5
    CACHE_DEFAULT_TTL: int = 300
    CACHE_MAX_CONNECTIONS: int = 50

    # ---- Object Storage (field-ized; provider via OBJECT_STORAGE_TYPE) -------
    OBJECT_STORAGE_TYPE: Literal[
        "local", "s3", "azure-blob", "aliyun-oss",
        "google-storage", "tencent-cos", "volcengine-tos", "huawei-obs",
    ] = "local"
    OBJECT_STORAGE_LOCAL_MODE: Literal["filesystem", "minio"] = "filesystem"
    OBJECT_STORAGE_LOCAL_PATH: str = "/var/lib/forge/uploads"
    OBJECT_STORAGE_DEFAULT_BUCKET: str = "forge-uploads"
    OBJECT_STORAGE_PRESIGNED_URL_EXPIRES: int = 900
    OBJECT_STORAGE_MAX_FILE_SIZE: int = 104857600
    # Common cloud credentials (S3 / MinIO / Aliyun OSS / Tencent COS / Volc TOS / Huawei OBS).
    OBJECT_STORAGE_ENDPOINT: str = ""          # e.g. http://minio:9000 ; empty = provider default
    OBJECT_STORAGE_REGION: str = ""
    OBJECT_STORAGE_ACCESS_KEY: str = ""
    OBJECT_STORAGE_SECRET_KEY: str = ""
    OBJECT_STORAGE_SECURE: bool = True         # TLS for endpoint
    # Azure Blob (account/key model instead of access/secret).
    OBJECT_STORAGE_AZURE_ACCOUNT: str = ""
    OBJECT_STORAGE_AZURE_KEY: str = ""
    # Google Cloud Storage (service-account JSON path + project).
    OBJECT_STORAGE_GCS_CREDENTIALS_JSON: str = ""
    OBJECT_STORAGE_GCS_PROJECT: str = ""

    # ---- Email (field-ized; provider via EMAIL_TYPE) ------------------------
    EMAIL_TYPE: Literal[
        "smtp", "aws_ses", "sendgrid", "aliyun_dm", "tencent_ses", "volcengine_dm",
    ] = "smtp"
    EMAIL_FROM_NAME: str = "Forge"
    EMAIL_FROM_ADDRESS: str = "forge@navtra.ai"
    EMAIL_REPLY_TO: str = "support@navtra.ai"
    EMAIL_HOST: str = "localhost"
    EMAIL_PORT: int = 11025
    EMAIL_USERNAME: str = ""
    EMAIL_PASSWORD: str = ""
    EMAIL_USE_TLS: bool = False
    # Cloud email-provider credentials (field-ized; used per EMAIL_TYPE).
    EMAIL_API_KEY: str = ""                      # SendGrid
    EMAIL_ACCESS_KEY: str = ""                   # AWS SES / Aliyun DM / Volc DM access key id
    EMAIL_SECRET_KEY: str = ""                   # AWS SES / Aliyun DM / Volc DM secret
    EMAIL_REGION: str = ""                        # SES / Aliyun / Tencent / Volc region
    EMAIL_TENCENT_SECRET_ID: str = ""            # Tencent SES SecretId
    EMAIL_TENCENT_SECRET_KEY: str = ""           # Tencent SES SecretKey
    EMAIL_TENCENT_TEMPLATE_ID: str = ""          # Tencent SES requires a registered template id
    # Primary→fallback failover (circuit-breaker opens after repeated failures).
    EMAIL_FALLBACK_TYPE: str = ""                # empty = no fallback
    EMAIL_FAILOVER_THRESHOLD: int = 5

    # ---- Search / ES (field-ized; provider via SEARCH_TYPE) ------------------
    # One opensearch-py client drives OpenSearch (default) AND every ES-API-compatible 信创
    # engine (Transwarp Scope / INFINI Easysearch / Huawei CSS / Aliyun·Tencent ES) — only the
    # endpoint/auth differ. (xinchuang.md §4) Optional category: enable only if a project indexes.
    SEARCH_TYPE: Literal[
        "opensearch", "elasticsearch",
        "transwarp", "easysearch", "huawei-css", "aliyun-es", "tencent-es",
    ] = "opensearch"
    SEARCH_HOST: str = "localhost"
    SEARCH_PORT: int = 9200
    SEARCH_USERNAME: str = ""
    SEARCH_PASSWORD: str = ""
    SEARCH_USE_SSL: bool = False
    SEARCH_VERIFY_CERTS: bool = False
    SEARCH_INDEX_PREFIX: str = "forge"

    # ---- Auth / Session ------------------------------------------------------
    SESSION_COOKIE_NAME: str = "forge_admin_session"
    SESSION_ABSOLUTE_TTL_SECONDS: int = 7 * 24 * 3600   # 7 days
    SESSION_IDLE_TTL_SECONDS: int = 12 * 3600
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    PASSWORD_MIN_LENGTH: int = 12
    # Tunable per product (b2b §11.1): a vendor-internal tool may relax these so the
    # convention "login password = email" is allowed (Forge sets classes=1, identity off).
    PASSWORD_REQUIRE_CHAR_CLASSES: int = 3
    PASSWORD_FORBID_IDENTITY: bool = True
    LOGIN_MAX_PER_IP_PER_MIN: int = 10
    LOGIN_LOCK_THRESHOLD: int = 5
    LOGIN_LOCK_SECONDS: int = 15 * 60
    RESET_TOKEN_TTL_SECONDS: int = 15 * 60
    TWOFA_ISSUER: str = "Forge"

    # ---- Crypto: field-level encryption KEK (NEVER in code/repo/log) ---------
    # KEK for wrapping DEKs that encrypt L5 secrets. The MASTER signing key + 2FA secrets are
    # wrapped with FORGE_FIELD_ENCRYPTION_KEY (api-only). The edge_lease key is wrapped with the
    # separate FORGE_EDGE_KEK so the public forge-edge process — which only holds FORGE_EDGE_KEK —
    # can sign leases but can NEVER decrypt the master private key (key-isolation HARD RULE).
    FORGE_FIELD_ENCRYPTION_KEY: str = ""   # base64 32 bytes; master KEK — required in prod for api role
    FORGE_EDGE_KEK: str = ""               # base64 32 bytes; edge_lease KEK; empty => falls back to master KEK (dev)

    # ---- Edge / online validation -------------------------------------------
    LEASE_TTL_SECONDS: int = 24 * 3600
    LEASE_GRACE_SECONDS: int = 72 * 3600
    EDGE_INTERNAL_API_URL: str = "http://forge-api:8080"
    EDGE_INTERNAL_TOKEN: str = ""           # service token for edge -> api internal loop

    # ---- Offline perpetual backstop -----------------------------------------
    OFFLINE_PERPETUAL_YEARS: int = 99

    @property
    def supported_langs(self) -> list[str]:
        return [s.strip() for s in self.SUPPORTED_LANGS.split(",") if s.strip()]


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
