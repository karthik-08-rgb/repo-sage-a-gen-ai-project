import pytest
import io
import zipfile
import tempfile
import os
from pathlib import Path
from app.services.repository.security_validator import validate_repository_url
from app.services.repository.zip_validator import extract_zip_safely
from app.core.exceptions import SecurityValidationException


def test_ssrf_blocks_private_ip_and_metadata():
    # Loopback
    with pytest.raises(SecurityValidationException) as exc:
        validate_repository_url("https://127.0.0.1/evil/repo")
    assert "restricted network" in str(exc.value).lower() or "invalid git" in str(exc.value).lower()

    # AWS / GCP metadata service
    with pytest.raises(SecurityValidationException):
        validate_repository_url("https://169.254.169.254/latest/meta-data")

    # Non-HTTPS protocol
    with pytest.raises(SecurityValidationException):
        validate_repository_url("http://github.com/octocat/Hello-World")


def test_zip_slip_prevention():
    # Construct an in-memory zip archive with path traversal member
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        z.writestr("../../../evil.sh", "echo 'pwned'")

    zip_buffer.seek(0)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_zip:
        tmp_zip.write(zip_buffer.read())
        tmp_zip_path = tmp_zip.name

    with tempfile.TemporaryDirectory() as dest_dir:
        try:
            with pytest.raises(SecurityValidationException) as exc:
                extract_zip_safely(tmp_zip_path, dest_dir)
            assert "zip slip" in str(exc.value).lower()
        finally:
            if os.path.exists(tmp_zip_path):
                os.remove(tmp_zip_path)
