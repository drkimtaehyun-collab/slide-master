---
name: chart-summary
description: >
  진료 녹음(또는 녹취록)을 병원의 초진·재진 차트 양식에 맞춘 요약 초안으로 변환합니다.
  Turn a clinic visit recording or transcript into a chart-summary draft in the
  clinic's fixed initial-visit (초진) or follow-up (재진) format. Use for "진료 녹음
  요약", "차트 정리", "초진/재진 기록 만들어줘", or when setting up / running the
  inbox-folder watcher that auto-summarizes recordings. Not for presentations.
---

# Chart Summary — 진료 녹음 → 차트 요약

진료 녹음을 **로컬에서 전사**한 뒤, 병원이 정한 초진·재진 양식에 맞춰
**의사가 검토할 요약 초안**을 만듭니다. 결과물은 초안일 뿐이며, EMR 입력 전
담당 의사의 확인이 반드시 필요합니다.

```
clinic/inbox/초진/*.m4a ─┐
clinic/inbox/재진/*.m4a ─┼→ transcribe.py (로컬 Whisper, 음성은 외부 전송 없음)
clinic/inbox/*.txt ──────┘        │
                                  ▼
                           phi_mask.py (주민번호·전화번호 등 마스킹)
                                  │
                                  ▼
                 summarize.py → claude -p (도구 비활성, 텍스트만)
                                  │
                                  ▼
               clinic/charts/YYYY-MM-DD/<파일명>_<초진|재진>.md
```

## 시작 전 필수 확인 (처음 한 번)

자동 처리를 켜기 전에 [`references/privacy-consent.md`](references/privacy-consent.md)
체크리스트를 사용자와 함께 확인합니다. 저장 위치, 환자 동의, 보관 기간,
외부 전송 범위가 정해지지 않았으면 watcher를 실행하지 않습니다.

## 양식 (단일 원본)

| 파일 | 역할 |
|---|---|
| [`references/format-initial.md`](references/format-initial.md) | 초진 양식 |
| [`references/format-followup.md`](references/format-followup.md) | 재진 양식 |
| [`references/rules.md`](references/rules.md) | 요약 규칙 (추측 금지, 불확실 표기 등) |
| [`references/vocabulary.txt`](references/vocabulary.txt) | 전사 정확도용 의학 용어·약품명 힌트 |

병원의 실제 양식이 있으면 `format-*.md`의 제목·항목을 그대로 교체합니다.
스크립트와 대화형 사용 모두 이 파일들을 읽으므로 한 곳만 고치면 됩니다.

## 대화형 사용 (녹취록 한 건)

사용자가 녹취록 텍스트나 파일을 주고 요약을 요청하면:

1. 초진/재진 여부를 확인합니다. 파일 위치(`inbox/초진`, `inbox/재진`)나
   사용자 지시로 알 수 없으면 묻습니다.
2. `references/rules.md`와 해당 양식 파일을 읽습니다.
3. 규칙대로 요약을 작성합니다. 녹취록에 없는 내용은 채우지 않습니다.
4. 파일로 저장할 때는 `clinic/charts/` 아래에만 저장합니다 (git 제외 경로).

## 자동 처리 (폴더 감시)

설치와 실행은 [`clinic/README.md`](../../../clinic/README.md)를 따릅니다. 요약:

```bash
pip install -r .claude/skills/chart-summary/requirements.txt   # faster-whisper
python3 .claude/skills/chart-summary/scripts/watch_inbox.py          # 계속 감시
python3 .claude/skills/chart-summary/scripts/watch_inbox.py --once   # 현재 파일만 처리
```

한 건만 수동 처리:

```bash
python3 .claude/skills/chart-summary/scripts/transcribe.py 녹음.m4a -o 녹취.txt
python3 .claude/skills/chart-summary/scripts/summarize.py 녹취.txt --visit 초진
```

## 금지 사항

- 환자 음성·녹취록·요약을 git에 커밋하거나 `clinic/` 밖(특히 클라우드 동기화 폴더)에 저장하지 않습니다.
- 녹취록에 없는 활력징후, 용량, 검사 수치, 진단을 만들어 넣지 않습니다.
- 로그·커밋 메시지·채팅 답변에 환자 이름이나 식별번호를 적지 않습니다.
