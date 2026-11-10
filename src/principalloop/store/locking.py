"""Lifetime lock, released by the OS when its owner dies.

Every PrincipalLoop writer follows this protocol. A program running under the
same account can still open SQLite directly; this is not fencing.
"""

import os
from pathlib import Path

from .errors import StoreError


class WriterLock:
    def __init__(self, path: Path):
        self.pid = os.getpid()
        self.fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.fstat(self.fd).st_nlink != 1:
                raise StoreError("UNSAFE_PATH", "Writer lock must have one hard link")
            if os.fstat(self.fd).st_size == 0:
                os.write(self.fd, b"0")
            os.lseek(self.fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            os.close(self.fd)
            self.fd = None
            raise StoreError("WRITER_BUSY", "Another kernel owns this database") from error
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise

    def close(self):
        if self.fd is None:
            return
        try:
            if self.pid == os.getpid():
                if os.name == "nt":
                    import msvcrt
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)
            self.fd = None
