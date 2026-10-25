from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from .errors import ValidationError

LogCallback = Callable[[str, str], None]


@dataclass(frozen=True)
class CookieSourceRevision:
    sha256: str
    size: int
    mtime_ns: int


def default_cookie_session_dir() -> Path:
    """Return an application-owned directory for mutable cookie working jars.

    The user-selected Netscape cookie file is an immutable import source. yt-dlp,
    however, intentionally treats ``cookiefile`` as a read/write cookie jar. The
    mutable jar therefore belongs in application data, not next to the source.
    """
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "NekoDownloader" / "NekoVideoDownloader" / "cookie-sessions"


def _safe_chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        # Windows ACLs are not controlled by POSIX mode bits. Failure to chmod
        # must not make the downloader unusable; the directory still lives under
        # the current user's application-data directory.
        pass


def _source_revision(path: Path) -> CookieSourceRevision:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        stat = path.stat()
    except OSError as exc:
        raise ValidationError(f"Cookie 文件无法读取：{path}（{exc}）") from exc
    return CookieSourceRevision(digest.hexdigest(), stat.st_size, stat.st_mtime_ns)


def _session_key(source: Path) -> str:
    canonical = os.path.normcase(str(source.resolve()))
    return hashlib.sha256(canonical.encode("utf-8", errors="surrogatepass")).hexdigest()[:24]


def _has_netscape_header(path: Path) -> bool:
    try:
        head = path.read_bytes()[:4096].decode("utf-8-sig", errors="replace")
    except OSError:
        return False
    return "Netscape HTTP Cookie File" in head


def validate_netscape_cookie_source(cookie_file: str | Path | None) -> Path | None:
    if cookie_file is None or not str(cookie_file).strip():
        return None
    path = Path(cookie_file).expanduser()
    if not path.exists() or not path.is_file():
        raise ValidationError(f"Cookie 文件不存在：{path}")
    try:
        with path.open("rb") as stream:
            stream.read(1)
    except OSError as exc:
        raise ValidationError(f"Cookie 文件无法读取：{path}（{exc}）") from exc
    if not _has_netscape_header(path):
        raise ValidationError(
            "Cookie 文件不是 yt-dlp 所需的 Netscape cookies.txt 格式："
            f"{path}\n请使用支持导出 Netscape cookies.txt 的工具重新导出。"
        )
    return path.resolve()


class CookieSessionStore:
    """Keep yt-dlp cookie updates without ever mutating the user's source file.

    Lifecycle:
      source cookies.txt (immutable) -> app-owned persistent jar -> per-call temp
      jar -> yt-dlp -> atomically commit the updated temp jar back to app storage.

    If the source file is replaced/re-exported, its hash/size/mtime revision changes
    and the persistent jar is automatically re-seeded from the new source.
    """

    def __init__(self, root: Path | None = None, log_callback: LogCallback | None = None) -> None:
        self.root = (root or default_cookie_session_dir()).expanduser().resolve()
        self.log_callback = log_callback

    def _log(self, level: str, message: str) -> None:
        if self.log_callback:
            self.log_callback(level, message)

    def _paths(self, source: Path) -> tuple[Path, Path, Path]:
        key = _session_key(source)
        return (
            self.root / f"{key}.cookies.txt",
            self.root / f"{key}.json",
            self.root / f"{key}.cookies.bak",
        )

    def _ensure_root(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            _safe_chmod(self.root, 0o700)
        except OSError as exc:
            raise ValidationError(f"无法创建 Cookie 会话目录：{self.root}（{exc}）") from exc

    @staticmethod
    def _read_metadata(meta_path: Path) -> dict:
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}

    def _write_metadata(self, meta_path: Path, source: Path, revision: CookieSourceRevision) -> None:
        payload = {
            "source": str(source),
            "source_revision": asdict(revision),
        }
        self._atomic_write_bytes(meta_path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    def _atomic_write_bytes(self, target: Path, data: bytes) -> None:
        self._ensure_root()
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=self.root)
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            _safe_chmod(tmp, 0o600)
            os.replace(tmp, target)
            _safe_chmod(target, 0o600)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def _atomic_copy(self, source: Path, target: Path) -> None:
        try:
            data = source.read_bytes()
        except OSError as exc:
            raise ValidationError(f"无法读取 Cookie 工作副本：{source}（{exc}）") from exc
        self._atomic_write_bytes(target, data)

    def _ensure_persistent_jar(self, source: Path) -> tuple[Path, Path, Path, CookieSourceRevision]:
        self._ensure_root()
        jar_path, meta_path, backup_path = self._paths(source)
        revision = _source_revision(source)
        metadata = self._read_metadata(meta_path)
        previous_revision = metadata.get("source_revision")
        current_revision = asdict(revision)

        reset_needed = (
            not jar_path.exists()
            or not _has_netscape_header(jar_path)
            or previous_revision != current_revision
        )
        if reset_needed:
            self._atomic_copy(source, jar_path)
            self._write_metadata(meta_path, source, revision)
            self._log("info", "Cookie 会话已从只读源文件初始化；后续更新仅保存在应用工作副本中。")
        else:
            self._log("debug", "继续使用应用维护的 Cookie 会话工作副本。")
        return jar_path, meta_path, backup_path, revision

    @contextmanager
    def runtime_cookie(self, source: Path | None) -> Iterator[Path | None]:
        if source is None:
            yield None
            return

        jar_path, meta_path, backup_path, revision = self._ensure_persistent_jar(source)
        with tempfile.TemporaryDirectory(prefix="neko-cookie-run-") as temp_dir:
            runtime = Path(temp_dir) / "cookies.txt"
            try:
                shutil.copyfile(jar_path, runtime)
                _safe_chmod(runtime, 0o600)
            except OSError as exc:
                raise ValidationError(f"无法创建 Cookie 运行副本：{jar_path}（{exc}）") from exc

            try:
                yield runtime
            except BaseException:
                # Do not commit a possibly half-written jar when extraction or
                # download aborts. The previous persistent jar remains intact.
                raise
            else:
                if not runtime.exists() or not _has_netscape_header(runtime):
                    self._log(
                        "warning",
                        "yt-dlp 返回的 Cookie 工作副本不是有效 Netscape 格式；已保留上一次可用会话副本。",
                    )
                    return
                try:
                    if jar_path.exists():
                        self._atomic_copy(jar_path, backup_path)
                    self._atomic_copy(runtime, jar_path)
                    self._write_metadata(meta_path, source, revision)
                except ValidationError:
                    # Keep the source immutable and preserve the old working jar.
                    raise

    def clear(self, source: Path | None) -> None:
        if source is None:
            return
        jar_path, meta_path, backup_path = self._paths(source)
        for path in (jar_path, meta_path, backup_path):
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                raise ValidationError(f"无法删除 Cookie 会话文件：{path}（{exc}）") from exc
        self._log("info", "已清除该 Cookie 源对应的应用工作会话。")


def clear_cookie_session(cookie_file: str | Path | None, *, root: Path | None = None) -> None:
    if cookie_file is None or not str(cookie_file).strip():
        return
    # Clearing app-owned state must still work if the original export has since
    # been moved/deleted/corrupted. No source-file read is required here.
    source = Path(cookie_file).expanduser().resolve()
    CookieSessionStore(root).clear(source)
