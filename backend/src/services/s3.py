import uuid
import boto3
from botocore.config import Config
from core.config import settings as settings_blob

s3_client = boto3.client(
    's3',
    aws_access_key_id=settings_blob.aws_access_key,
    aws_secret_access_key=settings_blob.aws_secret_access_key,
    region_name=settings_blob.aws_region,
    config=Config(signature_version='s3v4'),
)


def generate_upload_url(user_id: uuid.UUID, filename: str) -> tuple[str, str]:
    """Returns (presigned_url, s3_key)"""
    extension = filename.rsplit('.', 1)[-1].lower()
    s3_key = f"cvs/{user_id}/{uuid.uuid4()}.{extension}"

    url = s3_client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': settings_blob.aws_s3_bucket_name,
            'Key': s3_key,
            'ContentType': f'application/{extension}',
        },
        ExpiresIn=300,  # URL valid for 5 minutes
    )
    return url, s3_key

def generate_download_url(s3_key: str) -> str:
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': settings_blob.aws_s3_bucket_name, 
            'Key': s3_key
        },
        ExpiresIn=300,
    )
    return url

def delete_object(s3_key: str) -> None:
    s3_client.delete_object(Bucket=settings_blob.aws_s3_bucket_name, Key=s3_key)
