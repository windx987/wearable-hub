from typing import TypedDict


class Question(TypedDict):
    id: str
    text: str


SCENARIO_QUESTIONS: dict[str, list[Question]] = {
    "hrv_drop": [
        {"id": "hrv_drop_energy", "text": "วันนี้คุณรู้สึกมีแรงงานแค่ไหน? (1 = ไม่มีแรงเลย, 5 = มีแรงมาก)"},
        {"id": "hrv_drop_stress", "text": "มีเรื่องกดดันหรือเครียดอะไรที่กำลังเผชิญอยู่ไหม?"},
        {"id": "hrv_drop_sleep_feel", "text": "คืนที่แล้วนอนหลับพักผ่อนได้ดีแค่ไหน?"},
        {"id": "hrv_drop_cause", "text": "คิดว่าร่างกายตื่นตัวสูงเพราะอะไร? (เช่น งาน, ความสัมพันธ์, สุขภาพ)"},
    ],
    "post_workout": [
        {"id": "workout_feel", "text": "รู้สึกอย่างไรระหว่างและหลังออกกำลังกาย?"},
        {"id": "workout_intensity", "text": "หนักเกินไปหรือพอดีสำหรับวันนี้?"},
        {"id": "workout_recovery", "text": "กล้ามเนื้อหรือร่างกายมีอาการเจ็บหรือล้าไหม?"},
    ],
    "poor_sleep": [
        {"id": "sleep_quality", "text": "ตื่นนอนมารู้สึกอย่างไร? สดชื่นหรือยังง่วงอยู่?"},
        {"id": "sleep_disruption", "text": "มีอะไรที่ทำให้นอนไม่หลับหรือหลับไม่สนิทคืนนี้ไหม?"},
        {"id": "sleep_plan", "text": "วันนี้มีแผนจะพักผ่อนหรือลดภาระงานไหม?"},
    ],
    "elevated_arousal": [
        {"id": "arousal_situation", "text": "มีสถานการณ์อะไรที่ทำให้คุณรู้สึกตึงเครียดหรือกระวนกระวายในช่วงนี้ไหม?"},
        {"id": "arousal_body", "text": "ร่างกายรู้สึกอย่างไรบ้าง? (เช่น หัวใจเต้นเร็ว, หายใจไม่ลึก, เกร็ง)"},
        {"id": "arousal_coping", "text": "มีสิ่งที่ช่วยผ่อนคลายคุณได้ในตอนนี้ไหม?"},
    ],
    "streak_risk": [
        {"id": "streak_motivation", "text": "รู้สึกอย่างไรกับการดูแลตัวเองในช่วงนี้?"},
        {"id": "streak_barrier", "text": "มีอะไรที่ขัดขวางไม่ให้ดูแลตัวเองได้บ้าง?"},
        {"id": "streak_support", "text": "อยากให้เราช่วยอะไรเพื่อให้คุณกลับมาฟอร์มได้?"},
    ],
    "baseline": [
        {"id": "baseline_mood", "text": "วันนี้รู้สึกอย่างไรโดยรวม? (1 = แย่มาก, 5 = ดีมาก)"},
        {"id": "baseline_energy", "text": "มีพลังงานเพียงพอสำหรับวันนี้ไหม?"},
        {"id": "baseline_highlight", "text": "มีอะไรที่ทำให้รู้สึกดีในวันนี้บ้างไหม?"},
    ],
    # Risk of Pain Spreading (ROPS) — 6-item binary screener (Tanguay-Sabourin et al., Nature Medicine 2023)
    # Score = sum of yes answers (0–6); higher score = greater risk of chronic pain spreading
    "rops": [
        {"id": "rops_sleep", "text": "โดยปกติคุณมีปัญหาหลับยากหรือตื่นกลางดึกบ่อยๆ ไหม?"},
        {"id": "rops_fedup", "text": "คุณรู้สึก 'หมดแรงใจ' หรือเบื่อหน่ายกับชีวิตบ่อยๆ ไหม?"},
        {"id": "rops_tired", "text": "ใน 2 สัปดาห์ที่ผ่านมา คุณรู้สึกเหนื่อยล้าหรือไม่มีแรงมากกว่าครึ่งของวันไหม?"},
        {"id": "rops_mental_help", "text": "คุณเคยพบแพทย์หรือผู้เชี่ยวชาญด้านสุขภาพจิตเรื่องความเครียด ความวิตกกังวล หรือภาวะซึมเศร้าไหม?"},
        {"id": "rops_life_stress", "text": "ใน 2 ปีที่ผ่านมา คุณเผชิญกับเหตุการณ์รุนแรง เช่น การเจ็บป่วยหนัก การสูญเสียคนรัก หรือปัญหาการเงินที่รุนแรงไหม?"},
        {"id": "rops_bmi", "text": "ดัชนีมวลกาย (BMI) ของคุณมากกว่า 30 ไหม? (น้ำหนัก kg หารด้วยส่วนสูง m²)"},
    ],
}

ALL_SCENARIOS = list(SCENARIO_QUESTIONS.keys())
