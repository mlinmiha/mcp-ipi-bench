"""Building a fresh, validated environment from its YAML data."""

from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

from .injection import fill_injections
from .yaml_loader import load_yaml


def load_environment[T: BaseModel](
    data_path: Path, environment_cls: type[T], injections: Mapping[str, str] | None = None
) -> T:
    """Load an environment YAML file, fill its placeholders and validate it into a new `environment_cls`.

    Args:
        data_path: The environment YAML file; `!include` tags in it are followed.
        environment_cls: The Pydantic model to validate the data into.
        injections: The text for each injection vector ID; leaving it out is the same as `{}`.

    Raises:
        YamlLoadError: The environment file or an included file does not exist.
        yaml.YAMLError: A file cannot be parsed.
        KeyError: A placeholder's injection vector ID has no text.
        pydantic.ValidationError: The data does not fit `environment_cls`.
    """
    return environment_cls.model_validate(fill_injections(load_yaml(data_path), injections or {}))
