# asm-my-lectures

Claude Code 스킬: AI·SW마에스트로(swmaestro.ai) **멘토링/특강 접수내역** 조회.

로그인 → MY PAGE → 멘토링/특강 게시판 → 접수내역 전체 페이지를 Playwright로 크롤링하고, 사용자가 원하는 기준(이번 주, 특정 멘토, 특강/자유멘토링, 접수상태 등)으로 필터링해서 보여줍니다.

## 구성

```
.
├── SKILL.md              # 스킬 정의 (트리거 · 워크플로 · 출력 포맷)
├── scripts/
│   └── crawl.py          # Playwright 크롤러 — 로그인 + 모든 페이지 수집
├── .gitignore
└── README.md
```

## 사전 준비

1. Python 의존성 설치 (1회):
   ```bash
   pip install playwright python-dotenv
   playwright install chromium
   ```
2. 인증 정보 설정 — 다음 중 하나 (chat에 붙여넣지 말 것):
   - **A) 환경변수 직접 설정**
     - `ASM_USERNAME` — swmaestro.ai 아이디
     - `ASM_PASSWORD` — swmaestro.ai 비밀번호
   - **B) `.env` 파일 사용** — 이 디렉토리에 `.env` 생성 (`.gitignore`가 처리)
     ```
     ASM_USERNAME=your_id
     ASM_PASSWORD=your_password
     ```
     `.env.example` 파일을 템플릿으로 복사하면 됩니다.
     스크립트가 `python-dotenv`로 자동 로드합니다 — 크롤러 실행 위치에 상관없이 스킬 디렉토리의 `.env`를 찾습니다.

## 직접 실행

```bash
python scripts/crawl.py --out asm_history.json
# 또는 브라우저 창 보이기:
python scripts/crawl.py --headed
```

출력 JSON 스키마:
```json
{
  "count": 61,
  "fetched_at": "2026-04-24T07:35:00+09:00",
  "rows": [
    {
      "no": "61",
      "type": "자유멘토링",
      "title": "...",
      "mentor": "정원용",
      "session_datetime": "2026-04-26(일) 17:00:00 ~ 18:30:00",
      "registered_at": "2026-04-24 13:05",
      "status": "접수완료",
      "approval": "OK",
      "action_slot": "-",
      "note": "취소"
    }
  ]
}
```

## Claude Code에서 사용

스킬 디렉토리를 `~/.claude/skills/asm-my-lectures/`에 두면 Claude가 `SKILL.md`의 description을 보고 자동 트리거합니다. 예:

- "이번 주 멘토링 알려줘"
- "정경민 멘토 특강 뭐 있어?"
- "다음 주 AWS 관련 특강"
- "내가 신청한 자유멘토링 전부"

## 주의

- `.gitignore`가 `*.json`을 무시합니다. 크롤러가 만드는 `asm_history.json`에는 개인 일정·팀원 이름이 들어 있으므로 커밋하지 마세요 (필요시 `evals/evals.json` 같은 스킬 eval 파일은 예외 처리).
- 비고(`note`) 컬럼의 `취소`는 "취소 버튼이 노출됨"을 의미할 뿐 실제 취소 상태가 아닙니다. 실제 상태는 `status` 컬럼 (`접수완료` / `접수취소`)입니다.
- 크롤러는 안전장치로 200 페이지에서 멈춥니다.
