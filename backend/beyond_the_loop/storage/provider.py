import logging
import os
import shutil
import time
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional, Tuple

log = logging.getLogger(__name__)

import boto3
from botocore.exceptions import ClientError
from beyond_the_loop.config import (
    S3_ACCESS_KEY_ID,
    S3_BUCKET_NAME,
    S3_ENDPOINT_URL,
    S3_REGION_NAME,
    S3_SECRET_ACCESS_KEY,
    GCS_BUCKET_NAME,
    STORAGE_PROVIDER,
    UPLOAD_DIR,
)
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError, NotFound
from open_webui.constants import ERROR_MESSAGES


class StorageProvider(ABC):
    @abstractmethod
    def get_file(self, file_path: str) -> str:
        pass

    @abstractmethod
    def upload_file(self, file: BinaryIO, filename: str) -> Tuple[bytes, str]:
        pass

    @abstractmethod
    def delete_all_files(self) -> None:
        pass

    @abstractmethod
    def delete_file(self, file_path: str) -> None:
        pass

    def get_presigned_url(self, file_path: str, expiry_seconds: int = 600) -> Optional[str]:
        return None


class LocalStorageProvider(StorageProvider):
    @staticmethod
    def upload_file(file: BinaryIO, filename: str) -> Tuple[bytes, str]:
        t0 = time.perf_counter()
        contents = file.read()
        log.info(
            "[UPLOAD_TIMING] step=local_read_stream duration_ms=%.2f bytes=%d",
            (time.perf_counter() - t0) * 1000,
            len(contents),
        )
        if not contents:
            raise ValueError(ERROR_MESSAGES.EMPTY_CONTENT)
        file_path = f"{UPLOAD_DIR}/{filename}"
        t0 = time.perf_counter()
        with open(file_path, "wb") as f:
            f.write(contents)
        log.info(
            "[UPLOAD_TIMING] step=local_write_to_disk duration_ms=%.2f path=%s",
            (time.perf_counter() - t0) * 1000,
            file_path,
        )
        return contents, file_path

    @staticmethod
    def get_file(file_path: str) -> str:
        """Handles downloading of the file from local storage."""
        return file_path

    @staticmethod
    def delete_file(file_path: str) -> None:
        """Handles deletion of the file from local storage."""
        filename = file_path.split("/")[-1]
        file_path = f"{UPLOAD_DIR}/{filename}"
        if os.path.isfile(file_path):
            os.remove(file_path)
        else:
            log.warning(f"File {file_path} not found in local storage.")

    @staticmethod
    def delete_all_files() -> None:
        """Handles deletion of all files from local storage."""
        if os.path.exists(UPLOAD_DIR):
            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)  # Remove the file or link
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)  # Remove the directory
                except Exception as e:
                    log.error(f"Failed to delete {file_path}. Reason: {e}")
        else:
            log.warning(f"Directory {UPLOAD_DIR} not found in local storage.")

class GCSStorageProvider(StorageProvider):
    def __init__(self):
        self.bucket_name = GCS_BUCKET_NAME

        self.gcs_client = storage.Client()
        self.bucket = self.gcs_client.bucket(GCS_BUCKET_NAME)

    def upload_file(self, file: BinaryIO, filename: str) -> Tuple[bytes, str]:
        """Handles uploading of the file to GCS storage."""
        contents, file_path = LocalStorageProvider.upload_file(file, filename)
        try:
            t0 = time.perf_counter()
            blob = self.bucket.blob(filename)
            blob.upload_from_filename(file_path)
            log.info(
                "[UPLOAD_TIMING] step=gcs_upload_from_filename duration_ms=%.2f bucket=%s blob=%s bytes=%d",
                (time.perf_counter() - t0) * 1000,
                self.bucket_name,
                filename,
                len(contents),
            )
            return contents, "gs://" + self.bucket_name + "/" + filename
        except GoogleCloudError as e:
            raise RuntimeError(f"Error uploading file to GCS: {e}")

    def get_file(self, file_path: str) -> str:
        """Handles downloading of the file from GCS storage."""
        try:
            filename = file_path.removeprefix("gs://").split("/")[1]
            local_file_path = f"{UPLOAD_DIR}/{filename}"
            blob = self.bucket.get_blob(filename)
            blob.download_to_filename(local_file_path)

            return local_file_path
        except NotFound as e:
            raise RuntimeError(f"Error downloading file from GCS: {e}")

    def delete_file(self, file_path: str) -> None:
        """Handles deletion of the file from GCS storage."""
        try:
            filename = file_path.removeprefix("gs://").split("/")[1]
            blob = self.bucket.get_blob(filename)
            blob.delete()
        except NotFound as e:
            raise RuntimeError(f"Error deleting file from GCS: {e}")

        # Always delete from local storage
        LocalStorageProvider.delete_file(file_path)

    def delete_all_files(self) -> None:
        """Handles deletion of all files from GCS storage."""
        try:
            blobs = self.bucket.list_blobs()

            for blob in blobs:
                blob.delete()

        except NotFound as e:
            raise RuntimeError(f"Error deleting all files from GCS: {e}")

        # Always delete from local storage
        LocalStorageProvider.delete_all_files()



def get_storage_provider(storage_provider: str):
    if storage_provider == "local":
        Storage = LocalStorageProvider()
    elif storage_provider == "gcs":
        Storage = GCSStorageProvider()
    else:
        raise RuntimeError(f"Unsupported storage provider: {storage_provider}")
    return Storage


Storage = get_storage_provider(STORAGE_PROVIDER)
