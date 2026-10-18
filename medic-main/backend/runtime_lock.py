"""Prevent a second server from owning the same database or inbound phone line."""
from contextlib import contextmanager


@contextmanager
def process_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+b')
    try:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'\0')
            handle.flush()
        handle.seek(0)
        try:
            if __import__('os').name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SystemExit('Another Medic process already owns this server or phone line. Stop that process first.') from exc
        yield
    finally:
        handle.close()  # OS releases the lock even after a crash.
