# 진료 녹음 작업 폴더

`chart-summary` 스킬의 기본 작업 폴더입니다. **이 README를 제외한 모든 내용은
`.gitignore`로 제외**되어 저장소에 올라가지 않습니다.

> 시작 전에 [저장 위치 · 동의 절차 체크리스트](../.claude/skills/chart-summary/references/privacy-consent.md)를
> 먼저 확인하세요. 이 폴더가 OneDrive·iCloud·Dropbox 같은 동기화 폴더 안에 있으면
> `CHART_WORKSPACE` 환경변수로 로컬 경로를 따로 지정하세요.

## 폴더 구조 (처음 실행 시 자동 생성)

```
clinic/
├── inbox/          ← 여기에 넣으면 자동 처리 (초진/재진 판단을 Claude에 맡김)
│   ├── 초진/       ← 초진 양식으로 요약
│   └── 재진/       ← 재진 양식으로 요약
├── charts/YYYY-MM-DD/<파일명>_<초진|재진>.md   ← 요약 초안 (의사 확인용)
├── work/YYYY-MM-DD/<파일명>.txt               ← 로컬 전사 원문
├── archive/YYYY-MM-DD/                        ← 처리 끝난 녹음 원본
└── failed/                                    ← 실패 파일 + .error.txt
```

- 파일명은 환자 이름 대신 **차트번호**로: `재진/C12345_0930.m4a`
- 지원 형식: m4a, mp3, wav, aac, ogg, flac, webm, mp4, amr, 3gp, 그리고 이미 전사된 `.txt`

## 설치 (한 번)

1. Python 3.9 이상, [Claude Code](https://claude.com/claude-code) 설치 후 `claude` 로그인
2. 로컬 음성 인식 설치:
   ```bash
   pip install -r .claude/skills/chart-summary/requirements.txt
   ```
   첫 실행 때 Whisper 모델(large-v3, 약 3GB)을 한 번 내려받습니다. PC가 느리면
   `--model medium --compute-type int8`을 쓰세요.

## 실행

```bash
# 진료 시작할 때 켜 두기 (Ctrl+C로 종료)
python3 .claude/skills/chart-summary/scripts/watch_inbox.py

# 모아 둔 파일을 한 번에 처리하고 종료
python3 .claude/skills/chart-summary/scripts/watch_inbox.py --once

# 보관 정책 예: 요약 후 원본 즉시 삭제 / 7일 지나면 원본·전사본 삭제
python3 .claude/skills/chart-summary/scripts/watch_inbox.py --delete-audio
python3 .claude/skills/chart-summary/scripts/watch_inbox.py --purge-days 7
```

녹음 앱이 파일을 이 폴더(또는 `inbox/초진`, `inbox/재진`)에 저장하게 하거나,
진료 후 파일을 끌어다 놓으면 됩니다. 복사가 끝난 뒤 5초 동안 크기 변화가 없어야 처리합니다.

## 양식 바꾸기

`.claude/skills/chart-summary/references/format-initial.md`(초진),
`format-followup.md`(재진)를 병원 양식으로 고치면 다음 파일부터 반영됩니다.
자주 틀리는 약품명·용어는 `vocabulary.txt`에 추가하세요.
