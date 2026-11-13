"""Publish a new result directory only after every write/render step succeeds."""
from contextlib import contextmanager
from pathlib import Path
import tempfile


@contextmanager
def new_output_directory(destination):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(f'Output folder already exists: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.analysis-staging-', dir=destination.parent) as temp:
        staging = Path(temp) / 'results'
        staging.mkdir()
        yield staging
        if destination.exists():
            raise FileExistsError(f'Output folder already exists: {destination}')
        staging.rename(destination)
