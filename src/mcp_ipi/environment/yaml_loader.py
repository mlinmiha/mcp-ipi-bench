"""Safe YAML loading for environment data files, with `!include` relative to the including file."""

from pathlib import Path
from typing import Any

import yaml


class YamlLoadError(ValueError):
    """A YAML data file cannot be loaded; the message names the file."""


class _Loader(yaml.SafeLoader):
    """Private safe loader, so tags registered here never reach PyYAML's global `SafeLoader`."""


def _include(loader: _Loader, node: yaml.ScalarNode) -> Any:
    """Load the file named by an `!include` tag, relative to the directory of the file containing it."""
    return load_yaml(Path(loader.name).parent / loader.construct_scalar(node))


_Loader.add_constructor("!include", _include)


def load_yaml(path: Path) -> Any:
    """Load one YAML document from a UTF-8 file with a safe loader.

    A scalar tagged `!include <path>` is replaced by the loaded content of that file, with the path
    resolved against the directory of the file containing the tag.

    Args:
        path: The YAML file to load.

    Returns:
        Plain Python data: dicts, lists, strings, numbers, booleans, `None`, dates and datetimes.

    Raises:
        YamlLoadError: The file does not exist.
        yaml.YAMLError: The file has a syntax error, an unsafe or unknown tag, or more than one document.
    """
    try:
        stream = path.open(encoding="utf-8")
    except FileNotFoundError as error:
        raise YamlLoadError(f"YAML file not found: {path}") from error

    with stream:
        return yaml.load(stream, Loader=_Loader)
