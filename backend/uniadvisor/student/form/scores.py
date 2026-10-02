"""A subject's score from what the student gives: an exact score, a range, or a self-rated level.

Toán is graded in steps of 0.05, the other subjects in steps of 0.25. An exact score off its step is rejected; a range
becomes its midpoint rounded down to the step; a level becomes its fixed value (options.LEVELS). Only exact scores the
student says are official make the profile's `score_kind` "actual".
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from uniadvisor.student.form.options import LEVELS, SUBJECTS

MODES = {"exact": "Điểm chính xác", "range": "Khoảng điểm", "level": "Mức học"}


def step(subject: str) -> float:
    return 0.05 if subject == "TO" else 0.25


def on_step(value: float, subject: str) -> bool:
    k = value / step(subject)
    return abs(k - round(k)) < 1e-6


def floor_to_step(value: float, subject: str) -> float:
    s = step(subject)
    return round(math.floor(value / s + 1e-6) * s, 2)


@dataclass(frozen=True)
class ScoreEntry:
    """What the student entered for one subject. `mode` is a key of MODES; only that mode's fields are read."""

    subject: str
    mode: str = "exact"
    value: float | None = None       # exact
    low: float | None = None         # range
    high: float | None = None
    level: str | None = None         # a key of LEVELS

    def problem(self) -> str | None:
        """Why this entry cannot be turned into a score (Vietnamese, shown to the student), or None."""
        name = SUBJECTS.get(self.subject)
        if name is None:
            return "Môn học không hợp lệ."
        if self.mode == "exact":
            if self.value is None:
                return f"Em chưa nhập điểm {name}."
            if not 0 <= self.value <= 10:
                return f"Điểm {name} phải từ 0 đến 10."
            if not on_step(self.value, self.subject):
                return f"Điểm {name} phải là bội của {vn_number(step(self.subject))}, ví dụ {vn_number(floor_to_step(self.value, self.subject))}."
            return None
        if self.mode == "range":
            if self.low is None or self.high is None:
                return f"Em nhập đủ hai đầu khoảng điểm {name} nhé."
            if not 0 <= self.low <= self.high <= 10:
                return f"Khoảng điểm {name} phải nằm trong 0-10, số đầu không lớn hơn số sau."
            return None
        if self.mode == "level":
            return None if self.level in LEVELS else f"Em chọn mức học môn {name} nhé."
        return "Cách nhập điểm không hợp lệ."

    def score(self) -> float:
        """The score written to the JSON. Call only when problem() is None."""
        if self.mode == "exact":
            return round(float(self.value), 2)
        if self.mode == "range":
            return floor_to_step((self.low + self.high) / 2, self.subject)
        return LEVELS[self.level][1]


def vn_number(x: float) -> str:
    """A number the Vietnamese way: 7.75 -> "7,75", 8.0 -> "8"."""
    return f"{x:g}".replace(".", ",")

