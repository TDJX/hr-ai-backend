import uuid

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )
        self.bucket_name = settings.s3_bucket_name

    async def upload_file(
        self, file_content: bytes, file_name: str, content_type: str
    ) -> str | None:
        try:
            file_key = f"{uuid.uuid4()}_{file_name}"

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_content,
                ContentType=content_type,
            )

            file_url = f"{settings.s3_endpoint_url}/{self.bucket_name}/{file_key}"
            return file_url

        except ClientError as e:
            print(f"Error uploading file to S3: {e}")
            return None

    async def delete_file(self, file_url: str) -> bool:
        try:
            file_key = file_url.split("/")[-1]

            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)
            return True

        except ClientError as e:
            print(f"Error deleting file from S3: {e}")
            return False


s3_service = S3Service()
