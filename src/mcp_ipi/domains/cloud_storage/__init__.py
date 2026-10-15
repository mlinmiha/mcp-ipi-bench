"""Cloud storage domain with the cloud drive component and its tools."""

from ..base import Domain
from .models import CloudDrive, File, FileInfo
from .tools import (
    append_to_file,
    create_file,
    delete_file,
    get_file_by_id,
    list_files,
    search_files,
    share_file,
)

CLOUD_STORAGE = Domain(
    name="cloud_storage",
    component="cloud_drive",
    model=CloudDrive,
    tools=(list_files, search_files, get_file_by_id, create_file, append_to_file, share_file, delete_file),
)

__all__ = ["CLOUD_STORAGE", "CloudDrive", "File", "FileInfo"]
