"""Dataroutine package with src compatibility."""

import importlib
import sys

# When imported as 'dataroutine', create 'src' alias for backward compatibility
# This allows 'from src.modules import ...' to work when package is installed
if __name__ == "dataroutine":
    # Import hook to map src.* imports to dataroutine.*
    class SrcImportHook:
        """Import hook to automatically map 'src' imports to 'dataroutine' package."""

        def find_spec(self, name, path, target=None):
            # Only intercept 'src' imports when we're installed as dataroutine
            if name.startswith("src."):
                # Map src.X -> dataroutine.X
                new_name = name.replace("src.", "dataroutine.", 1)
                try:
                    # Try to find the spec for the dataroutine module
                    spec = importlib.util.find_spec(new_name)
                    if spec:
                        # Register alias immediately
                        try:
                            actual_module = importlib.import_module(new_name)
                            sys.modules[name] = actual_module
                        except ImportError:
                            pass
                    return spec
                except (ImportError, ValueError, AttributeError):
                    return None
            return None

    # Create src module alias
    class SrcModule:
        """Compatibility alias for 'src' module."""

        def __init__(self):
            self._modules = None
            self._shared = None

        @property
        def modules(self):
            if self._modules is None:
                # Lazy import to avoid circular dependencies
                import dataroutine.modules

                self._modules = dataroutine.modules
                # Register src.modules alias
                sys.modules["src.modules"] = dataroutine.modules
            return self._modules

        @property
        def shared(self):
            if self._shared is None:
                # Lazy import to avoid circular dependencies
                import dataroutine.shared

                self._shared = dataroutine.shared
                # Register src.shared alias
                sys.modules["src.shared"] = dataroutine.shared
            return self._shared

        def __getattr__(self, name):
            # Try to get from dataroutine
            import dataroutine

            return getattr(dataroutine, name)

    # Register 'src' module alias (only if it doesn't exist - dev mode check)
    if "src" not in sys.modules:
        sys.modules["src"] = SrcModule()
        # Install import hook to handle src.* imports
        sys.meta_path.insert(0, SrcImportHook())
