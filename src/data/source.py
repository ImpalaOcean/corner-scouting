"""Pinned JSON downloads with checksummed caching and offline replay."""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class DataError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def json_bytes(value):
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary = tempfile.mkstemp(
        prefix=".ingest-",
        dir=path.parent,
    )

    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)

        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def decode_json(raw):
    def invalid_constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    try:
        return json.loads(
            raw.decode("utf-8-sig"),
            parse_constant=invalid_constant,
        )
    except (UnicodeError, ValueError) as exc:
        raise DataError(
            "invalid_json",
            "Not valid UTF-8 JSON",
        ) from exc


@dataclass(frozen=True)
class Document:
    value: object
    path: Path
    sha256: str


class JsonSource:
    """Store exact provider bytes under cache/<commit>/data/..."""

    def __init__(
        self,
        revision,
        cache,
        *,
        offline=False,
        source_dir=None,
        timeout=60,
        retries=2,
        opener=None,
        sleeper=time.sleep,
    ):
        if not isinstance(revision, str) or not re.fullmatch(
            r"[0-9a-f]{40}", revision
        ):
            raise ValueError(
                "source_revision must be a full lowercase "
                "40-character commit SHA"
            )

        self.revision = revision
        self.cache = Path(cache).resolve() / revision
        self.offline = offline
        self.source_dir = (
            Path(source_dir).resolve() if source_dir else None
        )
        self.timeout = timeout
        self.retries = retries
        self.opener = opener or urlopen
        self.sleeper = sleeper
        self.verification = "pinned_github_url"

        if self.source_dir:
            self.verification = self._verify_local()

    def _verify_local(self):
        try:
            root = subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(self.source_dir),
                    "rev-parse",
                    "--show-toplevel",
                ],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()

            if Path(root).resolve() == self.source_dir:
                head = subprocess.check_output(
                    ["git", "-C", root, "rev-parse", "HEAD"],
                    text=True,
                ).strip()

                dirty = subprocess.check_output(
                    [
                        "git",
                        "-C",
                        root,
                        "status",
                        "--porcelain",
                        "--untracked-files=all",
                        "--",
                        "data",
                    ],
                    text=True,
                ).strip()

                if head != self.revision or dirty:
                    raise ValueError(
                        "Local checkout must be at the configured "
                        "revision with clean data/"
                    )

                return "clean_local_git_checkout"

        except (OSError, subprocess.CalledProcessError):
            pass

        marker = self.source_dir / "SOURCE_REVISION"

        if (
            not marker.is_file()
            or marker.read_text().strip() != self.revision
        ):
            raise ValueError(
                "A local export requires SOURCE_REVISION "
                "containing the configured SHA"
            )

        return "declared_local_export"

    def _download(self, path):
        if self.source_dir:
            try:
                return (self.source_dir / path).read_bytes()
            except FileNotFoundError as exc:
                raise DataError(
                    "missing",
                    f"Missing source file: {path}",
                ) from exc
            except OSError as exc:
                raise DataError(
                    "read_error",
                    f"Cannot read source file: {path}",
                ) from exc

        if self.offline:
            raise DataError(
                "not_cached",
                f"Not cached: {path}",
            )

        url = (
            "https://raw.githubusercontent.com/hudl/open-data/"
            f"{self.revision}/{path}"
        )

        for attempt in range(self.retries + 1):
            try:
                request = Request(
                    url,
                    headers={
                        "User-Agent": "corner-scouting-data/1.0"
                    },
                )

                with self.opener(
                    request,
                    timeout=self.timeout,
                ) as response:
                    return response.read()

            except HTTPError as exc:
                exc.close()
                if exc.code == 404:
                    raise DataError(
                        "missing",
                        f"Missing source file: {path}",
                    ) from exc

                if exc.code != 429 and exc.code < 500:
                    raise DataError(
                        "http_error",
                        f"HTTP {exc.code}: {path}",
                    ) from exc

                if attempt == self.retries:
                    raise DataError(
                        "http_error",
                        f"HTTP {exc.code}: {path}",
                    ) from exc

            except (URLError, TimeoutError, OSError) as exc:
                if attempt == self.retries:
                    raise DataError(
                        "network_error",
                        f"Download failed: {path}",
                    ) from exc

            self.sleeper(min(2 ** attempt, 8))

    def get(self, relative):
        path = PurePosixPath(relative)

        if (
            path.is_absolute()
            or ".." in path.parts
            or not path.parts
            or path.parts[0] != "data"
        ):
            raise ValueError(
                "Source path must be relative and inside data/"
            )

        target = self.cache.joinpath(*path.parts)
        receipt = target.with_suffix(
            target.suffix + ".sha256.json"
        )
        missing = target.with_suffix(
            target.suffix + ".missing.json"
        )

        if not target.exists() and missing.exists():
            try:
                expected_missing = {
                    "source_revision": self.revision,
                    "path": str(path),
                }

                if json.loads(
                    missing.read_text()
                ) != expected_missing:
                    raise ValueError(
                        "Invalid missing-file receipt"
                    )

                raise DataError(
                    "missing",
                    f"Missing source file: {path}",
                )

            except (OSError, ValueError) as exc:
                if isinstance(exc, DataError):
                    raise

                if self.offline and not self.source_dir:
                    raise DataError(
                        "corrupt_cache",
                        f"Invalid missing-file receipt: {relative}",
                    ) from exc

        if target.exists() or receipt.exists():
            try:
                raw = target.read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                expected = json.loads(receipt.read_text())

                if expected != {
                    "sha256": digest,
                    "source_revision": self.revision,
                }:
                    raise ValueError(
                        "Cache checksum mismatch"
                    )

                return Document(
                    decode_json(raw),
                    target,
                    digest,
                )

            except (OSError, ValueError, DataError) as exc:
                if self.offline and not self.source_dir:
                    raise DataError(
                        "corrupt_cache",
                        f"Invalid cached file: {relative}",
                    ) from exc

        try:
            raw = self._download(str(path))
        except DataError as exc:
            if exc.status == "missing" and not self.source_dir:
                atomic_write(
                    missing,
                    json_bytes(
                        {
                            "source_revision": self.revision,
                            "path": str(path),
                        }
                    ),
                )
            raise

        value = decode_json(raw)
        digest = hashlib.sha256(raw).hexdigest()

        atomic_write(target, raw)
        atomic_write(
            receipt,
            json_bytes(
                {
                    "sha256": digest,
                    "source_revision": self.revision,
                }
            ),
        )

        return Document(value, target, digest)