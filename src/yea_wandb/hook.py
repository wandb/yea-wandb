import importlib
import sys
import time
from types import ModuleType
from typing import (
    Callable,
    Dict,
    Optional,
    Tuple,
)


class ImportMetaHook:
    def __init__(self) -> None:
        self.modules: Dict[str, ModuleType] = dict()
        self.on_import: Dict[str, list] = dict()

    def add(self, fullname: str, on_import: Callable) -> None:
        self.on_import.setdefault(fullname, []).append(on_import)

    def install(self) -> None:
        sys.meta_path.insert(0, self)  # type: ignore

    def uninstall(self) -> None:
        sys.meta_path.remove(self)  # type: ignore

    def find_module(
        self, fullname: str, path: Optional[str] = None
    ) -> Optional["ImportMetaHook"]:
        if fullname in self.on_import:
            return self
        return None

    def load_module(self, fullname: str) -> ModuleType:
        self.uninstall()
        time_before = time.monotonic()
        mod = importlib.import_module(fullname)
        time_after = time.monotonic()
        self.install()
        self.modules[fullname] = mod
        on_imports = self.on_import.get(fullname)
        if on_imports:
            for f in on_imports:
                f(load_time=time_after - time_before)
        return mod

    def get_modules(self) -> Tuple[str, ...]:
        return tuple(self.modules)

    def get_module(self, module: str) -> ModuleType:
        return self.modules[module]


_import_hook: Optional[ImportMetaHook] = None


def add_import_hook(fullname: str, on_import: Callable) -> None:
    global _import_hook
    if _import_hook is None:
        _import_hook = ImportMetaHook()
        _import_hook.install()
    _import_hook.add(fullname, on_import)
