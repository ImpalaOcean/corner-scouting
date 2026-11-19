"""Run publication and provenance shared by the systems commands."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def environment():
    import duckdb
    def git(*args):
        return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()
    try:
        commit, dirty = git('rev-parse', 'HEAD'), bool(git('status', '--porcelain'))
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    sources = [*(ROOT / 'src').rglob('*.py'), *Path(__file__).parent.glob('*.sql'),
               Path(__file__).parent / 'requirements.txt']
    return dict(python=sys.version, duckdb=duckdb.__version__, os=platform.platform(),
                processor=platform.processor(), logical_cpus=os.cpu_count(),
                repository_commit=commit, working_tree_dirty=dirty,
                code_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in sources})


@contextmanager
def new_directory(destination):
    """A sibling staging directory keeps manifest-relative paths valid on rename."""
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(f'Output exists; choose a new directory: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.systems-run-', dir=destination.parent))
    try:
        yield stage
        if destination.exists():
            raise FileExistsError(f'Output appeared during run: {destination}')
        stage.rename(destination)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
