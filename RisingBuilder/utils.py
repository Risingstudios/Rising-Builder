import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_CANDIDATE_FILES = [
    Path("codexes") / "eldar_5e.json",
    Path("codexes") / "eldar 5e.json",
]

def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\s_]+", "", text)
    text = re.sub(r"\s+", "_", text)
    return text or "item"

def ensure_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def lines_to_list(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]

def list_to_lines(items: List[str]) -> str:
    return "\n".join(items)

def find_default_codex_file() -> Optional[Path]:
    for p in DEFAULT_CANDIDATE_FILES:
        if p.exists():
            return p
    codex_dir = Path("codexes")
    if codex_dir.exists():
        any_json = sorted(codex_dir.glob("*.json"))
        if any_json:
            return any_json[0]
    return None

def make_backup(original_path: Path) -> None:
    if not original_path.exists():
        return
    backup_dir = original_path.parent / "backups"
    ensure_folder(backup_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{original_path.stem}_{stamp}.json"
    backup_path.write_text(original_path.read_text(encoding="utf-8-sig"), encoding="utf-8")

def unique_id(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"