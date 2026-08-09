"""Immutable evidence object storage backends."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Optional


class ObjectStorageError(RuntimeError):
    """The configured immutable object store could not preserve evidence."""


class FileObjectStore:
    backend = "file"

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put_once(
        self,
        key: str,
        payload: bytes,
        content_type: str,
        *,
        verify_existing: bool = True,
    ) -> None:
        del content_type
        path = self._path(key)
        if path.exists():
            if verify_existing and hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(payload).digest():
                raise ObjectStorageError(f"内容寻址对象发生冲突: {key}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(str(temporary_path), str(path))
            except FileExistsError:
                pass
        finally:
            temporary_path.unlink(missing_ok=True)

    def get_bytes(self, key: str) -> bytes:
        return self.get_primary_bytes(key)

    def get_primary_bytes(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise ObjectStorageError(f"原始证据对象不存在: {key}")
        return path.read_bytes()

    def materialize(
        self,
        key: str,
        cache_root: Path,
        expected_hash: Optional[str] = None,
    ) -> Path:
        del cache_root
        path = self._path(key)
        if not path.is_file():
            raise ObjectStorageError(f"原始证据对象不存在: {key}")
        if expected_hash and hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ObjectStorageError(f"原始证据对象哈希不一致: {key}")
        return path

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def restore_from_backup(self, key: str) -> None:
        del key
        raise ObjectStorageError("文件后端没有配置独立备份对象桶")

    def get_backup_bytes(self, key: str) -> bytes:
        del key
        raise ObjectStorageError("文件后端没有配置独立备份对象桶")

    def health(self) -> dict[str, str]:
        return {"backend": self.backend, "root": str(self.root), "status": "healthy"}

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root != path and self.root not in path.parents:
            raise ObjectStorageError(f"对象键越界: {key}")
        return path


class S3ObjectStore:
    backend = "s3"

    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        backup_bucket: Optional[str] = None,
    ) -> None:
        if not endpoint_url or not bucket or not access_key or not secret_key:
            raise ObjectStorageError("S3 对象存储配置不完整")
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise ObjectStorageError("S3 对象存储需要 boto3") from exc
        self.endpoint_url = endpoint_url.rstrip("/")
        self.bucket = bucket
        self.backup_bucket = backup_bucket or None
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def put_once(
        self,
        key: str,
        payload: bytes,
        content_type: str,
        *,
        verify_existing: bool = True,
    ) -> None:
        self._put_once(self.bucket, key, payload, content_type, verify_existing=verify_existing)
        if self.backup_bucket:
            self._put_once(
                self.backup_bucket,
                key,
                payload,
                content_type,
                verify_existing=verify_existing,
            )

    def get_bytes(self, key: str) -> bytes:
        try:
            return self.get_primary_bytes(key)
        except ObjectStorageError:
            if self.backup_bucket:
                return self.get_backup_bytes(key)
            raise

    def get_primary_bytes(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except Exception as exc:
            raise ObjectStorageError(f"读取原始证据对象失败: {key}: {exc}") from exc

    def materialize(
        self,
        key: str,
        cache_root: Path,
        expected_hash: Optional[str] = None,
    ) -> Path:
        cache_root = Path(cache_root).resolve()
        payload = None
        try:
            head = self._head(self.bucket, key)
            if head is None:
                raise ObjectStorageError(f"原始证据对象不存在: {key}")
            expected = str(head.get("Metadata", {}).get("sha256") or "")
            if not expected:
                payload = self.get_primary_bytes(key)
                expected = hashlib.sha256(payload).hexdigest()
        except ObjectStorageError:
            if not self.backup_bucket:
                raise
            payload = self.get_backup_bytes(key)
            expected = hashlib.sha256(payload).hexdigest()
        if expected_hash and expected != expected_hash:
            raise ObjectStorageError(f"原始证据对象与目录哈希不一致: {key}")
        path = (cache_root / expected / key).resolve()
        if cache_root != path and cache_root not in path.parents:
            raise ObjectStorageError(f"对象缓存键越界: {key}")
        if path.is_file():
            if hashlib.sha256(path.read_bytes()).hexdigest() == expected:
                return path
            if payload is None:
                payload = self.get_bytes(key)
            if hashlib.sha256(payload).hexdigest() != expected:
                raise ObjectStorageError(f"原始证据对象元数据哈希不一致: {key}")
            recovery_dir = cache_root / "recovered" / expected
            recovery_dir.mkdir(parents=True, exist_ok=True)
            descriptor, recovery_name = tempfile.mkstemp(
                prefix=f"{Path(key).name}.",
                dir=str(recovery_dir),
            )
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            return Path(recovery_name)
        if payload is None:
            payload = self.get_primary_bytes(key)
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ObjectStorageError(f"原始证据对象元数据哈希不一致: {key}")
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(str(temporary_path), str(path))
            except FileExistsError:
                pass
        finally:
            temporary_path.unlink(missing_ok=True)
        return path

    def exists(self, key: str) -> bool:
        return self._head(self.bucket, key) is not None

    def restore_from_backup(self, key: str) -> None:
        if not self.backup_bucket:
            raise ObjectStorageError("没有配置对象备份桶")
        try:
            response = self.client.get_object(Bucket=self.backup_bucket, Key=key)
            payload = response["Body"].read()
            content_type = response.get("ContentType") or "application/octet-stream"
            self._put_once(self.bucket, key, payload, content_type)
        except Exception as exc:
            raise ObjectStorageError(f"从备份桶恢复对象失败: {key}: {exc}") from exc

    def get_backup_bytes(self, key: str) -> bytes:
        if not self.backup_bucket:
            raise ObjectStorageError("没有配置对象备份桶")
        try:
            response = self.client.get_object(Bucket=self.backup_bucket, Key=key)
            return response["Body"].read()
        except Exception as exc:
            raise ObjectStorageError(f"读取备份对象失败: {key}: {exc}") from exc

    def health(self) -> dict[str, str]:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            if self.backup_bucket:
                self.client.head_bucket(Bucket=self.backup_bucket)
        except Exception as exc:
            raise ObjectStorageError(f"对象存储健康检查失败: {exc}") from exc
        return {
            "backend": self.backend,
            "endpoint": self.endpoint_url,
            "bucket": self.bucket,
            "backup_bucket": self.backup_bucket or "",
            "status": "healthy",
        }

    def _put_once(
        self,
        bucket: str,
        key: str,
        payload: bytes,
        content_type: str,
        *,
        verify_existing: bool = True,
    ) -> None:
        existing = self._head(bucket, key)
        checksum = hashlib.sha256(payload).hexdigest()
        if existing:
            stored = str(existing.get("Metadata", {}).get("sha256") or "")
            if verify_existing:
                if not stored:
                    response = self.client.get_object(Bucket=bucket, Key=key)
                    stored = hashlib.sha256(response["Body"].read()).hexdigest()
                if stored != checksum:
                    raise ObjectStorageError(f"内容寻址对象发生冲突: {bucket}/{key}")
            return
        try:
            self.client.put_object(
                Bucket=bucket,
                Key=key,
                Body=payload,
                ContentType=content_type or "application/octet-stream",
                Metadata={"sha256": checksum},
            )
        except Exception as exc:
            raise ObjectStorageError(f"写入原始证据对象失败: {bucket}/{key}: {exc}") from exc

    def _head(self, bucket: str, key: str):
        try:
            return self.client.head_object(Bucket=bucket, Key=key)
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = str(response.get("Error", {}).get("Code") or "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise ObjectStorageError(f"检查原始证据对象失败: {bucket}/{key}: {exc}") from exc


def configured_object_store(root: Path):
    backend = os.getenv("QSOU_OBJECT_STORAGE_BACKEND", "file").strip().lower()
    if backend == "file":
        return FileObjectStore(Path(root))
    if backend != "s3":
        raise ObjectStorageError(f"不支持的对象存储后端: {backend}")
    return S3ObjectStore(
        endpoint_url=os.getenv("QSOU_OBJECT_STORAGE_ENDPOINT", ""),
        bucket=os.getenv("QSOU_OBJECT_STORAGE_BUCKET", ""),
        backup_bucket=os.getenv("QSOU_OBJECT_BACKUP_BUCKET") or None,
        access_key=os.getenv("QSOU_OBJECT_STORAGE_ACCESS_KEY", ""),
        secret_key=os.getenv("QSOU_OBJECT_STORAGE_SECRET_KEY", ""),
        region=os.getenv("QSOU_OBJECT_STORAGE_REGION", "us-east-1"),
    )
