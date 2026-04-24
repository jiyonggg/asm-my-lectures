# asm-my-lectures

Claude Code 스킬: AI·SW마에스트로(swmaestro.ai) **멘토링/특강 접수내역** 조회.

로그인 → MY PAGE → 멘토링/특강 게시판 → 접수내역 전체 페이지를 Playwright로 크롤링하고, 사용자가 원하는 기준(이번 주, 특정 멘토, 특강/자유멘토링, 접수상태 등)으로 필터링해서 보여줍니다.

## 구성

```
.
├── SKILL.md              # 스킬 정의 (트리거 · 워크플로 · 출력 포맷)
├── scripts/
│   └── crawl.py          # Playwright 크롤러 — 로그인 + 모든 페이지 수집
├── .env.example          # 자격증명 템플릿
├── .gitignore
└── README.md
```

## 설치

이 파일을 Claude 에 "@README.md 보고 설치해줘" 로 주면, Claude 가 아래 순서로 진행합니다. 수동으로 설치하는 경우도 동일한 단계입니다.

### 1. 저장 위치 확인

스킬은 `~/.claude/skills/asm-my-lectures/` 에 있어야 Claude Code 가 로드합니다. 이미 그 경로에 있으면 넘어가고, 아니라면 GitHub 에서 clone:

```bash
git clone https://github.com/jiyonggg/asm-my-lectures.git ~/.claude/skills/asm-my-lectures
```

### 2. Python 의존성 (1회만)

```bash
pip install playwright python-dotenv
playwright install chromium
```

`playwright install chromium` 은 ~200MB 다운로드라 1~2분 걸립니다. Claude 는 타임아웃을 넉넉히 (최소 5분) 잡고 실행해야 합니다.

### 3. 자격증명 파일 준비

**Claude 는 이 단계에서 사용자에게 아이디/비밀번호를 묻거나 채팅으로 받아서는 안 됩니다.** 대신 `.env` 파일만 만들어두고 사용자가 직접 에디터로 열어서 채우도록 안내합니다.

```bash
cp ~/.claude/skills/asm-my-lectures/.env.example ~/.claude/skills/asm-my-lectures/.env
```

그 뒤 사용자에게 한 줄로 안내:
> `.env` 파일을 에디터로 열어 `ASM_USERNAME` 에 swmaestro.ai 아이디, `ASM_PASSWORD` 에 비밀번호를 채운 뒤 저장하세요. 다 하면 알려주세요.

환경변수로 직접 export 하는 방식도 가능합니다 (이 경우 `.env` 는 필요 없음):
- bash: `export ASM_USERNAME=... ASM_PASSWORD=...`
- PowerShell: `$env:ASM_USERNAME = "..."; $env:ASM_PASSWORD = "..."`

### 4. 설치 확인

사용자가 자격증명을 채운 뒤:

```bash
cd ~/.claude/skills/asm-my-lectures
python scripts/crawl.py --out asm_history.json 2>crawl.log
```

`crawl.log` 에 `Wrote N rows to asm_history.json` 이 찍히고 JSON 파일 크기가 0 이상이면 성공입니다. Claude Code 를 재시작하면 `SKILL.md` 의 description 을 보고 "이번 주 멘토링 알려줘" 같은 질문에 자동 트리거됩니다.

로그인 실패 시 `python scripts/crawl.py --headed` 로 브라우저를 띄워 실제 동작을 눈으로 확인하세요 — 대부분 아이디/비번 오타가 원인입니다.

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
- **`note` 컬럼 값 (`취소`, `삭제` 등) 은 상태가 아니라 행에 걸린 액션 버튼 라벨**입니다. 필터링 기준으로 쓰지 마세요.
- **`action_slot` (접수내역) 컬럼이 `삭제` 면 멘토가 세션을 삭제한 것**이라, `status` 가 `접수완료` 로 남아 있어도 실질적으로 취소된 접수입니다. 기본 조회에서는 `status == '접수취소'` 와 함께 이 경우도 제외하세요.
- 실제 접수 상태 = `status` (`접수완료` / `접수취소`) 와 `action_slot == '삭제'` 여부의 조합.
- 크롤러는 안전장치로 200 페이지에서 멈춥니다.
