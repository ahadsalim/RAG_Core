"""
Storage Service
Handles temporary file storage in MinIO/S3
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import io
import asyncio
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.exceptions import ClientError
import structlog

from app.config.settings import settings

logger = structlog.get_logger()


class StorageService:
    """Service for managing file storage in MinIO/S3."""
    
    def __init__(self):
        """Initialize storage service with S3/MinIO client."""
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
            use_ssl=settings.s3_use_ssl
        )
        
        # Bucket names
        self.documents_bucket = settings.s3_documents_bucket  # advisor-docs
        self.temp_bucket = settings.s3_temp_bucket  # temp-userfile
        self.bucket_name = settings.s3_bucket_name  # Legacy
        
        self.temp_prefix = "temp_uploads/"
        
        # Ensure buckets exist
        self._ensure_bucket_exists(self.documents_bucket)
        self._ensure_bucket_exists(self.temp_bucket)
    
    def _ensure_bucket_exists(self, bucket_name: str):
        """Ensure the storage bucket exists."""
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} exists")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket doesn't exist, create it
                try:
                    self.s3_client.create_bucket(Bucket=bucket_name)
                    logger.info(f"Created bucket {bucket_name}")
                except ClientError as create_error:
                    logger.error(f"Failed to create bucket {bucket_name}: {create_error}")
            else:
                logger.error(f"Error checking bucket {bucket_name}: {e}")
    
    async def upload_temp_file(
        self,
        file_content: bytes,
        filename: str,
        user_id: str,
        content_type: str = 'application/octet-stream',
        expiration_hours: int = None
    ) -> Dict[str, Any]:
        """
        Upload a file to temporary storage.
        
        Args:
            file_content: Binary content of the file
            filename: Original filename
            user_id: User ID for organizing files
            content_type: MIME type of the file
            expiration_hours: Hours until file expires (default from settings.temp_file_expiration_hours)
            
        Returns:
            Dictionary with file metadata and storage key
        """
        try:
            # Generate unique key
            file_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            object_key = f"{self.temp_prefix}{user_id}/{timestamp}_{file_id}_{filename}"
            
            # Calculate expiration (use settings if not provided)
            hours = expiration_hours if expiration_hours is not None else settings.temp_file_expiration_hours
            expiration_date = datetime.utcnow() + timedelta(hours=hours)
            
            # Prepare metadata
            metadata = {
                'user_id': user_id,
                'original_filename': filename,
                'upload_timestamp': datetime.utcnow().isoformat(),
                'expiration_date': expiration_date.isoformat(),
                'file_id': file_id
            }
            
            # Upload to S3 (temp bucket for user files)
            def _upload_sync():
                self.s3_client.put_object(
                    Bucket=self.temp_bucket,  # Use temp-userfile bucket
                    Key=object_key,
                    Body=file_content,
                    ContentType=content_type,
                    Metadata=metadata,
                    # Set expiration using lifecycle policy or tagging
                    Tagging=f"expiration={expiration_date.isoformat()}"
                )
            
            # Run upload in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.executor, _upload_sync)
            
            logger.info(
                "File uploaded to temp storage",
                object_key=object_key,
                user_id=user_id,
                filename=filename,
                size_bytes=len(file_content)
            )
            
            return {
                'file_id': file_id,
                'object_key': object_key,
                'filename': filename,
                'size_bytes': len(file_content),
                'content_type': content_type,
                'uploaded_at': datetime.utcnow().isoformat(),
                'expires_at': expiration_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to upload file to temp storage: {e}", filename=filename)
            raise
    
    async def download_temp_file(self, object_key: str, bucket: Optional[str] = None) -> bytes:
        """
        Download a file from temporary storage.
        
        Args:
            object_key: S3 object key
            bucket: Bucket name (defaults to temp_bucket)
            
        Returns:
            File content as bytes
        """
        try:
            bucket_name = bucket or self.temp_bucket
            
            def _download_sync():
                response = self.s3_client.get_object(
                    Bucket=bucket_name,
                    Key=object_key
                )
                return response['Body'].read()
            
            # Run download in thread pool
            loop = asyncio.get_event_loop()
            file_content = await loop.run_in_executor(self.executor, _download_sync)
            
            logger.info("File downloaded from temp storage", object_key=object_key)
            return file_content
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                raise FileNotFoundError(f"File not found: {object_key}")
            else:
                logger.error(f"Failed to download file: {e}", object_key=object_key)
                raise
    
    async def delete_temp_file(self, object_key: str) -> bool:
        """
        Delete a file from temporary storage (temp-userfile bucket).
        
        Args:
            object_key: S3 object key
            
        Returns:
            True if deleted successfully
        """
        try:
            def _delete_sync():
                self.s3_client.delete_object(
                    Bucket=self.temp_bucket,  # Use temp-userfile bucket
                    Key=object_key
                )
            
            # Run delete in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.executor, _delete_sync)
            
            logger.info("File deleted from temp storage", object_key=object_key)
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file: {e}", object_key=object_key)
            return False
    
    async def upload_multiple_files(
        self,
        files: List[Dict[str, Any]],
        user_id: str,
        expiration_hours: int = None
    ) -> List[Dict[str, Any]]:
        """
        Upload multiple files to temporary storage.
        
        Args:
            files: List of file dictionaries with 'content', 'filename', 'content_type'
            user_id: User ID
            expiration_hours: Hours until files expire (default from settings.temp_file_expiration_hours)
            
        Returns:
            List of upload results
        """
        if len(files) > 5:
            raise ValueError("Maximum 5 files allowed per request")
        
        # Upload files concurrently
        tasks = [
            self.upload_temp_file(
                file_content=file['content'],
                filename=file['filename'],
                user_id=user_id,
                content_type=file.get('content_type', 'application/octet-stream'),
                expiration_hours=expiration_hours
            )
            for file in files
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        upload_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to upload file {files[i]['filename']}: {result}")
                upload_results.append({
                    'filename': files[i]['filename'],
                    'error': str(result),
                    'uploaded': False
                })
            else:
                upload_results.append({**result, 'uploaded': True})
        
        return upload_results
    
    async def cleanup_expired_files(self) -> int:
        """
        Clean up expired temporary files from temp_bucket.
        Files are deleted after TEMP_FILE_EXPIRATION_HOURS (default 12 hours).
        Note: File analysis remains in conversation memory.
        
        Returns:
            Number of files deleted
        """
        try:
            deleted_count = 0
            
            def _list_and_delete_sync():
                nonlocal deleted_count
                
                # List all objects in temp bucket with temp_uploads prefix
                paginator = self.s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(
                    Bucket=self.temp_bucket,  # Use temp-userfile bucket
                    Prefix=self.temp_prefix
                )
                
                current_time = datetime.utcnow()
                
                for page in pages:
                    if 'Contents' not in page:
                        continue
                    
                    for obj in page['Contents']:
                        # Get object metadata
                        try:
                            response = self.s3_client.head_object(
                                Bucket=self.temp_bucket,
                                Key=obj['Key']
                            )
                            
                            metadata = response.get('Metadata', {})
                            expiration_str = metadata.get('expiration_date')
                            
                            if expiration_str:
                                expiration_date = datetime.fromisoformat(expiration_str)
                                
                                # Delete if expired
                                if current_time > expiration_date:
                                    self.s3_client.delete_object(
                                        Bucket=self.temp_bucket,
                                        Key=obj['Key']
                                    )
                                    deleted_count += 1
                                    logger.info(
                                        "Deleted expired temp file",
                                        key=obj['Key'],
                                        expired_at=expiration_str
                                    )
                        except Exception as e:
                            logger.error(f"Error processing object {obj['Key']}: {e}")
                            continue
            
            # Run cleanup in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.executor, _list_and_delete_sync)
            
            logger.info(
                "Temp files cleanup completed",
                deleted_count=deleted_count,
                expiration_hours=settings.temp_file_expiration_hours
            )
            return deleted_count
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return 0


# Global service instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get or create storage service instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
