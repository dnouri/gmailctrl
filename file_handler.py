import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

# Define a base directory for all downloads.
DOWNLOADS_DIR = Path("downloads")


def _sanitize_for_path(name: str) -> str:
    """
    Sanitizes a string to be safe for use as a file or directory name.
    Removes potentially invalid characters.
    """
    # Remove characters that are commonly invalid in file/directory names
    # across different operating systems.
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def _find_unique_filepath(
    base_dir: Path, original_filename: str, email_date: datetime
) -> Path:
    """
    Finds a unique path for a file, handling collisions by appending a number.
    The final filename will be prefixed with the email date (YYYY-MM-DD).

    Args:
        base_dir: The directory where the file should be saved.
        original_filename: The desired name of the file.
        email_date: The date of the email, used for the filename prefix.

    Returns:
        A Path object representing a unique, non-existent file path.
    """
    sanitized_filename = _sanitize_for_path(original_filename)
    # If the original filename is empty after sanitization (e.g., it was just '/'),
    # provide a default name.
    if not sanitized_filename:
        sanitized_filename = "unnamed_attachment"

    # Prefix the filename with the date.
    datestr = email_date.strftime("%Y-%m-%d")
    prefixed_filename = f"{datestr} - {sanitized_filename}"

    file_path = base_dir / prefixed_filename
    if not file_path.exists():
        return file_path

    # If the file exists, try appending a number.
    # e.g., "2025-03-03 - document.pdf" -> "2025-03-03 - document-1.pdf"
    stem = file_path.stem
    suffix = file_path.suffix
    counter = 1
    while True:
        # The stem already contains the date and original filename part.
        new_filename = f"{stem}-{counter}{suffix}"
        new_path = base_dir / new_filename
        if not new_path.exists():
            return new_path
        counter += 1


def save_attachment(
    content: bytes, sender: str, original_filename: str, email_date: datetime
) -> Path:
    """
    Saves attachment content to a file safely.

    This function handles:
    - Creating the necessary directory structure.
    - Sanitizing sender email and filename for path safety.
    - Finding a unique filename to avoid collisions, prefixed with the email date.
    - Writing to a temporary file first, then moving it to the final destination
      to prevent partial/corrupt files.
    - Setting the file's modification time to match the email's date.

    Returns:
        The final path where the file was saved.
    """
    # Sanitize sender email to create a valid directory name.
    sender_dir_name = _sanitize_for_path(sender)
    target_dir = DOWNLOADS_DIR / sender_dir_name

    # Create the root 'downloads' and sender-specific directories if they don't exist.
    target_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f"Ensured download directory exists: {target_dir}")

    final_path = _find_unique_filepath(target_dir, original_filename, email_date)
    logging.info(f"Determined unique file path: {final_path}")

    # Use a temporary file in the same directory to ensure atomic move.
    # A NamedTemporaryFile in the final directory is the safest way.
    # We set delete=False so we can move it ourselves.
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=target_dir, delete=False, suffix=".tmp"
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(content)
        logging.info(f"Saved content to temporary file: {tmp_path}")

        # Move the temporary file to its final destination. This is an atomic
        # operation on most systems if the source and destination are on the
        # same filesystem.
        tmp_path.rename(final_path)
        logging.info(f"Moved temporary file to final path: {final_path}")

        # Set the last modified time of the file to the email's date.
        # The timestamp should be in seconds since the epoch.
        timestamp = email_date.timestamp()
        os.utime(final_path, (timestamp, timestamp))
        logging.info(f"Set file timestamp to {email_date.isoformat()}")

    except Exception as e:
        # If anything goes wrong, try to clean up the temporary file if it exists.
        if "tmp_path" in locals() and tmp_path.exists():
            tmp_path.unlink()
        logging.error(f"Failed to save attachment to {final_path}: {e}")
        raise  # Re-raise the exception to be handled by the caller.

    return final_path
