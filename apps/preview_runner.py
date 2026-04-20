from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8011)
    parser.add_argument("--root", default="Si")
    parser.add_argument("--skip-warmup", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    preview_root = Path(tempfile.gettempdir()) / f"imoex-preview-{args.port}"
    database_path = preview_root / "preview.db"
    backups_path = preview_root / "backups"
    server_pid_path = preview_root / "server.pid"

    preview_root.mkdir(parents=True, exist_ok=True)
    backups_path.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    pythonpath_parts = [str(repo_root / ".vendor"), str(repo_root)]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    env["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    env["BACKUPS_DIR"] = str(backups_path)

    if not args.skip_warmup:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "apps.worker.runner",
                "recalculate",
                "--root",
                args.root,
            ],
            cwd=repo_root,
            env=env,
            check=True,
        )

    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
            "--no-access-log",
        ],
        cwd=repo_root,
        env=env,
    )
    server_pid_path.write_text(str(child.pid), encoding="utf-8")
    try:
        return child.wait()
    except KeyboardInterrupt:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=10)
        return 130
    finally:
        if server_pid_path.exists() and child.poll() is not None:
            server_pid_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
