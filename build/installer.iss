; Inno Setup 스크립트 — KakaoMacroSetup.exe 생성
;
; 컴파일:
;   iscc installer.iss
;
; 결과물:
;   KakaoMacroSetup.exe  (사용자에게 배포할 설치 마법사)
;
; 특징:
;   - 관리자 권한 불필요 (PrivilegesRequired=lowest)
;   - 사용자 프로그램 폴더에 설치
;   - 한국어 마법사, 시작 메뉴 + 바탕화면 아이콘
;   - 제거 프로그램 자동 등록

#define AppName "카카오톡 공지 댓글 매크로"
#define AppVersion "1.0.0"
#define AppPublisher "Local"
#define AppExeName "KakaoMacro.exe"
#define AppId "{{8C4A9D3E-2F1B-4A5C-9F6D-1E7B3A5C8D2F}"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}

; 사용자 로컬 설치 (관리자 권한 없음)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
DefaultDirName={autopf}\KakaoMacro
DefaultGroupName=KakaoMacro
DisableProgramGroupPage=yes

OutputBaseFilename=KakaoMacroSetup
OutputDir=.
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

; 언어 설정
LanguageDetectionMethod=locale
ShowLanguageDialog=auto

; 아키텍처 — x64 네이티브 + ARM64(x64 에뮬레이션) 모두 허용.
; "x64compatible"는 Inno Setup 6.3+에서 지원되며, 다음 조건에서 true:
;   - 진짜 x64 Windows
;   - ARM64 Windows에서 x64 에뮬레이션 가능 (Win11 ARM의 Prism 등)
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\KakaoMacro.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\config.example.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
; 주의: Source 경로는 installer.iss가 있는 build/ 기준으로 해석됨

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\사용 설명서"; Filename: "{app}\README.md"
Name: "{group}\제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 제거 시 사용자 설정은 기본적으로 보존한다.
; 완전히 지우려면 아래 줄의 주석을 해제:
; Type: files; Name: "{app}\config.json"
