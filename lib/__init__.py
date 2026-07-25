from typing import Any

__all__ = [
    "ProjectManager",
    "PROJECT_ROOT",
    "DataValidator",
    "validate_project",
    "validate_episode",
    "ValidationResult",
]


def __getattr__(name: str) -> Any:
    if name == "PROJECT_ROOT":
        from .env_init import PROJECT_ROOT

        return PROJECT_ROOT
    if name == "ProjectManager":
        from .project_manager import ProjectManager

        return ProjectManager
    if name in {"DataValidator", "ValidationResult", "validate_episode", "validate_project"}:
        from . import data_validator

        return getattr(data_validator, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
