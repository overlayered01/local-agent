# Local Agent

인터넷에 연결되지 않은 Windows 환경에서 로컬 LLM을 이용해 Unity 및 Unreal Engine 프로젝트를 분석하고 수정하는 코드 에이전트입니다.

## 목표

- 모든 추론과 코드 처리를 로컬에서 수행
- RTX 5060 공유 환경과 VRAM 24GB 이상 환경을 각각 지원
- 파일 검색, 코드 패치, 빌드 및 테스트 결과 확인을 하나의 작업 흐름으로 제공
- Unity 및 Unreal 에셋을 엔진 API를 통해 안전하게 처리
- 외부 네트워크 접근과 위험한 명령을 기본적으로 차단

## 예정 구성

```text
사용자 CLI
  -> Agent Loop
      -> llama.cpp OpenAI 호환 로컬 서버
      -> 저장소 검색 및 컨텍스트 관리
      -> 안전한 파일 패치와 Git diff
      -> Unity/Unreal 빌드 및 테스트 어댑터
```

## 하드웨어 프로필

| 프로필 | 초기 모델 권장값 | 컨텍스트 권장값 |
| --- | --- | --- |
| RTX 5060과 에디터 동시 사용 | 3B Q5 또는 7B Q4 GGUF | 8K~16K |
| VRAM 24GB와 에디터 동시 사용 | 14B~16B Q4 GGUF | 16K~32K |
| VRAM 24GB LLM 전용 | 30B급 Q4 GGUF | 16K~32K |

모델 파일은 저장소에 포함하지 않고 오프라인 배포 번들에서 별도로 관리합니다.

## 개발 순서

1. llama.cpp 로컬 서버 실행과 상태 확인 ✅
2. Python 기반 `ask` CLI 및 스트리밍 응답 ✅
3. 파일 목록, 읽기 전용 검색 및 분석 컨텍스트 수집 ✅
4. 패치 미리보기, 적용, Git diff 및 되돌리기
5. 명령 허용 목록, 타임아웃, 작업공간 경로 검증
6. Unity 컴파일 및 EditMode/PlayMode 테스트 연동
7. Unreal Build Tool, Automation Tool 및 Automation Test 연동
8. Unity Editor 및 Unreal Editor 전용 브리지 구현
9. 로컬 엔진 문서 인덱스와 회귀 평가 세트 구축

## 안전 원칙

- LLM이 임의의 셸 문자열을 직접 실행하지 않도록 합니다.
- 실행 파일과 인자를 구조화된 도구 요청으로 전달합니다.
- 모든 쓰기 대상은 허용된 작업공간 내부로 제한합니다.
- 삭제, 패키지 설치, 원격 Git 작업은 명시적인 승인을 요구합니다.
- Unreal의 `.uasset` 및 `.umap` 파일은 직접 수정하지 않습니다.
- Unity Scene 및 Prefab 변경은 가능한 경우 Unity Editor API를 사용합니다.

## 빠른 시작

Python 3.10 이상이 필요합니다. 저장소에는 외부 Python 런타임 의존성이 없습니다. Windows Python Launcher가 설치되어 있다면 별도 설치 없이 저장소의 실행 파일을 사용할 수 있습니다.

```powershell
.\local-agent.cmd --help
```

패키지 형태로 설치하려면 `py -m pip install -e .`을 실행한 뒤 `local-agent` 명령을 사용합니다. 빌드 도구를 내려받을 수 없는 오프라인 환경에서는 위의 `local-agent.cmd`를 사용합니다.

llama.cpp의 `llama-server.exe`와 GGUF 모델은 저장소 밖에 준비합니다. 서버는 셸 문자열을 통하지 않고 구조화된 인자 목록으로 실행됩니다.

```powershell
.\local-agent.cmd serve `
  --server C:\Tools\llama.cpp\llama-server.exe `
  --model D:\Models\model.gguf `
  --ctx-size 16384 `
  --gpu-layers 999
```

다른 터미널에서 서버 상태를 확인하고 질문할 수 있습니다.

```powershell
.\local-agent.cmd status
.\local-agent.cmd ask "C++에서 RAII를 간단히 설명해줘"
```

프로젝트 조사는 모델 없이도 동작합니다.

```powershell
.\local-agent.cmd inspect D:\Projects\MyGame
.\local-agent.cmd inspect D:\Projects\MyGame --search "PlayerController"
```

`analyze`는 질문과 관련도가 높은 텍스트 파일을 제한된 크기로 모아 로컬 서버에 전달합니다.

```powershell
.\local-agent.cmd analyze D:\Projects\MyGame "플레이어 점프 로직의 흐름을 설명해줘"
```

기본 서버 주소는 `http://127.0.0.1:8080`입니다. `--base-url` 또는 `LOCAL_AGENT_BASE_URL`로 변경할 수 있습니다. 루프백이 아닌 서버는 실수로 외부에 코드를 전송하지 않도록 차단되며, 필요한 경우에만 `--allow-remote`로 명시적으로 허용합니다. 모델 이름은 `--model` 또는 `LOCAL_AGENT_MODEL`로 지정합니다.

## 현재 안전 범위

- 프로젝트 조사는 읽기 전용이며 심볼릭 링크를 따라가지 않습니다.
- 파일당 512KB, 분석당 기본 48,000문자와 20개 파일로 제한합니다.
- `.env`, 모델 파일, Unity/Unreal 바이너리 에셋과 엔진 생성 디렉터리를 제외합니다.
- 서버 실행은 포그라운드에서 이뤄져 `Ctrl+C`로 종료할 수 있습니다.
- 현재 버전에는 파일 수정이나 임의 명령 실행 기능이 없습니다.

## 테스트

```powershell
$env:PYTHONPATH = "src"
py -m unittest discover -s tests -v
```

## 상태

첫 번째 구현 목표인 Windows용 llama.cpp 서버 실행, OpenAI 호환 스트리밍 질문, 로컬 프로젝트 읽기 전용 검색 및 분석 CLI가 구현되었습니다. 다음 단계는 안전한 패치 미리보기와 Git diff 작업 흐름입니다.
