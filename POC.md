# รู้ใจ RoojaiHub — Product Concept & Architecture

**Product:** รู้ใจ RoojaiHub  
**Tagline:** AI infrastructure for preventive nervous-system health  
**MVP:** Stress + Recovery Intelligence — Thai market first

---

## 1. Problem

Thailand has one of the highest rates of workplace burnout in Southeast Asia, yet mental-health infrastructure is scarce, expensive, and stigmatized. People don't know they're burning out until it's too late. Clinical-grade stress monitoring exists (HRV biofeedback, PSG sleep studies) but requires specialist equipment and visits.

RoojaiHub makes continuous, passive, multi-signal stress monitoring available on an iPhone the user already carries — with no conscious effort required.

---

## 2. Core Hypothesis

Three passive signals, fused daily, can predict stress and recovery better than any single signal alone:

| Signal | Source | Key features |
|---|---|---|
| Physiological | Apple Watch / Garmin / Whoop | HRV (RMSSD), resting HR, sleep stages, SpO₂, environmental dB |
| Vocal biomarkers | On-device audio agent | Pitch mean, energy RMS, silence ratio, breathing rate, valence, arousal |
| Adaptive check-in | Agent-generated questions | 3–4 contextual questions based on today's signals — not a fixed form |

Combined daily into a **Stress & Recovery Score (0–100)**.

### Why RMSSD not LF/HF

RMSSD is the primary HRV metric. It reflects parasympathetic (vagal) tone, is validated for short recordings (2–5 min overnight window), and is directly available from Apple Watch via HealthKit. LF/HF ratio requires FFT computation from raw RR intervals, is scientifically contested (LF is not purely sympathetic), and adds complexity without proven benefit at MVP scale. LF/HF may be revisited as an ML feature in Phase 3.

### RMSSD vs Voice — complementary time horizons

```
RMSSD  →  "how recovered is your body?"     reflects yesterday → today (lags 4–12h)
Voice  →  "how stressed are you right now?"  reflects this hour (real-time)
```

They measure different stress pathways. High RMSSD + low voice valence = emotional stressor not yet showing in physiology. Low RMSSD + normal voice = physical overtraining or illness. Fusion disambiguates the cause.

---

## 3. Passive Audio Agent — Architecture

### 3.1 Design Philosophy

> "A doctor doesn't follow you everywhere recording everything you say. They check your vitals every hour and after significant events. We do the same."

Random continuous sampling wastes battery and produces mostly useless data. A user speaks or makes emotionally significant sound only ~25% of the day. Random 100 samples/day → ~10 actually useful. More critically, random sampling has no context — a stressed voice after exercise looks identical to one during commute noise.

The hourly + event-triggered model solves both problems.

### 3.2 Sampling Schedule

**Hourly baseline (16 samples/day)**
- Waking hours only: 07:00–23:00
- One 10–15 sec capture per hour
- Scheduled via `BGAppRefreshTask` — iOS-native, battery-efficient

**Event-triggered samples (~4–10 additional)**

| Trigger | When | Why |
|---|---|---|
| `post_workout` | 5 min after workout ends | Recovery state, known physiological context |
| `wake` | Within 10 min of wake detection | Baseline before daily stress accumulates |
| `hrv_drop` | HRV drops >20% vs 7-day average | Confirmed physiological stress signal |
| `pre_sleep` | ~30 min before sleep onset | End-of-day recovery window |
| `calendar_end` | After calendar meeting ends | Post-social/work stress probe |

**Total: ~20–26 samples/day** — each with a known `trigger` context.

### 3.3 Noise Filtering via Apple Watch Environmental dB

Apple Watch passively measures ambient noise all day via `environmental_audio_exposure` (dB) — already available in HealthKit and in the open-wearables `data_point_series` table.

Instead of a 500ms iPhone mic pre-check, the score engine cross-references the Watch's dB reading for the same time window as each audio sample:

```
At score time:
watch_db = get_timeseries(user_id, "environmental_audio_exposure", recorded_at ± 5min)

if watch_db.avg > 70 dB:                    # BTS / traffic
    environment_quality = "noisy"
    discount or discard sample

if ANC active (environmental_sound_reduction > 10 dB):
    threshold = 85 dB                        # AirPods compensate ~15–20 dB
```

**Advantages over iPhone mic pre-check:**
- No extra battery drain on iPhone — Watch is already measuring
- Retroactive labeling — can re-evaluate samples if Watch data arrives late
- AirPods ANC context via `environmental_sound_reduction` series
- BTS commute (75–85 dB) automatically excluded — SNR is negative at those levels

Skipped/noisy samples still stored with `was_skipped=true` — commute exposure patterns are themselves useful environment data.

### 3.4 Why This Beats Random Sampling

| Metric | Random 100×/day | Hourly + Event ~25×/day |
|---|---|---|
| Useful voice samples | ~10 (25% hit rate) | ~20+ (known context = all usable) |
| CPU time/day | ~25 min | ~5 min |
| Battery impact | High | ~80% less |
| BTS false positives | High (SNR negative) | Eliminated by noise floor check |
| Interpretability | None — random timing | Full — trigger context known |
| iOS background reliability | Poor (random BGTask) | Good (BGAppRefreshTask hourly) |

### 3.5 The BTS Problem

On Bangkok BTS/MRT platforms, ambient noise reaches 75–85 dB. Human voice at 0.5m = 60–70 dB. Signal-to-Noise Ratio = negative. All extracted features (pitch, energy, breathing rate) reflect train noise, not the user's vocal state. Random sampling approaches have no defense against this.

The noise floor check rejects these samples before any processing happens. The user's commute appears as a cluster of `was_skipped=true` samples with `ambient_db ≈ 80`, which correctly tells the score engine: "no reliable voice data during 08:00–09:00 commute."

### 3.6 On-Device Feature Extraction

Raw audio is **never transmitted or stored**. Feature extraction runs entirely on-device:

```
Record 10–15 sec → Feature extraction (CoreML / openSMILE) → Discard raw audio → POST feature vector
```

Feature vector fields:
- `pitch_mean` — fundamental frequency (vocal effort / arousal proxy)
- `energy_rms` — loudness (activation proxy)
- `silence_ratio` — proportion of silence in sample (low energy / fatigue proxy)
- `breathing_rate` — estimated from low-frequency amplitude modulation
- `valence_score` — positive/negative affect (0–1, CoreML classifier)
- `arousal_score` — activation level (0–1, CoreML classifier)
- `ambient_db` — pre-sample noise floor
- `trigger` — sampling trigger type (hourly | post_workout | wake | hrv_drop | pre_sleep)
- `environment_quality` — clean | noisy | skipped

---

## 4. Physiological Signal Pipeline

### 4.1 HealthKit Integration

Pull from Apple HealthKit (background fetch, no cloud):

- HRV: SDNN and RMSSD (5-min windows from watchOS)
- Resting heart rate
- Sleep stages: awake, REM, core, deep (watchOS 9+)
- Activity energy, step count, active minutes

First launch: backfill 7 days. Then: daily delta sync in background.

### 4.2 Normalization

HealthKit data normalized to match the existing `summaries` / `timeseries` schema so existing dashboard and API infrastructure works unchanged.

---

## 5. Adaptive Check-in Agent

### 5.1 Design Philosophy

A fixed 5-question form causes survey fatigue within 2 weeks — users answer on autopilot and signal quality collapses. Instead, an agent reads today's signals first, then generates 3–4 targeted questions relevant to what actually happened.

```
Fixed form:   same questions every day  →  survey fatigue, low signal quality
Adaptive:     reads signals → picks scenario → asks relevant questions  →  high engagement
```

### 5.2 Scenario Detection

Before sending the check-in notification, a Celery task runs:

```python
def select_scenario(user_id, today):
    if rmssd_drop_pct > 25:       return Scenario.HRV_DROP
    if had_workout_today:          return Scenario.POST_WORKOUT
    if sleep_efficiency < 0.70:    return Scenario.POOR_SLEEP
    if avg_audio_arousal > 0.70:   return Scenario.HIGH_AROUSAL
    if recovery_streak >= 3:       return Scenario.RECOVERY_STREAK
    return Scenario.BASELINE
```

### 5.3 Question Sets by Scenario

| Scenario | Trigger condition | Sample questions |
|---|---|---|
| `hrv_drop` | RMSSD dropped >25% | มีเรื่องกดดันวานนี้ไหม? / นอนหลับยากไหม? / ร่างกายเหนื่อยไหม? |
| `post_workout` | Workout recorded <4h ago | เหนื่อยมากแค่ไหน? / กล้ามเนื้อปวดไหม? / อยากออกพรุ่งนี้ไหม? |
| `poor_sleep` | Sleep <5h or efficiency <70% | ตื่นกลางดึกบ่อยไหม? / ตื่นมาสดชื่นไหม? / อะไรทำให้นอนไม่หลับ? |
| `high_arousal` | Voice arousal avg >0.7 | วันนี้เครียดหรือตื่นเต้น? / ตอนนี้รู้สึกยังไง? |
| `recovery_streak` | Score >70 for 3+ days | ทำอะไรแตกต่างช่วงนี้? / อารมณ์โดยรวมเป็นยังไง? |
| `baseline` | No significant signal | อารมณ์วันนี้? / ระดับพลังงาน? / มีความเจ็บปวดไหม? |

Context intro shown before questions (e.g., "HRV ของคุณต่ำกว่าปกติวันนี้...") — explains why we're asking, builds trust.

### 5.4 Storage

Answers stored as flexible JSONB — not fixed columns — so question sets can evolve without migrations:

```json
{
  "scenario": "hrv_drop",
  "context_snapshot": { "rmssd_drop_pct": 32, "rmssd_today": 28 },
  "answers": {
    "stressor_present": true,
    "stressor_text": "มีประชุมยาวมาก",
    "sleep_difficulty": 4,
    "body_fatigue": 3
  }
}
```

Enforced once-per-day server-side. All copy in Thai.

---

## 6. Stress & Recovery Score Engine

### 6.1 Input Features

**HRV / Physiological** (from Apple Watch via HealthKit)
- `rmssd_drop_pct` — today RMSSD vs 30-day personal baseline (personal baseline is critical — same 28ms = stressed for one user, recovered for another)
- `sleep_efficiency` — deep + REM minutes / total time in bed
- `sleep_duration_minutes` — total sleep
- `resting_hr_vs_baseline` — today vs 7-day average
- `oxygen_saturation` — avg SpO₂ during sleep

**Voice** (from `audio_daily_summary`)
- `avg_valence` — daily average across usable samples
- `avg_arousal` — daily average
- `avg_silence_ratio` — low = rushed speech = stress
- `avg_breathing_rate` — elevated = stress
- `usable_sample_ratio` — data quality weight factor
- `environment_quality` — from Apple Watch `environmental_audio_exposure`

**Adaptive check-in** (from `questionnaire_response`)
- Scenario-dependent — JSONB answers normalized to 0–1 contribution score per scenario

### 6.2 Phase 1 — Rule-Based Baseline

```
hrv_score    = 100 - (rmssd_drop_pct × 1.5) + resting_hr_bonus
sleep_score  = (efficiency × 60) + (duration_score × 30) + (spo2_score × 10)
audio_score  = (avg_valence × 50) + ((1 - avg_arousal) × 30) + (pace_score × 20)
               × usable_sample_ratio
survey_score = normalized from scenario answers (0–100)

score = (hrv_score × 0.40)
      + (sleep_score × 0.25)
      + (audio_score × 0.20)
      + (survey_score × 0.15)
```

Score range: 0–100 (higher = better recovery). Component breakdown stored per day so users see which signal drove the score.

### 6.3 Signal Fallback

Missing signal → weight redistributed proportionally:

```
No wearable  →  audio 0.35 / survey 0.30 / sleep 0.35
No voice     →  hrv 0.50 / sleep 0.30 / survey 0.20
No survey    →  hrv 0.45 / sleep 0.35 / audio 0.20
No sleep     →  hrv 0.55 / audio 0.25 / survey 0.20
```

Score always computed with minimum 1 signal.

### 6.4 Alert Logic

```
score < 40                        →  push notification
score < 40 for 3 consecutive days →  burnout risk alert
rmssd_drop > 40% single day       →  immediate alert (regardless of score)
```

### 6.5 Phase 3 — ML Model (after labeled data exists)

Replace rule-based formula once internal labeled dataset reaches ~1,000 user-days:
- Evaluate: wav2vec 2.0 base vs. HuBERT base vs. openSMILE + gradient boost
- LF/HF ratio added as ML feature (not standalone signal — too noisy for rules)
- Target: CoreML export, <50ms inference on iPhone

---

## 7. Alerts & Thresholds

Default alerts (APNs push):
- Score < 40 → "ความเครียดสูงวันนี้ — ดูแลตัวเองด้วยนะ"
- Score < 40 for 3 consecutive days → "เริ่มสังเกตสัญญาณเหนื่อยล้า — ลองพักดูไหม?"
- RMSSD drop > 40% single day → immediate alert regardless of score

User-configurable:
- Alert threshold (default 40)
- Quiet hours (no push during sleep window)
- Snooze (skip alerts for N days)

---

## 8. Privacy & Data Model

| Data | Where stored | Raw ever leaves device? |
|---|---|---|
| Raw audio | Never stored, not even on-device | No |
| Audio feature vectors | Server (per-sample, timestamped) | Yes (features only) |
| HealthKit readings | Server (aggregated daily + 5-min HRV) | Yes |
| Questionnaire responses | Server | Yes |
| Score history | Server | Yes |

All data belongs to the user. PDPA-compliant (Thailand Personal Data Protection Act). Opt-out deletes all stored data within 72h.

---

## 9. Thai Market Specifics

- Full Thai language from day 1 — all UI, notifications, onboarding
- Localization via `Localizable.strings` / SwiftUI `LocalizedStringKey`
- Designed for 08:00–17:00 office worker (common Thai work pattern)
- BTS/MRT commute handled explicitly (noise floor check designed around Bangkok transit noise levels)
- Buddhist calendar awareness for future features (e.g., monks' days, holidays affecting stress patterns)

---

## 10. B2B Expansion (Phase 4)

After B2C validation:

- **HR dashboard** — anonymized team stress heatmap, burnout risk flags
- **Clinician report** — weekly PDF export with all signal trends (for company doctors)
- **Condition modules** — licensable API for third-party health apps (anxiety module, burnout module, sleep module)
- Multi-tenant API key management (base infrastructure already in stack)

---

## 11. Implementation Status

### Phase 1.3 — Adaptive Check-in Agent ✅ Complete

Built and live:

- `questionnaire_response` table — JSONB answers + context snapshot, unique constraint (user × date)
- `detect_scenario()` — signal-priority cascade: `hrv_drop → elevated_arousal → poor_sleep → post_workout → streak_risk → baseline`
- 6 scenario question sets in Thai (3–4 questions each)
- `GET /questionnaire/users/{id}/today` — returns scenario + questions + already_submitted flag
- `POST /questionnaire/users/{id}/submit` — once-per-day enforcement via IntegrityError catch
- Scenario thresholds: RMSSD drop >15% (vs 30d baseline), arousal >0.65, sleep efficiency <75%, 2-day streak gap

### Phase 1.4 — Score Engine ✅ Complete

Built and live:

- `daily_score` table — component scores + weights per day, unique constraint (user × date)
- Actual formula implemented:

```python
hrv_score   = (today_rmssd / baseline_30d) × 70   # capped 0–100
audio_score = valence × 60 + max(0, 1 - |arousal - 0.40| × 2.5) × 40
survey_score = (avg_1to5 - 1) / 4 × 100
sleep_score = via SleepScoreService (existing)

weights = {hrv: 0.40, sleep: 0.25, audio: 0.20, survey: 0.15}
# Missing signal → weight redistributed proportionally to present signals
```

- `POST /scores/users/{id}/compute` — upsert (recomputes if called again)
- `GET /scores/users/{id}/daily` — history with per-component breakdown
- Validated: score=46.61 with only HRV signal (38ms today / 57ms baseline)

### Phase 1.AI — Autonomous Agentic Core ✅ Complete

Replaced the chatbot pattern with a fully autonomous perceive→reason→act→record loop.

**Architecture:**

```
Trigger (cron / manual / on_submit / hrv_drop)
    ↓
_perceive()  — collects DailyScore 7d, AudioSummary 7d, Questionnaire 7d,
               RMSSD today + 30d baseline, hrv_drop_pct, declining_streak,
               days_since_last_checkin
    ↓
_reason()    — GPT-4o-mini (temperature=0.3, response_format=json_object)
               Returns: observations[], risk_level, reasoning, actions[]
    ↓
_act()       — executes each action:
               compute_score | override_scenario | generate_insight
               queue_push | flag_risk
    ↓
AgentRunLog  — full audit trail persisted: context_snapshot, observations,
               reasoning, actions_planned, actions_executed
```

**Risk levels and rules:**
- `low` — no action required
- `moderate` — flag_risk only
- `elevated` — generate_insight + flag_risk (+ queue_push if elevated)
- `critical` — all 5 actions, including immediate push notification

**Live test result (2026-05-08):**
- jwoods: today_rmssd=38ms, baseline=57ms → drop=33.4%
- Score computed: 46.61 (HRV-only, caution zone)
- Agent classified: `risk_level: critical`
- Actions executed: compute_score ✓ → generate_insight ✓ → queue_push (queued, APNs Phase 1.5) → override_scenario ✓ → flag_risk (critical) ✓
- Full Thai reasoning generated by GPT-4o-mini

**Celery beat:** Runs daily at 00:00 UTC (07:00 ICT) for all users.

**Endpoints:**
- `POST /agent/users/{id}/run` — manual trigger with optional target_date
- `GET /agent/users/{id}/log` — full audit trail with context snapshots

**Also built (chatbot mode):**
- `POST /ai/users/{id}/insights` — structured insight + mood_label + recommendations
- `POST /ai/users/{id}/chat` — conversational with 4 function-calling tools (daily scores, audio summary, questionnaire history, HRV trend)

### What's Pending

| Phase | Feature | Status |
|---|---|---|
| 1.1 | HealthKit SDK ingestion (RMSSD, sleep, steps) | Not started |
| 1.5 | APNs push delivery (queue_push currently stubs) | Not started |
| 1.5 | Alert rules + user alert preferences endpoint | Not started |
| 1.5 | Celery tasks: audio daily aggregation, 14:00 check-in push | Stubs exist |
| 2 | CoreML on-device audio feature extraction | Not started |
| 3 | ML model replacing rule-based score formula | Not started |

---

## 12. Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + PostgreSQL + Celery + Redis |
| AI Agent | GPT-4o-mini via OpenAI SDK (`response_format=json_object`, temp=0.3) |
| iOS app | SwiftUI + HealthKit + CoreML + BGTaskScheduler |
| Audio extraction | openSMILE iOS / CoreML feature model (TBD) |
| Infra | Docker → self-hosted VPS (MVP) → cloud (scale) |
| SDK | open_wearables_ios_sdk (extended for HealthKit) |

---

## 13. MVP Success Criteria

- [ ] 50 internal beta users (team + friends), 2-week run
- [ ] >70% daily adaptive check-in completion rate (vs. ~40% for fixed forms)
- [ ] Score correlates with self-reported stress (Spearman ρ > 0.5)
- [ ] Audio samples: >60% usable (not skipped) per user per day
- [ ] Apple Watch dB cross-reference correctly labels BTS commute windows as noisy
- [ ] Push notification CTR > 30% on threshold alerts
- [ ] Zero raw audio leaving device (privacy audit)
- [ ] Scenario detection fires correct scenario >80% of the time (manual spot-check)
