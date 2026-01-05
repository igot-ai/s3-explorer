import sys
from typing import Optional

from dataroutine.modules.ingestion.core.handlers.base import CollectionHandler


class CollectionHandlerManager:
    _instance = None
    _initialized = False

    def __new__(cls):
        for mod_name, module in sys.modules.items():
            if "collection_handler_manager" in mod_name and hasattr(
                module, "_prototype_manager_shared_instance"
            ):
                return module._prototype_manager_shared_instance

        if cls._instance is None:
            cls._instance = super().__new__(cls)
            global _prototype_manager_shared_instance
            _prototype_manager_shared_instance = cls._instance
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.prototype: Optional[CollectionHandler] = None
        self._initialized = True

    @classmethod
    def get_prototype(cls) -> Optional[CollectionHandler]:
        return cls().prototype

    @classmethod
    def set_prototype(cls, prototype: CollectionHandler):
        instance = cls()
        instance.prototype = prototype
