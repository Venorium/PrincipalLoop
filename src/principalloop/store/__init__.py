"""Persistence (PL-03). Principal comes from the kernel, never from an event."""

from .errors import StoreError
from .sqlite import Reader, Receipt, Store

__all__ = ["Reader", "Receipt", "Store", "StoreError"]
