#!/usr/bin/env python3
"""Seed historical QuestionnaireResponse records for all scenarios.

Creates realistic past responses spread across the last 90 days so the app
has data to display in the questionnaire history.

Usage:
    uv run python scripts/seed_questionnaire.py --user EMAIL
    uv run python scripts/seed_questionnaire.py --user EMAIL --days 90
"""
import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.questionnaire_response import QuestionnaireResponse
from app.models.user import User

# ---------------------------------------------------------------------------
# Mock answers per scenario
# ---------------------------------------------------------------------------

_ANSWERS: dict[str, list[list[dict]]] = {
    "hrv_drop": [
        [
            {"id": "hrv_drop_energy",     "answer": "2"},
            {"id": "hrv_drop_stress",     "answer": "ใช่ มีงานด่วนที่ต้องส่งวันนี้"},
            {"id": "hrv_drop_sleep_feel", "answer": "ตื่นมายังรู้สึกง่วงและหนักหัว"},
            {"id": "hrv_drop_cause",      "answer": "งานและความเครียดสะสม"},
        ],
        [
            {"id": "hrv_drop_energy",     "answer": "1"},
            {"id": "hrv_drop_stress",     "answer": "ใช่ กังวลเรื่องสุขภาพของคนในครอบครัว"},
            {"id": "hrv_drop_sleep_feel", "answer": "นอนหลับได้แค่ 4 ชั่วโมง"},
            {"id": "hrv_drop_cause",      "answer": "ความกังวลและนอนไม่หลับ"},
        ],
        [
            {"id": "hrv_drop_energy",     "answer": "2"},
            {"id": "hrv_drop_stress",     "answer": "มีการประชุมสำคัญหลายรายการ"},
            {"id": "hrv_drop_sleep_feel", "answer": "หลับไม่สนิท ตื่นบ่อย"},
            {"id": "hrv_drop_cause",      "answer": "ความเครียดจากงาน"},
        ],
    ],
    "elevated_arousal": [
        [
            {"id": "arousal_situation", "answer": "ใช่ มีการประชุมสำคัญและเส้นตายงาน"},
            {"id": "arousal_body",      "answer": "หัวใจเต้นเร็ว หายใจตื้น และรู้สึกเกร็งที่ไหล่"},
            {"id": "arousal_coping",    "answer": "ลองหายใจลึกๆ และฟังเพลงผ่อนคลาย"},
        ],
        [
            {"id": "arousal_situation", "answer": "ขัดแย้งกับเพื่อนร่วมงาน ทำให้รู้สึกกังวล"},
            {"id": "arousal_body",      "answer": "รู้สึกปวดหัว และมือสั่นเล็กน้อย"},
            {"id": "arousal_coping",    "answer": "คุยกับเพื่อนสนิทและเดินเล่นพักสมอง"},
        ],
        [
            {"id": "arousal_situation", "answer": "เพิ่งได้รับข่าวไม่ดี ใจยังไม่สงบ"},
            {"id": "arousal_body",      "answer": "แน่นหน้าอก และนั่งไม่ค่อยติด"},
            {"id": "arousal_coping",    "answer": "นั่งสมาธิ 10 นาที ช่วยได้บ้าง"},
        ],
    ],
    "poor_sleep": [
        [
            {"id": "sleep_quality",    "answer": "ยังง่วงและเหนื่อย ไม่สดชื่นเลย"},
            {"id": "sleep_disruption", "answer": "ใช่ ตื่นกลางดึก 2-3 ครั้ง คิดเรื่องงานตลอด"},
            {"id": "sleep_plan",       "answer": "จะพยายามงีบกลางวัน และเข้านอนเร็วขึ้นคืนนี้"},
        ],
        [
            {"id": "sleep_quality",    "answer": "ง่วงมาก อยากนอนต่ออีกหลายชั่วโมง"},
            {"id": "sleep_disruption", "answer": "ดูหนังดึกเกินไป เลยนอนน้อย"},
            {"id": "sleep_plan",       "answer": "ตั้งใจเข้านอนก่อน 22.00 คืนนี้"},
        ],
        [
            {"id": "sleep_quality",    "answer": "รู้สึกหนักหัว ตาแฉะ"},
            {"id": "sleep_disruption", "answer": "ลูกร้องกลางดึก ทำให้ตื่นบ่อย"},
            {"id": "sleep_plan",       "answer": "ยังไม่แน่ใจ แต่จะพยายามพัก"},
        ],
    ],
    "post_workout": [
        [
            {"id": "workout_feel",     "answer": "ดีมาก รู้สึกสดชื่นและมีพลังหลังออกกำลังกาย"},
            {"id": "workout_intensity","answer": "พอดีสำหรับวันนี้ ไม่หนักเกินไป"},
            {"id": "workout_recovery", "answer": "กล้ามเนื้อขาล้าเล็กน้อย แต่โดยรวมโอเค"},
        ],
        [
            {"id": "workout_feel",     "answer": "เหนื่อยมากในช่วงแรก แต่ตอนหลังดีขึ้น"},
            {"id": "workout_intensity","answer": "หนักกว่าปกติ แต่ยังรับได้"},
            {"id": "workout_recovery", "answer": "ไหล่และหลังตึงหน่อย จะนวดคืนนี้"},
        ],
        [
            {"id": "workout_feel",     "answer": "สนุกมาก ได้เพื่อนชวนวิ่งด้วยกัน"},
            {"id": "workout_intensity","answer": "เบาพอดี วันนี้แค่อยากขยับร่างกาย"},
            {"id": "workout_recovery", "answer": "ไม่มีอาการเจ็บ รู้สึกดีมาก"},
        ],
    ],
    "streak_risk": [
        [
            {"id": "streak_motivation", "answer": "รู้สึกขาดแรงจูงใจช่วงนี้ งานยุ่งมาก"},
            {"id": "streak_barrier",    "answer": "ตารางงานแน่นและเหนื่อยเกินไปจนไม่อยากทำอะไรเพิ่ม"},
            {"id": "streak_support",    "answer": "อยากได้การแจ้งเตือนเบาๆ และเป้าหมายที่ทำได้จริง"},
        ],
        [
            {"id": "streak_motivation", "answer": "ช่วงนี้ไม่ค่อยมีเวลาให้ตัวเอง"},
            {"id": "streak_barrier",    "answer": "ดูแลพ่อแม่ที่ป่วย เลยหมดแรงตอนกลางคืน"},
            {"id": "streak_support",    "answer": "แค่ 5 นาทีต่อวันก็พอ อยากทำอะไรง่ายๆ"},
        ],
    ],
    "rops": [
        [
            {"id": "rops_sleep",       "answer": "ใช่"},
            {"id": "rops_fedup",       "answer": "ใช่"},
            {"id": "rops_tired",       "answer": "ใช่"},
            {"id": "rops_mental_help", "answer": "ไม่"},
            {"id": "rops_life_stress", "answer": "ใช่"},
            {"id": "rops_bmi",         "answer": "ไม่"},
        ],
        [
            {"id": "rops_sleep",       "answer": "ใช่"},
            {"id": "rops_fedup",       "answer": "ไม่"},
            {"id": "rops_tired",       "answer": "ใช่"},
            {"id": "rops_mental_help", "answer": "ใช่"},
            {"id": "rops_life_stress", "answer": "ไม่"},
            {"id": "rops_bmi",         "answer": "ไม่"},
        ],
    ],
    "baseline": [
        [
            {"id": "baseline_mood",      "answer": "4"},
            {"id": "baseline_energy",    "answer": "ใช่ มีพลังงานพอสมควรสำหรับวันนี้"},
            {"id": "baseline_highlight", "answer": "ได้กินอาหารอร่อยและนอนหลับพักผ่อนดี"},
        ],
        [
            {"id": "baseline_mood",      "answer": "5"},
            {"id": "baseline_energy",    "answer": "มีพลังงานมาก รู้สึกดีมากวันนี้"},
            {"id": "baseline_highlight", "answer": "เสร็จงานสำคัญ และได้ออกกำลังกายตอนเช้า"},
        ],
        [
            {"id": "baseline_mood",      "answer": "3"},
            {"id": "baseline_energy",    "answer": "พอไหว ไม่มากไม่น้อย"},
            {"id": "baseline_highlight", "answer": "ได้คุยกับครอบครัว รู้สึกดีขึ้น"},
        ],
        [
            {"id": "baseline_mood",      "answer": "4"},
            {"id": "baseline_energy",    "answer": "ใช่ วันนี้รู้สึกสดใส"},
            {"id": "baseline_highlight", "answer": "อากาศดี ได้เดินเล่นตอนเช้า"},
        ],
    ],
}

# How many times each scenario appears across 90 days
_SCENARIO_DISTRIBUTION = [
    ("baseline",         35),
    ("post_workout",     18),
    ("poor_sleep",        8),
    ("elevated_arousal",  7),
    ("hrv_drop",          6),
    ("streak_risk",       4),
    ("rops",              2),
]


def _pick_answers(scenario: str) -> list[dict]:
    pool = _ANSWERS.get(scenario, [])
    if not pool:
        return []
    return random.choice(pool)


def _compute_rops_score(answers: list[dict]) -> dict:
    yes_ids = {"rops_sleep", "rops_fedup", "rops_tired", "rops_mental_help", "rops_life_stress", "rops_bmi"}
    score = sum(1 for a in answers if a.get("id") in yes_ids and str(a.get("answer", "")).lower() in ("yes", "ใช่", "1", "true"))
    risk = "low" if score <= 2 else ("moderate" if score <= 4 else "high")
    return {"rops_score": score, "rops_risk": risk}


def seed_questionnaire_history(db, user_id, days: int = 90) -> int:
    today = date.today()

    # Build list of (date, scenario) pairs — work backwards from today
    schedule: list[tuple[date, str]] = []
    available_dates = list(range(1, days + 1))  # days ago
    random.shuffle(available_dates)

    idx = 0
    for scenario, count in _SCENARIO_DISTRIBUTION:
        for _ in range(count):
            if idx >= len(available_dates):
                break
            d = today - timedelta(days=available_dates[idx])
            schedule.append((d, scenario))
            idx += 1

    schedule.sort(key=lambda x: x[0])

    inserted = 0
    for response_date, scenario in schedule:
        existing = db.execute(
            select(QuestionnaireResponse).where(
                QuestionnaireResponse.user_id == user_id,
                QuestionnaireResponse.date == response_date,
            )
        ).scalar_one_or_none()
        if existing:
            continue

        answers = _pick_answers(scenario)
        context: dict = {"seeded": True}
        if scenario == "rops":
            context.update(_compute_rops_score(answers))

        db.add(QuestionnaireResponse(
            id=uuid4(),
            user_id=user_id,
            date=response_date,
            scenario=scenario,
            answers=answers,
            context_snapshot=context,
        ))
        try:
            db.flush()
            inserted += 1
        except IntegrityError:
            db.rollback()

    db.commit()
    return inserted


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user", metavar="EMAIL", required=True)
    parser.add_argument("--days", type=int, default=90, help="How many days of history to seed (default: 90)")
    args = parser.parse_args()

    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == args.user)).scalar_one_or_none()
        if not user:
            sys.exit(f"User not found: {args.user}")

        print(f"Seeding questionnaire history for {args.user} ({args.days} days)…")
        n = seed_questionnaire_history(db, user.id, args.days)
        print(f"Inserted {n} questionnaire responses across all scenarios.")


if __name__ == "__main__":
    main()
