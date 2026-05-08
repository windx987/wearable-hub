import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from logging import getLogger
from uuid import UUID

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.audio_daily_summary import AudioDailySummary
from app.models.daily_score import DailyScore
from app.models.data_point_series import DataPointSeries
from app.models.data_source import DataSource
from app.models.questionnaire_response import QuestionnaireResponse
from app.models.series_type_definition import SeriesTypeDefinition

logger = getLogger(__name__)

_SYSTEM_PROMPT = """คุณคือ รู้ใจ (Roojai) — AI ผู้ช่วยด้านสุขภาพระบบประสาท
คุณช่วยให้ผู้ใช้เข้าใจข้อมูลความเครียดและการฟื้นตัวจากอุปกรณ์สวมใส่ การวิเคราะห์เสียง และการเช็คอินประจำวัน

กฎ:
- ตอบเป็นภาษาไทยเสมอ ยกเว้นผู้ใช้เขียนภาษาอังกฤษ
- พูดสั้น กระชับ และให้คำแนะนำที่ปฏิบัติได้จริง
- ไม่วินิจฉัยโรคหรือให้คำแนะนำทางการแพทย์
- เป็นกันเอง ใส่ใจ ไม่ตัดสิน
- คะแนน 0-100: 80+ = ดีมาก, 60-79 = พอใช้, 40-59 = ต้องระวัง, <40 = วิกฤต"""

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_daily_scores",
            "description": "ดึงคะแนน Stress & Recovery ประจำวันของผู้ใช้ พร้อม component HRV / sleep / audio / survey",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "จำนวนวันย้อนหลัง (default 7)", "default": 7},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_audio_summary",
            "description": "ดึงข้อมูลสรุปเสียง: valence (อารมณ์), arousal (ความตื่นตัว), breathing_rate",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "จำนวนวันย้อนหลัง (default 7)", "default": 7},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_questionnaire_history",
            "description": "ดึงประวัติการเช็คอิน: scenario ที่ถูกเลือก, คำตอบ และ context",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "จำนวนวันย้อนหลัง (default 7)", "default": 7},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hrv_trend",
            "description": "ดึงค่า RMSSD (HRV) รายวันพร้อม baseline 30 วัน เพื่อดูแนวโน้ม",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "จำนวนวันย้อนหลัง (default 14)", "default": 14},
                },
                "required": [],
            },
        },
    },
]


def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _tool_get_daily_scores(db: Session, user_id: UUID, days: int = 7) -> dict:
    date_from = date.today() - timedelta(days=days)
    rows = db.execute(
        select(DailyScore)
        .where(DailyScore.user_id == user_id, DailyScore.date >= date_from)
        .order_by(DailyScore.date.desc())
    ).scalars().all()
    return {
        "scores": [
            {
                "date": r.date,
                "score": r.score,
                "hrv_score": r.hrv_score,
                "sleep_score": r.sleep_score,
                "audio_score": r.audio_score,
                "survey_score": r.survey_score,
                "hrv_weight": r.hrv_weight,
                "audio_weight": r.audio_weight,
            }
            for r in rows
        ]
    }


def _tool_get_audio_summary(db: Session, user_id: UUID, days: int = 7) -> dict:
    date_from = date.today() - timedelta(days=days)
    rows = db.execute(
        select(AudioDailySummary)
        .where(AudioDailySummary.user_id == user_id, AudioDailySummary.date >= date_from)
        .order_by(AudioDailySummary.date.desc())
    ).scalars().all()
    return {
        "audio": [
            {
                "date": r.date,
                "avg_valence": r.avg_valence,
                "avg_arousal": r.avg_arousal,
                "avg_breathing_rate": r.avg_breathing_rate,
                "sample_count": r.sample_count,
                "usable_count": r.usable_count,
            }
            for r in rows
        ]
    }


def _tool_get_questionnaire_history(db: Session, user_id: UUID, days: int = 7) -> dict:
    date_from = date.today() - timedelta(days=days)
    rows = db.execute(
        select(QuestionnaireResponse)
        .where(QuestionnaireResponse.user_id == user_id, QuestionnaireResponse.date >= date_from)
        .order_by(QuestionnaireResponse.date.desc())
    ).scalars().all()
    return {
        "checkins": [
            {
                "date": r.date,
                "scenario": r.scenario,
                "answers": r.answers,
                "context": r.context_snapshot,
            }
            for r in rows
        ]
    }


def _tool_get_hrv_trend(db: Session, user_id: UUID, days: int = 14) -> dict:
    window_start = datetime.now(timezone.utc) - timedelta(days=days)
    baseline_start = datetime.now(timezone.utc) - timedelta(days=30)

    daily_rows = db.execute(
        select(
            func.date_trunc("day", DataPointSeries.recorded_at).label("day"),
            func.avg(DataPointSeries.value).label("avg_rmssd"),
        )
        .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
        .join(SeriesTypeDefinition, DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id)
        .where(
            DataSource.user_id == user_id,
            SeriesTypeDefinition.code == "heart_rate_variability_rmssd",
            DataPointSeries.recorded_at >= window_start,
        )
        .group_by("day")
        .order_by("day")
    ).all()

    baseline = db.execute(
        select(func.avg(DataPointSeries.value))
        .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
        .join(SeriesTypeDefinition, DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id)
        .where(
            DataSource.user_id == user_id,
            SeriesTypeDefinition.code == "heart_rate_variability_rmssd",
            DataPointSeries.recorded_at >= baseline_start,
        )
    ).scalar()

    return {
        "baseline_30d": float(baseline) if baseline else None,
        "daily": [
            {"date": row.day.date() if hasattr(row.day, "date") else row.day, "rmssd": float(row.avg_rmssd)}
            for row in daily_rows
        ],
    }


def _dispatch_tool(name: str, args: dict, db: Session, user_id: UUID) -> str:
    try:
        if name == "get_daily_scores":
            result = _tool_get_daily_scores(db, user_id, args.get("days", 7))
        elif name == "get_audio_summary":
            result = _tool_get_audio_summary(db, user_id, args.get("days", 7))
        elif name == "get_questionnaire_history":
            result = _tool_get_questionnaire_history(db, user_id, args.get("days", 7))
        elif name == "get_hrv_trend":
            result = _tool_get_hrv_trend(db, user_id, args.get("days", 14))
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        result = {"error": str(exc)}
    return json.dumps(result, default=_decimal_default)


class AIAgentService:
    def __init__(self) -> None:
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            key = settings.openai_api_key
            if key is None:
                raise ValueError("OPENAI_API_KEY is not configured")
            self._client = OpenAI(api_key=key.get_secret_value())
        return self._client

    def generate_insights(self, db: Session, user_id: UUID, target_date: date | None = None) -> dict:
        today = target_date or date.today()

        scores = _tool_get_daily_scores(db, user_id, days=7)
        audio = _tool_get_audio_summary(db, user_id, days=7)
        checkins = _tool_get_questionnaire_history(db, user_id, days=7)

        today_score = next((s for s in scores["scores"] if s["date"] == today), None)

        data_summary = {
            "today": today.isoformat(),
            "today_score": today_score,
            "recent_scores": scores["scores"][:7],
            "recent_audio": audio["audio"][:3],
            "recent_checkins": checkins["checkins"][:3],
        }

        prompt = f"""วิเคราะห์ข้อมูลสุขภาพของผู้ใช้วันที่ {today} และสร้าง insight:

ข้อมูล:
{json.dumps(data_summary, default=_decimal_default, ensure_ascii=False, indent=2)}

ตอบในรูปแบบ JSON เท่านั้น (ไม่มีข้อความอื่น):
{{
  "insight": "insight 2-3 ประโยคเป็นภาษาไทย",
  "recommendations": ["คำแนะนำ 1", "คำแนะนำ 2", "คำแนะนำ 3"],
  "mood_label": "ดีมาก" หรือ "พอใช้" หรือ "ต้องระวัง" หรือ "วิกฤต",
  "score_interpretation": "อธิบาย component ที่มีผลมากที่สุด"
}}"""

        response = self.client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"insight": content, "recommendations": [], "mood_label": "พอใช้", "score_interpretation": ""}

    def chat(
        self,
        db: Session,
        user_id: UUID,
        message: str,
        history: list[dict],
    ) -> tuple[str, list[str]]:
        messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": _SYSTEM_PROMPT}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})  # type: ignore[misc]
        messages.append({"role": "user", "content": message})

        tools_called: list[str] = []

        while True:
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=_TOOLS,  # type: ignore[arg-type]
                tool_choice="auto",
                temperature=0.7,
            )

            choice = response.choices[0]
            msg = choice.message
            messages.append(msg)  # type: ignore[arg-type]

            if choice.finish_reason == "tool_calls" and msg.tool_calls:
                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    fn_args = json.loads(tc.function.arguments)
                    tools_called.append(fn_name)
                    result = _dispatch_tool(fn_name, fn_args, db, user_id)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
            else:
                return msg.content or "", tools_called


ai_agent_service = AIAgentService()
