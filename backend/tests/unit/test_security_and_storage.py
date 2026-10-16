import io
import tempfile

import pytest
from fastapi import HTTPException

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.services.storage_service import LocalStorageProvider


def test_local_storage_provider():
    with tempfile.TemporaryDirectory() as tmp_dir:
        provider = LocalStorageProvider(base_dir=tmp_dir)
        file_data = io.BytesIO(b"Physics Exam Draft 2026")
        saved_path = provider.save_file(file_data, "physics/paper.pdf")

        assert saved_path.endswith("paper.pdf")
        content = provider.get_file("physics/paper.pdf")
        assert content == b"Physics Exam Draft 2026"

        provider.delete_file("physics/paper.pdf")
        with pytest.raises(FileNotFoundError):
            provider.get_file("physics/paper.pdf")


def test_storage_rejects_path_traversal():
    with tempfile.TemporaryDirectory() as tmp_dir:
        provider = LocalStorageProvider(base_dir=tmp_dir)
        with pytest.raises(ValueError):
            provider.save_file(io.BytesIO(b"x"), "../escape.pdf")


def test_jwt_token_creation_and_decoding():
    token = create_access_token({"sub": "user_123", "email": "faculty@univ.edu"})
    decoded = decode_access_token(token)
    assert decoded["sub"] == "user_123"
    assert decoded["email"] == "faculty@univ.edu"


def test_refresh_token_cannot_be_used_as_access_token():
    with pytest.raises(HTTPException) as exc:
        decode_access_token(create_refresh_token("user_123"))
    assert exc.value.status_code == 401


def test_tampered_token_is_rejected():
    token = create_access_token({"sub": "user_123"})
    header, payload, signature = token.split(".")
    forged = ".".join([header, payload, signature[::-1]])
    with pytest.raises(HTTPException):
        decode_access_token(forged)


def test_password_hashing():
    hashed = hash_password("Password123")
    assert hashed != "Password123"
    assert verify_password("Password123", hashed)
    assert not verify_password("wrong", hashed)


def test_database_storage_provider():
    from app.services.storage_service import DatabaseStorageProvider

    provider = DatabaseStorageProvider()
    provider.save_file(io.BytesIO(b"v1"), "PHY/PHY-201/paper.pdf")
    provider.save_file(io.BytesIO(b"v2"), "PHY/PHY-201/paper.pdf")  # overwrite is allowed
    assert provider.get_file("PHY/PHY-201/paper.pdf") == b"v2"
    provider.delete_file("PHY/PHY-201/paper.pdf")
    with pytest.raises(FileNotFoundError):
        provider.get_file("PHY/PHY-201/paper.pdf")
