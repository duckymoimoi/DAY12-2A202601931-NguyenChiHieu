#!/usr/bin/env python3
"""Chấm điểm tự động — K3 Ngày 12: Hạ Tầng Cloud & Deployment.

Cách dùng (chạy từ thư mục gốc của repo):
    python grade.py

Cách tính điểm (tổng 100):
    - 5 checkpoint (85đ): điểm mỗi checkpoint = số test pass / tổng test × điểm
    - exercises.md (15đ): điểm = số câu đã trả lời / tổng số câu × 15

Quy ước riêng:
    - CP5 dùng phương án dự phòng (LOCAL_FALLBACK=true) chỉ được tối đa 60%
      số điểm của checkpoint đó.
    - Test bị skip (ví dụ máy chưa bật Docker) KHÔNG bị tính là rớt, nhưng
      cũng không được cộng điểm — phần điểm đó chia đều cho các test còn lại.

"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent

# (mã, tên hiển thị, args pytest, điểm tối đa)
CHECKPOINTS = [
    ("CP1", "12-Factor Config, Health & Logging", ["tests/test_cp1.py"], 15),
    ("CP2", "Docker: multi-stage, bảo mật image", ["tests/test_cp2.py"], 15),
    ("CP3", "API Security: auth, rate limit, cost guard", ["tests/test_cp3.py"], 20),
    ("CP4", "Scaling & Reliability: stateless, probe, shutdown", ["tests/test_cp4.py"], 20),
    ("CP5", "Cloud Deployment: service chạy thật", ["tests/test_cp5.py"], 15),
]

EXERCISES_POINTS = 15
PLACEHOLDER = "> *Câu trả lời của bạn*"
TOTAL_QUESTIONS = 10

FALLBACK_MAX_RATIO = 0.6

class _Collector:
    """Plugin pytest đếm kết quả một lần chạy."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            if report.passed:
                self.passed += 1
            elif report.failed:
                self.failed += 1
            elif report.skipped:
                self.skipped += 1
        elif report.failed:
            # Lỗi ngay ở setup (ví dụ file không import được) → tính là rớt
            self.failed += 1
        elif report.skipped and report.when == "setup":
            self.skipped += 1


def run_checkpoint(args: list[str]) -> _Collector:
    resolved = [str(ROOT / arg) if arg.startswith("tests/") else arg for arg in args]
    collector = _Collector()
    pytest.main(
        resolved + ["-q", "--tb=no", "--no-header", "-p", "no:cacheprovider"],
        plugins=[collector],
    )
    return collector


def fallback_mode() -> bool:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    return os.getenv("LOCAL_FALLBACK", "false").strip().lower() in ("1", "true", "yes")


def grade_exercises() -> tuple[int, Path | None]:
    path = ROOT / "exercises.md"
    if not path.exists():
        return 0, None
    remaining = path.read_text(encoding="utf-8").count(PLACEHOLDER)
    return max(0, TOTAL_QUESTIONS - remaining), path


def main() -> int:
    print("=" * 74)
    print("CHẤM ĐIỂM TỰ ĐỘNG — K3 Ngày 12: Hạ Tầng Cloud & Deployment")
    print("=" * 74)

    rows = []
    notes = []

    for code, name, args, max_points in CHECKPOINTS:
        print(f"\n>>> {code} — {name}")
        result = run_checkpoint(args)
        counted = result.passed + result.failed
        score = round(max_points * result.passed / counted, 1) if counted else 0.0

        if code == "CP5" and fallback_mode():
            capped = round(min(score, max_points * FALLBACK_MAX_RATIO), 1)
            if capped < score:
                notes.append(
                    f"CP5 dùng phương án dự phòng (LOCAL_FALLBACK=true) → "
                    f"trần điểm {max_points * FALLBACK_MAX_RATIO:.0f}/{max_points}"
                )
            score = capped

        detail = f"{result.passed}/{counted} test"
        if result.skipped:
            detail += f" ({result.skipped} bỏ qua)"
        rows.append((f"{code} — {name}", detail, score, max_points))

    answered, path = grade_exercises()
    ex_score = round(EXERCISES_POINTS * answered / TOTAL_QUESTIONS, 1)
    ex_detail = (
        f"{answered}/{TOTAL_QUESTIONS} câu" if path else "không tìm thấy exercises.md"
    )
    rows.append(("Exercises — câu hỏi phản ánh", ex_detail, ex_score, EXERCISES_POINTS))

    print("\n" + "=" * 74)
    print("BẢNG ĐIỂM")
    print("=" * 74)
    total = 0.0
    for name, detail, score, max_points in rows:
        total += score
        print(f"  {name:<48} {detail:<20} {score:>5.1f}/{max_points}")
    print("-" * 74)
    print(f"  {'Tổng điểm':<48} {'':<20} {round(total, 1):>5.1f}/100")
    print("=" * 74)

    for note in notes:
        print(f"  ⚠  {note}")

    if total >= 90:
        print("\n  Xuất sắc. Service của bạn đã đạt chuẩn production.")
    elif total >= 75:
        print("\n  Đạt yêu cầu. Xem lại các test còn rớt để hoàn thiện nốt.")
    elif total >= 50:
        print("\n  Còn thiếu khá nhiều — chạy `pytest tests/test_cpN.py -v` để xem chi tiết.")
    else:
        print("\n  Mới bắt đầu. Làm tuần tự CP1 → CP5, đừng nhảy cóc.")

    print(
        "\nGhi chú: điểm exercises là điểm hoàn thành — chất lượng nội dung\n"
        "sẽ được giảng viên chấm lại thủ công."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
