import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings


class BucketProvisioningError(Exception):
    """Raised when a tenant's IONOS Object Storage bucket couldn't be
    created. Tenant creation is all-or-nothing on this succeeding — see
    `create_tenant` in endpoints/tenants.py — so callers should treat this
    as a request failure, not something to swallow and continue past.
    """


def _s3_client():
    if not settings.IONOS_S3_ENDPOINT_URL or not settings.IONOS_S3_ACCESS_KEY or not settings.IONOS_S3_SECRET_KEY:
        raise BucketProvisioningError(
            "IONOS Object Storage is not configured — set IONOS_S3_ENDPOINT_URL, "
            "IONOS_S3_ACCESS_KEY, and IONOS_S3_SECRET_KEY."
        )
    return boto3.client(
        "s3",
        endpoint_url=settings.IONOS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.IONOS_S3_ACCESS_KEY,
        aws_secret_access_key=settings.IONOS_S3_SECRET_KEY,
        region_name=settings.IONOS_S3_REGION,
    )


def create_tenant_bucket(bucket_name: str) -> None:
    """Creates a new IONOS Object Storage bucket for a newly-provisioned
    tenant, named after its unique company code (e.g. "vl-1234567").

    Synchronous on purpose (boto3 has no async API, same reasoning as
    `app/core/email.py`'s smtplib usage) — callers must run this via
    `run_in_threadpool` so a slow/unreachable IONOS endpoint doesn't block
    the event loop.
    """
    client = _s3_client()
    try:
        client.create_bucket(Bucket=bucket_name)
    except (BotoCoreError, ClientError) as exc:
        raise BucketProvisioningError(f"Could not create storage bucket '{bucket_name}': {exc}") from exc
