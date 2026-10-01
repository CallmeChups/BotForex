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


def _load_swing_setup_state(state_path: str) -> dict[str, list[str]]:
    try:
        with open(state_path, "r", encoding="utf-8") as state_file:
            state = json.load(state_file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid swing setup state file: {state_path}") from error

    if not isinstance(state, dict) or any(
        not isinstance(key, str)
        or not isinstance(setup_ids, list)
        or any(not isinstance(setup_id, str) for setup_id in setup_ids)
        for key, setup_ids in state.items()
    ):
        raise ValueError(f"Invalid swing setup state format: {state_path}")
    return state


def _save_swing_setup_state(state_path: str, state: dict[str, list[str]]) -> None:
    tmp_path = state_path + f".{os.getpid()}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as state_file:
        json.dump(state, state_file)

    last_error = None
    for _ in range(5):
        try:
            os.replace(tmp_path, state_path)
            return
        except PermissionError as error:
            last_error = error
            time.sleep(0.05)
    raise last_error


def load_swing_setup_ids(state_path: str, key: str) -> set[str]:
    """Load setup IDs already reserved by a live Swing strategy instance."""
    with _file_lock(state_path + ".lock"):
        state = _load_swing_setup_state(state_path)
    return set(state.get(key, []))


def reserve_swing_setup_id(state_path: str, key: str, setup_id: str) -> bool:
    """Atomically reserve a setup ID; return False if another process used it."""
    with _file_lock(state_path + ".lock"):
        state = _load_swing_setup_state(state_path)
        setup_ids = state.setdefault(key, [])
        if setup_id in setup_ids:
            return False
        setup_ids.append(setup_id)
        _save_swing_setup_state(state_path, state)
        return True


def release_swing_setup_id(state_path: str, key: str, setup_id: str) -> None:
    """Release a reservation when the broker rejects the associated order."""
    with _file_lock(state_path + ".lock"):
        state = _load_swing_setup_state(state_path)
        setup_ids = state.get(key, [])
        if setup_id not in setup_ids:
            return
        setup_ids.remove(setup_id)
        if not setup_ids:
            state.pop(key, None)
        _save_swing_setup_state(state_path, state)
