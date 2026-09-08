"""Cross-process safe JSON state updates for Windows and POSIX."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def _file_lock(lock_path: str) -> Iterator[None]:
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with open(lock_path, "a+b") as lock_file:
        lock_file.seek(0)
        if os.name == "nt":
            import msvcrt

            lock_file.write(b"\0")
            lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def update_bot_state(state_path: str, entry: dict) -> None:
    """Atomically upsert one bot entry while serializing all writers."""
    lock_path = state_path + ".lock"
    pid = entry.get("pid")
    with _file_lock(lock_path):
        try:
            with open(state_path, "r", encoding="utf-8") as state_file:
                states = json.load(state_file)
        except (FileNotFoundError, json.JSONDecodeError):
            states = []

        states = [state for state in states if state.get("pid") != pid]
        states.append(entry)
        tmp_path = state_path + f".{pid}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as state_file:
            json.dump(states, state_file)

        last_error = None
        for _ in range(5):
            try:
                os.replace(tmp_path, state_path)
                return
            except PermissionError as error:
                last_error = error
                time.sleep(0.05)
        raise last_error


def remove_bot_state(state_path: str, pid: int) -> None:
    """Atomically remove one bot entry while serializing all writers."""
    lock_path = state_path + ".lock"
    with _file_lock(lock_path):
        try:
            with open(state_path, "r", encoding="utf-8") as state_file:
                states = json.load(state_file)
        except (FileNotFoundError, json.JSONDecodeError):
            return

        states = [state for state in states if state.get("pid") != pid]
        tmp_path = state_path + f".{pid}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as state_file:
            json.dump(states, state_file)
        os.replace(tmp_path, state_path)
