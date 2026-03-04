"""Data models for parsed Python entities."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FunctionEntity:
    """A top-level function defined in a module."""

    name: str
    file_path: str
    line_number: int
    end_line: int
    signature: str
    docstring: str | None = None


@dataclass(frozen=True)
class ClassEntity:
    """A class definition."""

    name: str
    file_path: str
    line_number: int
    end_line: int
    bases: tuple[str, ...] = ()


@dataclass(frozen=True)
class MethodEntity:
    """A method defined inside a class."""

    name: str
    class_name: str
    file_path: str
    line_number: int
    end_line: int
    signature: str
    docstring: str | None = None


@dataclass(frozen=True)
class ImportEntity:
    """An import statement (non-stdlib)."""

    module_path: str
    imported_names: tuple[str, ...] = ()
    is_relative: bool = False
    line_number: int = 0


@dataclass(frozen=True)
class CallEntity:
    """A function or method call."""

    caller_name: str
    callee_name: str
    line_number: int


@dataclass
class FileEntities:
    """All entities extracted from a single file."""

    file_path: str
    functions: list[FunctionEntity] = field(default_factory=list)
    classes: list[ClassEntity] = field(default_factory=list)
    methods: list[MethodEntity] = field(default_factory=list)
    imports: list[ImportEntity] = field(default_factory=list)
    calls: list[CallEntity] = field(default_factory=list)
