from abc import ABC, abstractmethod
import os
import shutil
from typing import BinaryIO
from app.core.config import settings


class BaseStorageProvider(ABC):
    @abstractmethod
    def save_file(self, file_obj: BinaryIO, relative_path: str) -> str:
        """Save a file and return its stored URI/path."""
        pass

    @abstractmethod
    def get_file(self, relative_path: str) -> bytes:
        """Retrieve a file's bytes."""
        pass

    @abstractmethod
    def delete_file(self, relative_path: str) -> None:
        """Delete a stored file if it exists."""
        pass


class LocalStorageProvider(BaseStorageProvider):
    def __init__(self, base_dir: str = settings.LOCAL_STORAGE_DIR):
        self.base_dir = os.path.realpath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def _resolve(self, relative_path: str) -> str:
        full_path = os.path.realpath(os.path.join(self.base_dir, relative_path))
        # Guard against path traversal ("../") escaping the storage root.
        if os.path.commonpath([full_path, self.base_dir]) != self.base_dir:
            raise ValueError("Invalid storage path")
        return full_path

    def save_file(self, file_obj: BinaryIO, relative_path: str) -> str:
        full_path = self._resolve(relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        file_obj.seek(0)
        with open(full_path, "wb") as f:
            shutil.copyfileobj(file_obj, f)
        return full_path

    def get_file(self, relative_path: str) -> bytes:
        full_path = self._resolve(relative_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {relative_path}")
        with open(full_path, "rb") as f:
            return f.read()

    def delete_file(self, relative_path: str) -> None:
        full_path = self._resolve(relative_path)
        if os.path.exists(full_path):
            os.remove(full_path)


class DatabaseStorageProvider(BaseStorageProvider):
    """Stores file bytes in the `stored_files` table, for hosts with ephemeral disks (e.g. free PaaS tiers)."""

    def save_file(self, file_obj: BinaryIO, relative_path: str) -> str:
        from app.db.session import SessionLocal
        from app.models.entities import StoredFile

        file_obj.seek(0)
        content = file_obj.read()
        with SessionLocal() as db:
            db.merge(StoredFile(path=relative_path, content=content, size_bytes=len(content)))
            db.commit()
        return f"db://{relative_path}"

    def get_file(self, relative_path: str) -> bytes:
        from app.db.session import SessionLocal
        from app.models.entities import StoredFile

        with SessionLocal() as db:
            stored = db.get(StoredFile, relative_path)
            if stored is None:
                raise FileNotFoundError(f"File not found: {relative_path}")
            return stored.content

    def delete_file(self, relative_path: str) -> None:
        from sqlalchemy import delete

        from app.db.session import SessionLocal
        from app.models.entities import StoredFile

        with SessionLocal() as db:
            db.execute(delete(StoredFile).where(StoredFile.path == relative_path))
            db.commit()


def get_storage_provider() -> BaseStorageProvider:
    if settings.STORAGE_TYPE == "local":
        return LocalStorageProvider()
    if settings.STORAGE_TYPE == "database":
        return DatabaseStorageProvider()
    raise ValueError(f"STORAGE_TYPE '{settings.STORAGE_TYPE}' is not implemented; use 'local' or 'database'.")
