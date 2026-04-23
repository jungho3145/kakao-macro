# 카카오톡 공지 댓글 매크로

Windows 환경에서 카카오톡 데스크톱 앱의 공지사항에 **정해진 시각에 맞춰 자동으로
댓글을 다는** 매크로입니다. 한국 NTP 서버(카카오 서버와 같은 시간원)로 시계를
동기화하고, 사전에 캡처한 클릭 좌표 + 클립보드 붙여넣기로 한글 댓글을 전송합니다.

## 왜 이 방식인가 (First Principles)

| 제약 | 결과 |
|------|------|
| 카카오톡은 공지 댓글용 공개 API가 없음 | UI 자동화가 유일한 방법 |
| 공지 UI는 커스텀 렌더링이라 UI Automation 트리로 식별 불가 | **좌표 기반 클릭** |
| 한글 직접 타이핑은 IME가 깨뜨림 | **클립보드 복사 → Ctrl+V** |
| "카카오톡 서버 시간"은 공개되지 않음. 카카오는 KST를 KRISS에 싱크 | **국내 NTP 오프셋**을 프록시로 사용 |
| Windows `time.sleep` 해상도 ~15ms | 마지막 50ms는 **busy-wait** |

## 설치 (Windows)

일반 사용자(IT 지식 없음)에게 배포할 거라면 **방법 C(.exe 설치 마법사)** 를 쓰세요. 배포자가 한 번 빌드하면, 최종 사용자는 `KakaoMacroSetup.exe` 더블클릭만 하면 됩니다. 빌드 방법은 [`build/README.md`](./build/README.md) 참고.

### 방법 A — 원클릭 설치기 (Python이 설치되어 있지 않아도 됨)

1. 이 폴더 전체를 Windows PC에 복사
2. `install.bat` 더블클릭
3. 완료되면 `run_macro.bat` 더블클릭으로 GUI 실행

설치기는 이렇게 동작합니다:
- Python 3.12를 python.org에서 다운로드
- **관리자 권한 없이** 이 폴더 내부(`./python/`)에만 설치 — 시스템 PATH/레지스트리 안 건드림
- tkinter, pip 포함
- `requirements.txt`의 의존성 자동 설치

제거는 `uninstall.bat` 더블클릭 (또는 폴더 통째로 삭제).

### 방법 B — 이미 Python이 있다면

```powershell
# Python 3.11 이상 권장
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> `keyboard` 모듈은 전역 키 훅을 걸기 때문에 Windows에서 **관리자 권한**이 필요할
> 수 있습니다. CLI 캡처 도구가 동작하지 않으면 관리자 권한으로 터미널을 여세요.
> GUI의 `3초 후 캡처`는 관리자 권한 없이 동작합니다.

## 사용법

### 1) GUI로 사용 (추천)

설치기로 깔았다면 `run_macro.bat` 더블클릭. 수동 설치라면:

```powershell
python run.py gui
```

한 화면에서 좌표 추가 → 댓글 입력 → 목표 시각 설정 → 실행까지 끝냅니다.

**좌표 추가 흐름:**
1. 카카오톡에서 댓글을 달 공지를 직접 찾아서 **댓글 입력창이 보이는 상태**로 둡니다.
2. GUI의 `3초 후 캡처` 버튼 → 3초 안에 댓글 입력창 위로 마우스 이동.
3. 필요하면 공지 진입 흐름도 순서대로 캡처 (공지 열기 → 공지 선택 → 댓글 입력창).

### 2) CLI로 사용

```powershell
# 서버 시간 확인
python run.py now

# 좌표 캡처 (F9: 저장, Esc: 취소)
python run.py capture -n 3

# 설정 파일(config.json)을 기반으로 예약 실행
python run.py run

# 실제 클릭 없이 로그만 (리허설)
python run.py dry-run

# 시간 대기 없이 즉시 실행 (테스트용)
python run.py run --no-wait
```

`config.example.json`을 복사해 `config.json`으로 수정하세요.

```json
{
  "click_positions": [[1200, 880]],
  "comment_text": "참여합니다!",
  "target_time_kst": "2026-04-23 20:00:00",
  "submit_with_enter": true,
  "step_delay_seconds": 0.25,
  "window_title_contains": "카카오톡"
}
```

## 동작 순서

1. NTP로 로컬 시계 오프셋 산출 (`time.bora.net` → `kr.pool.ntp.org` → `time.kriss.re.kr`)
2. 목표 시각 5초 전: 카카오톡 창을 전면으로 활성화
3. 목표 시각 50ms 전: busy-wait로 전환해 정밀도 확보
4. 설정된 좌표들을 순서대로 클릭
5. 댓글 본문을 클립보드에 복사 → Ctrl+V
6. Enter(또는 Ctrl+Enter)로 전송

## 한계와 주의

- **API 사용이 아닌 UI 자동화**입니다. 카카오톡이 업데이트되어 화면 좌표가 바뀌면
  좌표를 다시 캡처해야 합니다.
- **카카오톡 약관**을 확인하세요. 자동화된 동작은 제재 대상이 될 수 있습니다.
  본인 책임하에 사용하세요.
- **해상도/스케일 고정**: 모니터 DPI 스케일과 카카오톡 창 위치/크기가 캡처 당시와
  같아야 좌표가 맞습니다.
- **포커스**: 실행 시점에 다른 창이 위를 덮고 있으면 실패합니다. 스케줄러가 5초
  전에 카카오톡 창을 활성화하지만, 전체화면 게임/비디오 앞에서는 동작이 불안정
  합니다.
- **NTP 정확도**: 일반 가정용 네트워크에서 ±10ms 수준. 미션 크리티컬한 ms 단위
  정밀도가 필요한 용도에는 적합하지 않습니다.

## 파일 구조

```
kakao-macro/
├── install.bat                # [소스 배포] 원클릭 설치기 (Python 자동)
├── run_macro.bat              # GUI 실행
├── run_macro_cli.bat          # CLI 쉘
├── uninstall.bat              # 제거
├── app.py                     # .exe용 GUI 엔트리
├── run.py                     # 개발자용 CLI 엔트리
├── requirements.txt
├── config.example.json
├── src/
│   ├── config.py              # 설정 직렬화
│   ├── time_sync.py           # NTP 오프셋
│   ├── scheduler.py           # 정밀 스케줄러
│   ├── position_capture.py    # 좌표 캡처(CLI)
│   ├── kakao_automation.py    # 창 포커스·클릭·붙여넣기
│   └── gui.py                 # Tkinter GUI
├── build/                     # [배포자용] .exe 빌드
│   ├── build.bat              # 원클릭 빌드
│   ├── KakaoMacro.spec        # PyInstaller 설정
│   ├── installer.iss          # Inno Setup 스크립트
│   ├── version_info.txt       # .exe 버전 정보
│   └── README.md              # 빌드 가이드
├── .github/workflows/
│   └── build-windows.yml      # CI 자동 빌드 (GitHub Actions)
└── README.md
```

## 트러블슈팅

| 증상 | 원인 / 대응 |
|------|------|
| 한글이 깨져 입력됨 | IME 문제. 이 매크로는 이미 클립보드 붙여넣기를 사용하므로, 발생 시 입력창이 한글 모드로 전환됐는지 확인 — 한글 모드라도 붙여넣기는 정상이어야 합니다. |
| 클릭이 엉뚱한 위치에 됨 | 카카오톡 창 위치/크기가 캡처 당시와 달라짐. 좌표 재캡처. |
| 창 활성화가 안 됨 | `window_title_contains`를 실제 창 제목에 맞게 수정 (예: `KakaoTalk`). |
| NTP 동기화 실패 | 방화벽이 UDP/123을 차단. `time.google.com`까지 fallback되지만 그래도 실패하면 네트워크 확인. |
| `keyboard` 모듈이 안 됨 | Windows 관리자 권한으로 실행. |
