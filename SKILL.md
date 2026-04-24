---
name: asm-my-lectures
description: AI·SW마에스트로(swmaestro.ai) 멘토링·특강 접수내역을 조회합니다. 소마 / SOMA / swmaestro / AI·SW마에스트로 관련 질문 — 예정/지난 멘토링, "이번 주 멘토링", "오늘 특강", "내가 신청한 강의", 특정 멘토의 세션, 접수내역, 자유멘토링, 멘토특강 등 — 에는 반드시 이 스킬을 사용하세요. swmaestro.ai 계정 데이터가 필요한 경우 사이트를 직접 크롤링하지 말고 항상 이 스킬로 처리합니다.
---

# AI·SW마에스트로 멘토링 접수내역 조회

This skill reads the user's mentoring / 특강 reception history (접수내역) on https://swmaestro.ai and answers questions about it — by date, mentor, type (자유멘토링 / 멘토특강), status, or any filter the user asks for.

## Prerequisites

1. **Python dependencies** (one-time):
   ```bash
   pip install playwright python-dotenv
   playwright install chromium
   ```
2. **Credentials** — never paste in chat. Either:
   - Export `ASM_USERNAME` and `ASM_PASSWORD` as environment variables, **or**
   - Drop a `.env` file in the skill directory with:
     ```
     ASM_USERNAME=...
     ASM_PASSWORD=...
     ```
   The crawler loads `.env` automatically via `python-dotenv` if installed.

If neither is set, stop and ask the user to configure them. Do not ask them to type credentials into chat.

## Workflow

### Step 1 — Crawl the full history

Run the bundled crawler. It logs in, paginates through every page of 접수내역, and emits JSON to stdout. Progress goes to stderr.

```bash
python "<SKILL_DIR>/scripts/crawl.py" --out ~/.cache/asm_history.json
```

Replace `<SKILL_DIR>` with the actual path to this skill directory. On Windows with bash, something like `C:/Users/<name>/.claude/skills/asm-my-lectures`.

The output file has this shape:

```json
{
  "count": 61,
  "fetched_at": "2026-04-24T07:35:00+09:00",
  "rows": [ { "no": "61", "type": "자유멘토링", ... }, ... ]
}
```

### Step 2 — Row schema

Each row has these string fields:

| Field | Column | Meaning |
|---|---|---|
| `no` | NO. | Entry number (higher = more recent) |
| `type` | 구분 | `자유멘토링` or `멘토특강` |
| `title` | 제목 | Session title |
| `mentor` | 작성자 | Mentor name |
| `session_datetime` | 강의날짜 | e.g. `2026-04-26(일) 17:00:00 ~ 18:30:00` |
| `registered_at` | 접수일 | e.g. `2026-04-24 13:05` |
| `status` | 접수상태 | `접수완료` (confirmed) or `접수취소` (cancelled) |
| `approval` | 개설승인 | `OK` or `-` |
| `action_slot` | 접수내역 | usually `-` or `삭제` |
| `note` | 비고 | `취소` (cancel button shown) or `-` |

### Step 3 — Parse `session_datetime`

The first token is `YYYY-MM-DD`. A Korean day label `(월|화|수|목|금|토|일)` follows, then a `HH:MM:SS ~ HH:MM:SS` range. Extract the date and the start/end times to answer date-range questions.

### UTF-8 stdout (Windows)

Any ad-hoc Python helper you write to read `asm_history.json` and print results **must reconfigure stdout to UTF-8 first** — the default on Windows is CP949, and the first Korean character you `print()` will raise `UnicodeEncodeError` or arrive garbled in the agent's tool output. Start every helper with:

```python
import sys
sys.stdout.reconfigure(encoding="utf-8")
```

This is only needed for the wrapper scripts you generate on the fly to filter/format the JSON. `crawl.py` itself writes the file with an explicit `encoding="utf-8"` and is unaffected.

### Step 4 — Filter

Apply the filters implied by the user's question:

- **"이번 주"**: Monday through Sunday of the current week in **Asia/Seoul** (KST). If you're unsure what day "today" is, check the conversation's system context or run `date` in bash.
- **Default to `status == '접수완료'`** unless the user explicitly asks to include cancelled sessions.
- **By type**: `type == '자유멘토링'` or `'멘토특강'`.
- **By mentor**: substring match on `mentor`.
- **By keyword in title**: substring match on `title`.

### Step 5 — Format the output

Default format, grouped by date (ascending):

```
**📅 MM/DD (요일)**
[구분] 제목 — 작성자 멘토 | HH:MM~HH:MM
```

If the user asks for JSON / CSV / a table / plain text, honour that instead.

## Common pitfalls

- **`note == '취소'` is NOT a cancelled registration.** It just means the row has a "취소" button the user could click. The authoritative state is `status`.
- **Duplicate titles.** If the user cancelled and re-registered, you'll see two rows for the same session. Each row is its own reception record.
- **Login failure.** Run the crawler with `--headed` to watch the browser and see what went wrong:
  ```bash
  python "<SKILL_DIR>/scripts/crawl.py" --headed
  ```
  A visible browser is usually enough to spot a bad credential or a selector drift.
- **Pagination cap.** The crawler stops after 200 pages as a safety net. Normal accounts have well under 10.

## Caching within a conversation

If the user asks a follow-up ("그럼 다음 주는?", "자유멘토링만 다시"), re-read `/tmp/asm_history.json` and re-filter in memory. Only re-crawl if:

- The user says they just registered or cancelled something,
- The user explicitly asks for fresh data, or
- The cached file is missing / stale (e.g., from an earlier day).
