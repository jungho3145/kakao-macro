"""설정 파일 입출력.

JSON 스키마:
{
  "click_positions": [[x, y], ...],          # 댓글 입력창까지 이동하기 위한 클릭들
  "comment_text": "...",                     # 댓글 본문
  "target_time_kst": "2026-04-23 20:00:00",  # 한국 시간 기준 등록 시각
  "submit_button_position": [x, y],          # 등록 버튼 좌표 (없으면 null)
  "submit_with_enter": true,                 # 버튼 좌표 없을 때 폴백
  "step_delay_seconds": 0.25,
  "window_title_contains": "카카오톡"
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
    target_time_kst: str = ""
    submit_button_position: tuple[int, int] | None = None
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
        submit_pos_raw = raw.get("submit_button_position")
        submit_pos = tuple(submit_pos_raw) if submit_pos_raw else None
        return cls(
            click_positions=positions,
            comment_text=raw.get("comment_text", ""),
            target_time_kst=raw.get("target_time_kst", ""),
            submit_button_position=submit_pos,
            submit_with_enter=raw.get("submit_with_enter", True),
            step_delay_seconds=raw.get("step_delay_seconds", 0.25),
            window_title_contains=raw.get("window_title_contains", "카카오톡"),
        )
