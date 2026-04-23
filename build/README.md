# .exe 빌드 가이드

일반 사용자에게 `.exe` 하나만 건네주고 싶을 때 이 폴더의 스크립트들을 사용합니다.

## 결과물

| 파일 | 설명 |
|------|------|
| `dist/KakaoMacro.exe` | 단일 실행 파일 (~30MB). 설치 없이 바로 실행 가능. USB/이메일로 배포 가능. |
| `KakaoMacroSetup.exe` | 설치 마법사. 더블클릭 → 다음/다음/마침 → 시작 메뉴·바탕화면에 아이콘 생성 + 제거 프로그램 등록. |

사용자에게는 **`KakaoMacroSetup.exe` 하나만 전달**하면 됩니다.

## 빌드하는 두 가지 방법

### 방법 1: Windows PC에서 로컬 빌드

**사전 설치:**
- Python 3.12 (루트의 `install.bat`을 실행했다면 이미 있음)
- **Inno Setup 6** (설치 마법사가 필요한 경우만) — <https://jrsoftware.org/isdl.php>

**실행:**

```cmd
cd build
build.bat
```

스크립트가 자동으로:
1. `pyinstaller` 및 의존성 설치
2. `KakaoMacro.spec`로 `dist/KakaoMacro.exe` 생성
3. `iscc installer.iss`로 `KakaoMacroSetup.exe` 생성 (Inno Setup이 있을 때만)

Inno Setup이 없으면 `dist/KakaoMacro.exe` 단일 파일만 생성됩니다. 이 파일 자체를 배포해도 됩니다.

### 방법 2: GitHub Actions로 클라우드 빌드

Windows PC가 없거나 자동화를 원한다면 이 방법이 편합니다.

**수동 실행:**
1. 이 레포를 GitHub에 push
2. Actions 탭 → `Build Windows .exe` 워크플로 선택 → `Run workflow`
3. 5~10분 뒤 Artifacts에서 `KakaoMacro-Windows.zip` 다운로드

**태그 기반 자동 릴리스:**

```bash
git tag v1.0.0
git push origin v1.0.0
```

워크플로가 자동으로 빌드하고 GitHub Release 페이지에 `.exe` 두 개를 업로드합니다. 최종 사용자는 Release 페이지에서 바로 받을 수 있습니다.

## 파일 설명

```
build/
├── KakaoMacro.spec      # PyInstaller 설정 (단일 windowed exe)
├── version_info.txt     # .exe 속성에 표시될 버전 정보
├── installer.iss        # Inno Setup 스크립트 (설치 마법사)
├── build.bat            # 로컬 빌드 원클릭
├── icon.ico             # (선택) 커스텀 아이콘. 있으면 자동 적용
└── README.md            # 이 문서
```

## 사용자 관점의 흐름

빌드된 `KakaoMacroSetup.exe`를 받은 최종 사용자:

1. 다운로드한 `KakaoMacroSetup.exe` 더블클릭
2. Windows SmartScreen 경고(서명되지 않은 앱) → `추가 정보` → `실행`
   - 이 경고는 코드 서명 인증서($$$)가 없으면 피할 수 없습니다. 정상입니다.
3. 설치 마법사 → `다음` × 몇 번 → `설치` → `마침`
4. 바탕화면 아이콘 더블클릭 → GUI 뜸
5. 좌표 캡처 → 댓글 작성 → 목표 시각 설정 → 실행

## 알려진 제한

- **코드 서명 없음**: SmartScreen 경고 피하려면 Code Signing Certificate 필요 (연 $100~$400). 사내 배포면 생략 가능.
- **안티바이러스 오탐**: PyInstaller 빌드물은 일부 AV에서 오탐할 수 있음. 특히 `keyboard` 같은 키 훅 라이브러리 포함 시 더 잦음. VirusTotal에 업로드해 확인 후 배포 권장.
- **크기**: 단일 exe ~30MB, 인스톨러 ~30MB. tkinter + Python 런타임이 포함되어 불가피.
- **macOS/Linux 빌드 불가**: PyInstaller는 크로스 컴파일 지원이 없습니다. Windows 러너(로컬 or Actions)가 반드시 필요합니다.

## 트러블슈팅

| 증상 | 원인 / 대응 |
|------|------|
| `pyinstaller: command not found` | `pip install pyinstaller` 먼저 |
| `ISCC is not recognized` | Inno Setup 미설치. <https://jrsoftware.org/isdl.php>에서 설치 |
| `KakaoMacro.exe` 실행 시 아무 반응 없음 | `app.py`의 예외 처리로 메시지박스가 뜨지 않으면 콘솔 빌드로 재시도: spec의 `console=False` → `True` |
| SmartScreen에서 차단 | "추가 정보" → "실행". 코드 서명이 없는 모든 exe에서 발생하는 정상 경고 |
| 바이러스로 인식됨 | `keyboard` 모듈 때문일 가능성. `requirements.txt`에서 제외 후 CLI 캡처 대신 GUI의 `3초 후 캡처`만 쓰면 동작엔 문제 없음 |
