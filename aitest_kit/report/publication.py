"""Publish reports with result.json as the commit marker."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import tempfile

from .renderer import render_markdown


@contextmanager
def report_lock(bucket):
    bucket.mkdir(parents=True, exist_ok=True)
    with (bucket / ".report.lock").open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


def atomic_write(path, data):
    _replace_file(path, lambda stream: stream.write(data))


def _replace_file(path, write):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".writing-", delete=False) as stream:
        temp = Path(stream.name)
        try:
            write(stream)
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)


def write_report(directory, result, junit=None):
    if junit is not None:
        atomic_write(directory / "junit.xml", junit)
    atomic_write(directory / "report.md", render_markdown(result).encode("utf-8"))
    atomic_write(directory / "result.json", json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"))


def latest_directory(bucket):
    latest = bucket / "latest"
    previous = bucket / ".latest-previous"
    return previous if not latest.exists() and previous.exists() else latest


def update_latest(directory, bucket, result):
    latest = bucket / "latest"
    previous = bucket / ".latest-previous"
    if not latest.exists() and previous.exists():
        os.rename(previous, latest)
    marker = latest / "result.json"
    if marker.exists():
        old_id = json.loads(marker.read_text(encoding="utf-8")).get("run_id", "")
        if old_id > result["run_id"]:
            return
    with tempfile.TemporaryDirectory(dir=bucket, prefix=".report-stage-") as staging:
        snapshot = Path(staging) / "snapshot"
        shutil.copytree(directory, snapshot, ignore=shutil.ignore_patterns(".writing-*"))
        if previous.exists():
            shutil.rmtree(previous)
        if latest.exists():
            os.rename(latest, previous)
        try:
            os.replace(snapshot, latest)
        except OSError:
            if previous.exists():
                os.rename(previous, latest)
            raise
        if previous.exists():
            shutil.rmtree(previous)
