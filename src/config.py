"""설정 파일 입출력.

JSON 스키마:
{
  "click_positions": [[x, y], ...],
  "comment_text": "...",
  "target_time_kst": "2026-04-23 20:00:00",
  "submit_with_enter": true,
  "step_delay_seconds": 0.25
}
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class MacroConfig:
    click_positions: list[tuple[int, int]] = field(default_factory=list)
    comment_text: str = ""
    target_time_kst: str = ""  # "YYYY-MM-DD HH:MM:SS"
    submit_with_enter: bool = True
    step_delay_seconds: float = 0.25
    window_title_contains: str = "카카오톡"

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> "MacroConfig":
        raw = json.loads(path.read_text(encoding="utf-8"))
        positions = [tuple(p) for p in raw.get("click_positions", [])]
        return cls(
            click_positions=positions,
            comment_text=raw.get("comment_text", ""),
            target_time_kst=raw.get("target_time_kst", ""),
            submit_with_enter=raw.get("submit_with_enter", True),
            step_delay_seconds=raw.get("step_delay_seconds", 0.25),
            window_title_contains=raw.get("window_title_contains", "카카오톡"),
        )
