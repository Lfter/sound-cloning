from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def command_version(command: str, env: dict[str, str] | None = None) -> str:
    if shutil.which(command) is None:
        return "missing"
    try:
        result = subprocess.run([command, "--version"], check=False, capture_output=True, text=True, env=env)
        return (result.stdout or result.stderr).splitlines()[0]
    except OSError:
        return "missing"


def module_status(module: str, python: Path | None = None) -> str:
    if python is None:
        return "ok" if importlib.util.find_spec(module) else "missing"
    result = subprocess.run(
        [str(python), "-c", f"import importlib.util; raise SystemExit(0 if importlib.util.find_spec('{module}') else 1)"],
        check=False,
        capture_output=True,
        text=True,
    )
    return "ok" if result.returncode == 0 else "missing"


def main() -> None:
    local_npm = ROOT / "scripts" / "npm-local.sh"
    local_node = ROOT / ".tools" / "node-v24.15.0-darwin-arm64" / "bin" / "node"
    local_cargo = ROOT / ".cargo" / "bin" / "cargo"
    local_ffmpeg = ROOT / ".venv" / "bin" / "ffmpeg"
    venv_python = ROOT / ".venv" / "bin" / "python"
    rust_env = {
        **os.environ,
        "CARGO_HOME": str(ROOT / ".cargo"),
        "RUSTUP_HOME": str(ROOT / ".rustup"),
    }
    print("Voice Patch Studio environment")
    print(f"python: {command_version('python3')}")
    print(f"venv python: {command_version(str(venv_python))}")
    print(f"node: {command_version('node')}")
    print(f"local node: {command_version(str(local_node))}")
    print(f"npm: {command_version('npm')}")
    print(f"local npm: {command_version(str(local_npm))}")
    print(f"cargo: {command_version('cargo')}")
    print(f"local cargo: {command_version(str(local_cargo), env=rust_env)}")
    print(f"ffmpeg: {command_version('ffmpeg')}")
    print(f"local ffmpeg: {command_version(str(local_ffmpeg))}")
    print(f"fastapi: {module_status('fastapi', venv_python)}")
    print(f"uvicorn: {module_status('uvicorn', venv_python)}")
    print(f"mlx_audio: {module_status('mlx_audio', venv_python)}")
    print(f"models dir: {(Path.cwd() / 'models').resolve()}")


if __name__ == "__main__":
    main()
