# Android Embedded Device Configurator v1.0

> 안드로이드 기반 임베디드 기기(Smart Wallpad 등)의 환경 설정(Config) 진단 및 OTA 업데이트 자동화를 위한 다중 런타임 지원 파이프라인 엔진입니다. 현업 배포 환경의 제약 조건을 극복하기 위해 레거시 매크로에서 업계 표준 프레임워크를 거쳐 독자적인 경량 파싱 엔진으로 진화시킨 기술적 여정을 담고 있습니다.

---

## 🚀 1. 기능 설명 (Core Pipeline Architecture)

본 프로젝트는 단말기 제어 요구사항에 맞추어 점진적으로 진화된 **3가지 자동화 런타임 모드**를 제공합니다. 사용자는 구동 환경 및 종속성 제약에 따라 유연하게 모드를 선택하여 실행할 수 있습니다.

### 🔹 1단계: Legacy Coordinate Macro Mode (Approach 3)
* **방식**: 안드로이드 순정 `input keyevent` 및 하드코딩된 물리 좌표(`input tap x y`) 주입 기반 매크로.
* **특징**: 가장 직관적이고 빠른 프로토타입 구현 방식이나, 디바이스 해상도 가변성 및 프레임 드랍 발생 시 하드코딩의 한계로 오작동 위험이 존재함을 파악했습니다.

### 🔹 2단계: Appium WebDriver Framework (Approach 2)
* **방식**: UI 요소를 객체(Resource-ID, Text, XPATH) 단위로 추적하는 글로벌 업계 표준 테스트 프레임워크 연동.
* **특징**: 코드의 구조적 안정성을 대폭 확보하고 요소 탐색 신뢰성을 올렸으나, 필드(타 부서 및 현장 엔지니어 PC) 배포 시 Node.js 환경 및 Appium 서버 상시 구동이라는 무거운 종속성(Dependency)이 발생하는 비즈니스 제약 조건을 발견했습니다.

### 🔹 3단계: Optimized Pure UiAutomator Engine (Approach 1 - *최종 선택*)
* **방식**: 외부 무거운 프레임워크 없이, 단말기 내장 `uiautomator.jar` 엔진의 XML 덤프 파일과 파이썬 표준 `ElementTree` 라이브러리를 결합한 지능형 오브젝트 추적 엔진.
* **특징**:
    * Appium의 동작 원리를 역이용하여 백그라운드 서버 없이 **"더블클릭으로 즉시 구동되는 단일 파일(.exe)"** 경량 배포 체계 완성.
    * 실시간으로 화면의 XML 노드를 파싱하여 요소의 정중앙 좌표를 자동 계산 후 정밀 타격.
    * 요소 탐색 실패 시 엉뚱한 설정을 건드리지 않고 즉시 격리 종료하는 **Fail-Safe 메커니즘** 구현.

---

## 🛠️ 2. 사전 준비물 및 환경 구성 가이드 (Prerequisites)

구동하고자 하는 아키텍처 모드에 따라 아래 가이드를 참고하여 환경을 빌드합니다. (최종 빌드된 `pure_uiautomator` 모드 단독 사용 시 별도의 환경 구성 없이 즉시 실행 가능합니다.)

### 🐍 Python 기본 환경 구축 (전체 공통)
1. [Python 공식 홈페이지](https://www.python.org/)에서 대상 OS에 맞는 버전을 설치합니다.
2. 설치 시 반드시 **"Add Python to PATH"** 옵션을 체크하여 환경 변수를 등록합니다.

### ☕ Appium 통합 테스트 환경 구축 (Approach 2 가이드)
본 프로젝트의 Appium 웹드라이버 프로토타입 라인을 디버깅하거나 확장하기 위해서는 아래의 종속성 인프라 설치가 필요합니다.

1. **Node.js 설치**: Appium 서버의 베이스가 되는 [Node.js](https://nodejs.org/)를 설치합니다.
2. **Appium 서버 설치**: 터미널(CMD/PowerShell)을 열고 글로벌 옵션으로 서버를 설치합니다.
   ```bash
   npm install -g appium
3. **UiAutomator2 드라이버 연동**: 안드로이드 제어를 위한 핵심 드라이버를 추가합니다.
   ```bash
   appium driver install uiautomator2
4. **Python Appium Client 설치**: 프로젝트 소스코드와 Appium 서버 간의 통신을 위한 라이브러리를 바인딩합니다.
   ```bash
   pip install Appium-Python-Client

---

## 📊 3. 환경 및 버전 정보 (Environment Specifications)

본 아키텍처 설계 및 검증 당시 사용된 정식 호환 소프트웨어 및 프레임워크의 빌드 스펙 명세입니다.

| 기술 스택 (Tech Stack) | 검증 버전 (Verified Version)                  | 비고 (Remarks)                        |
| :--- |:------------------------------------------|:------------------------------------|
| **Python** | `v3.11.x` 이상                              | 메인 스크립트 런타임 및 GUI(Tkinter) 코어       |
| **Android ADB** | `Android Debug Bridge version 1.0.41`     | 프로젝트 내부 임베딩 처리 완료 (Platform-Tools)  |
| **Appium Server** | `v2.x`                                    | `UiAutomator2 Driver v2.x` 호환 규격 명세 |
| **UiAutomator Engine** | `UiAutomator V1 (uiautomator.jar)`        | 안드로이드 임베디드 단말기 내부 내장 순정 바이너리 스펙     |
| **Target OS (Device)** | `Android 7.1.2 (Nougat)` | API 레벨 25 임베디드 월패드 타겟 디바이스 명세       |

---

## 📦 4. 배포판 빌드 방법 (PyInstaller One-File)

사용자 PC의 환경 변수 오염 및 종속성 간섭을 차단하기 위해 단일 포터블 실행 파일(.exe)로 패키징하는 명령어입니다.
   ```bash
   pyinstaller -F --clean -n "Configurator v1.0" --add-data "adbkey;." --add-data "adbkey.pub;." --add-data "adb.exe;." --add-data "AdbWinApi.dll;." --add-data "AdbWinUsbApi.dll;." main.py