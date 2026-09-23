import os
import zipfile
from pathlib import Path
from app.core.exceptions import SecurityValidationException
from app.core.config import settings

# Dangerous or executable extensions to discard from unzipping
BLOCKED_ARCHIVE_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".iso", ".bat", ".cmd", ".vbs"
}


def extract_zip_safely(zip_path: str, destination_dir: str) -> int:
    """
    Safely extract a ZIP archive with strict security checks:
    - Mitigates Zip Slip (path traversal outside destination).
    - Mitigates zip bomb (max uncompressed size limit, file count limit).
    - Rejects symlinks and dangerous executable binaries.
    Returns the count of extracted files.
    """
    dest_path = Path(destination_dir).resolve()
    dest_path.mkdir(parents=True, exist_ok=True)

    max_files = settings.MAX_ARCHIVE_FILES
    max_total_bytes = settings.MAX_REPOSITORY_SIZE_MB * 1024 * 1024

    total_bytes = 0
    extracted_count = 0

    if not zipfile.is_zipfile(zip_path):
        raise SecurityValidationException("Uploaded file is not a valid ZIP archive.")

    with zipfile.ZipFile(zip_path, "r") as archive:
        infolist = archive.infolist()
        if len(infolist) > max_files:
            raise SecurityValidationException(
                f"Archive bomb protection: Archive contains {len(infolist)} entries (max allowed: {max_files})."
            )

        for member in infolist:
            total_bytes += member.file_size
            if total_bytes > max_total_bytes:
                raise SecurityValidationException(
                    f"Archive bomb protection: Total extracted size exceeds {settings.MAX_REPOSITORY_SIZE_MB}MB limit."
                )

            # Prevent Zip Slip / path traversal
            target_path = (dest_path / member.filename).resolve()
            if not str(target_path).startswith(str(dest_path)):
                raise SecurityValidationException(
                    f"Zip Slip detected: Archive member '{member.filename}' attempts to escape target directory."
                )

            # Prevent symlink attacks (check mode flags)
            is_symlink = (member.external_attr >> 16) & 0o120000 == 0o120000
            if is_symlink:
                continue

            # Skip dangerous binary extensions
            if target_path.suffix.lower() in BLOCKED_ARCHIVE_EXTENSIONS:
                continue

            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, open(target_path, "wb") as target:
                    target.write(source.read())
                extracted_count += 1

    return extracted_count
