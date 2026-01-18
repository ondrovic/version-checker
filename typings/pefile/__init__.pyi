"""Type stubs for pefile library."""

from typing import Any

class StringTable:
    entries: dict[bytes, bytes]

class StringFileInfo:
    StringTable: list[StringTable]

class PE:
    FileInfo: list[list[StringFileInfo]]
    VS_VERSIONINFO: Any

    def __init__(self, name: str, fast_load: bool = False) -> None: ...
    def close(self) -> None: ...
