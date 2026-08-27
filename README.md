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

1. llama.cpp 로컬 서버 실행과 상태 확인
2. Python 기반 `ask` CLI 및 스트리밍 응답
3. 파일 목록, 부분 읽기, `rg` 검색 도구
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

## 상태

현재 저장소는 초기 설계 단계입니다. 첫 번째 구현 목표는 Windows에서 llama.cpp 서버를 실행하고 로컬 프로젝트를 읽기 전용으로 분석하는 CLI입니다.
