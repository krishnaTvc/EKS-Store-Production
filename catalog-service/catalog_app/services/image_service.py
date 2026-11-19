import logging
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from catalog_app.config import settings

logger = logging.getLogger(__name__)


class ImageService:
    def __init__(self):
        self._s3_client = None

    @property
    def s3_client(self):
        if self._s3_client is None:
            # Uses AWS default credential chain (Env vars, IAM roles on EKS, ~/.aws/credentials)
            self._s3_client = boto3.client("s3", region_name=settings.AWS_REGION)
        return self._s3_client

    def resolve_image_url(self, image_key: str | None) -> str:
        """
        Resolves an S3 object key to a reachable URL.
        Falls back to the generic placeholder if image_key is None or empty.
        In local mode: returns local static URL path.
        In s3 mode: returns AWS S3 presigned GET URL (never logged).
        """
        target_key = image_key if image_key else settings.PLACEHOLDER_KEY

        if settings.IMAGE_MODE.lower() == "s3":
            try:
                # Generate presigned GET URL
                url = self.s3_client.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={
                        "Bucket": settings.S3_BUCKET_NAME,
                        "Key": target_key
                    },
                    ExpiresIn=settings.S3_PRESIGNED_EXPIRATION_SECONDS
                )
                # Note: URL itself is intentionally NOT logged to prevent credential leakage
                logger.debug(f"Generated S3 presigned URL for key: {target_key}")
                return url
            except (BotoCoreError, ClientError) as e:
                logger.error(f"Failed to generate presigned S3 URL for key {target_key}: {e}")
                # Fall back to local path on AWS failure
                return f"{settings.LOCAL_IMAGE_BASE_URL}/{settings.PLACEHOLDER_KEY}"
        else:
            # Local development mode
            return f"{settings.LOCAL_IMAGE_BASE_URL}/{target_key}"


image_service = ImageService()
