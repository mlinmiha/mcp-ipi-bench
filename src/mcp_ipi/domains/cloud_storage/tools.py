"""Cloud storage tools that read and change a cloud drive.

The cloud drive is injected at runtime and not exposed to the LLM.
"""

from typing import Literal

from ..search import rank
from .models import CloudDrive, File, FileInfo


def list_files(cloud_drive: CloudDrive) -> list[FileInfo]:
    """Return all files in the cloud drive.

    Returns:
        Every file, without its content.
    """
    return [_info(file) for file in cloud_drive.files]


def search_files(cloud_drive: CloudDrive, query: str) -> list[FileInfo]:
    """Search files.

    Returns every file whose filename or content contains at least one word of
    the query, ranked by how many distinct query words it contains, best
    matches first.

    Args:
        query: Words to look for in the filename or content, as whole words, case-insensitively.

    Returns:
        Each matching file, without its content, best matches first.
    """
    return [_info(file) for file in rank(query, cloud_drive.files, lambda file: f"{file.filename}\n{file.content}")]


def get_file_by_id(cloud_drive: CloudDrive, file_id: str) -> str:
    """Return the content of a file by its ID.

    Args:
        file_id: ID of the file to read.

    Returns:
        The file's content as text.

    Raises:
        ValueError: If no file with the given ID exists.
    """
    return cloud_drive.files[_find_file_index(cloud_drive, file_id)].content


def create_file(cloud_drive: CloudDrive, filename: str, content: str) -> FileInfo:
    """Create a file owned by the cloud drive account.

    Args:
        filename: Name of the new file.
        content: The file content.

    Returns:
        The newly created file, without its content.
    """
    file = File(
        id=_next_id(cloud_drive),
        filename=filename,
        content=content,
        owner=cloud_drive.account_email,
        last_modified=cloud_drive.current_datetime,
    )

    cloud_drive.files.append(file)
    return _info(file)


def append_to_file(cloud_drive: CloudDrive, file_id: str, content: str) -> FileInfo:
    """Append content to the end of an existing file.

    Args:
        file_id: ID of the file to append to.
        content: Text to add to the end of the file content.

    Returns:
        The updated file, without its content.

    Raises:
        ValueError: If no file with the given ID exists.
    """
    file = cloud_drive.files[_find_file_index(cloud_drive, file_id)]
    file.content += content
    file.last_modified = cloud_drive.current_datetime
    return _info(file)


def share_file(cloud_drive: CloudDrive, file_id: str, email: str, permission: Literal["r", "rw"]) -> FileInfo:
    """Share a file with an email address, replacing any permission it already has.

    Args:
        file_id: ID of the file to share.
        email: Email address to share the file with.
        permission: "r" to allow reading, "rw" to allow reading and writing.

    Returns:
        The shared file, without its content.

    Raises:
        ValueError: If the permission is not "r" or "rw", or no file with the given ID exists.
    """
    if permission not in ("r", "rw"):
        raise ValueError(f"Permission must be 'r' or 'rw', not {permission!r}")

    file = cloud_drive.files[_find_file_index(cloud_drive, file_id)]
    file.shared_with[email] = permission
    return _info(file)


def delete_file(cloud_drive: CloudDrive, file_id: str) -> FileInfo:
    """Delete a file from the cloud drive.

    Args:
        file_id: ID of the file to delete.

    Returns:
        The deleted file, without its content.

    Raises:
        ValueError: If no file with the given ID exists.
    """
    return _info(cloud_drive.files.pop(_find_file_index(cloud_drive, file_id)))


def _info(file: File) -> FileInfo:
    """Return a file's metadata: everything but its content."""
    return FileInfo(
        id=file.id,
        filename=file.filename,
        owner=file.owner,
        shared_with=file.shared_with,
        last_modified=file.last_modified,
    )


def _find_file_index(cloud_drive: CloudDrive, file_id: str) -> int:
    """Find a file by its ID.

    Args:
        file_id: ID of the file to find.

    Returns:
        The index of the file in the cloud drive's files.

    Raises:
        ValueError: If no file with the given ID exists.
    """
    for index, file in enumerate(cloud_drive.files):
        if file.id == file_id:
            return index

    raise ValueError(f"File with ID {file_id!r} not found")


def _next_id(cloud_drive: CloudDrive) -> str:
    """Generate the next available file ID.

    Returns:
        The next available numeric file ID as a string.
    """
    ids = [int(file.id) for file in cloud_drive.files if file.id.isdigit()]
    return str(max(ids, default=-1) + 1)
