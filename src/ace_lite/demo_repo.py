from __future__ import annotations

from pathlib import Path


def seed_demo_repo(*, root: str | Path) -> Path:
    """Create a tiny multi-file repo used by `ace-lite demo`.

    The goal is a deterministic, self-contained repo that exercises common
    queries like "shutdown middleware allowlist blocklist withdraw phase".
    """
    base = Path(root).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {
        "README.md": (
            "# ACE-Lite Demo Repo\n\n"
            "This is a tiny repo for validating retrieval and plan outputs.\n"
        ),
        "app/__init__.py": "",
        "app/shutdown/__init__.py": "",
        "app/shutdown/allowlist.py": (
            "ALLOWLIST = {\n"
            "    \"/health\",\n"
            "    \"/status\",\n"
            "}\n\n"
            "BLOCKLIST = {\n"
            "    \"/admin/danger\",\n"
            "}\n\n"
            "def is_allowed(path: str) -> bool:\n"
            "    return path in ALLOWLIST and path not in BLOCKLIST\n"
        ),
        "app/shutdown/middleware.py": (
            "from __future__ import annotations\n\n"
            "from app.shutdown.allowlist import is_allowed\n"
            "from app.shutdown.phase import shutdown_phase\n\n"
            "def shutdown_middleware(path: str) -> str:\n"
            "    if shutdown_phase() != \"open\" and not is_allowed(path):\n"
            "        return \"blocked\"\n"
            "    return \"ok\"\n"
        ),
        "app/shutdown/phase.py": (
            "from __future__ import annotations\n\n"
            "def shutdown_phase() -> str:\n"
            "    # demo: always open\n"
            "    return \"open\"\n"
        ),
        "app/handlers/__init__.py": "",
        "app/handlers/withdraw.py": (
            "from __future__ import annotations\n\n"
            "def handle_withdraw(user_id: str, amount: int) -> dict:\n"
            "    if amount <= 0:\n"
            "        return {\"ok\": False, \"error\": \"invalid_amount\"}\n"
            "    return {\"ok\": True, \"user_id\": user_id, \"amount\": amount}\n"
        ),
    }

    for rel, content in files.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return base


__all__ = ["seed_demo_repo"]

