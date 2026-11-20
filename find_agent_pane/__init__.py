"""Which coding agent owns each tmux pane."""
from .core import Proc, Table, Verdict, classify, resolve_pane

__version__ = "0.1.0"
__all__ = ["Proc", "Table", "Verdict", "classify", "resolve_pane", "__version__"]
