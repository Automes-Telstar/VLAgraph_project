# VLA Graph / Isaac Sim / IsaacLab 연결 실행 정리

이 문서는 VLA Graph, Isaac Sim, `C:\isaac_exts`, IsaacLab, 새 bridge 프로젝트의 역할과 실행 방법을 정리한다.

## 아주 쉬운 실행 순서

처음에는 아래 순서만 따라 하면 된다.

```text
1. VLA Graph 켜기
2. Motion Learning Graph 선택
3. 사람 걷는 영상 업로드
4. Run Graph 실행
5. Motion Extract Node 클릭
6. Copy IsaacLab Command 누르기
7. 복사된 명령을 터미널에서 실행
8. IsaacLab viewer에서 학습 실행 확인
```

전체 구조를 몰라도 되는 최소 흐름은 이것이다.

```text
영상 업로드
  -> VLA Graph가 motion trace JSON 생성
  -> 복사한 IsaacLab 명령 실행
  -> IsaacLab에서 학습 시작
```

### 1. VLA Graph 실행

PowerShell에서: 

```powershell
cd C:\Users\0\Desktop\vlagraph
powershell -ExecutionPolicy Bypass -File scripts\docker-compose-up.ps1
```

브라우저에서 VLA Graph frontend를 연다. 보통 주소는 다음 중 하나다.

```text
http://localhost:9173
http://127.0.0.1:9173
```

### 2. Motion Learning Graph 선택

화면 상단의 `Graph Template`에서 다음을 선택한다.

```text
Motion Learning Graph
```

### 3. 영상 업로드

`Human Motion Video` 노드에서 `Upload Video`를 누른다.

처음 테스트 영상은 이런 것이 좋다.

```text
사람 한 명
전신이 보임
3~5초 걷는 영상
mp4 파일
```

예:

```text
C:\Users\0\Desktop\motions\walk.mp4
```

### 4. Run Graph 실행

상단의 `Run Graph` 버튼을 누른다.

성공하면 VLA Graph가 내부적으로 다음 파일을 만든다.

```text
C:\Users\0\Desktop\vlagraph\uploads\motion_traces\*.json
```

이 파일이 IsaacLab 학습에 넘길 motion trace 데이터셋이다.

### 5. IsaacLab 명령 복사

그래프에서 `Motion Extract Node`를 클릭한다.

오른쪽 Inspector에 다음 항목이 보이면 성공이다.

```text
IsaacLab 학습 준비 완료
trace: ...
frames: ...
Copy IsaacLab Command
```

`Copy IsaacLab Command` 버튼을 누른다.

### 6. IsaacLab 학습 실행

PowerShell 또는 명령 프롬프트를 열고 복사한 명령을 붙여넣어 실행한다.

복사 명령은 대략 이런 형태다.

```powershell
powershell -ExecutionPolicy Bypass -File "C:\vlagraph_isaaclab_bridge\scripts\train_isaaclab.ps1" -Trace "C:\Users\0\Desktop\vlagraph\uploads\motion_traces\walk_001.json" -Task Isaac-Cartpole-Direct-v0 -NumEnvs 1 -MaxIterations 200
```

처음에는 `Isaac-Cartpole-Direct-v0`로 연결 테스트를 한다. 실제 G1/휴머노이드 학습은 다음 단계에서 task를 바꿔야 한다.

### 7. 가장 최근 trace로 바로 실행하는 방법

Copy 버튼을 쓰지 않고, VLA Graph 프로젝트에서 가장 최근 생성된 trace를 바로 IsaacLab에 넘길 수도 있다.

```powershell
cd C:\Users\0\Desktop\vlagraph

powershell -ExecutionPolicy Bypass -File .\scripts\train-latest-motion-trace.ps1 `
  -Task Isaac-Cartpole-Direct-v0 `
  -NumEnvs 1 `
  -MaxIterations 200
```

이 방법은 `uploads\motion_traces` 폴더에서 가장 최근 JSON 파일을 자동으로 찾아서 실행한다.

### 8. 문제가 생겼을 때 확인할 것

영상 업로드는 됐는데 trace가 안 생기면:

```text
영상에 사람 전신이 보이는지 확인
영상이 너무 어둡거나 흔들리지 않는지 확인
Motion Extract Node의 오류 메시지 확인
```

IsaacLab 명령 실행이 안 되면:

```text
C:\vlagraph_isaaclab_bridge 폴더가 있는지 확인
C:\IsaacLab 폴더가 있는지 확인
Trace 경로의 JSON 파일이 실제로 있는지 확인
PowerShell 실행 정책 때문에 막히면 -ExecutionPolicy Bypass 사용
```

MediaPipe 패키지 충돌이 나오면:

```text
MediaPipe를 IsaacLab Python에 설치하지 말 것
MediaPipe는 VLA Graph .venv-motion 또는 Docker backend에서만 사용
```

## 핵심 결론

현재 구조는 하나의 프로그램으로 통합 실행하는 방식이 아니라, 각 프로그램을 별도로 실행하고 파일과 WebSocket으로 연결하는 방식이다.

```text
VLA Graph
  -> 영상 / 웹캠 / RealSense 입력
  -> MediaPipe motion trace JSON 생성
  -> 학습 상태 표시

Isaac Sim + C:\isaac_exts
  -> VLA Graph가 보낸 모션을 로봇에 재생
  -> 화면에서 모션 확인

C:\vlagraph_isaaclab_bridge
  -> VLA Graph trace를 IsaacLab 학습용으로 연결
  -> C:\isaac_exts의 G1 adapter를 import
  -> telemetry를 VLA Graph로 전송

IsaacLab
  -> 로봇 물리 시뮬레이션
  -> reward 계산
  -> RSL-RL / imitation learning 학습
  -> viewer에서 학습 상태 확인
```

한 줄로 정리하면 다음과 같다.

```text
모션 생성/데이터셋 저장: VLA Graph
모션 재생/시각 확인: Isaac Sim + C:\isaac_exts
학습 연결 레이어: C:\vlagraph_isaaclab_bridge
학습 실행: IsaacLab
```

## 추천 방식

현재 가장 안정적인 추천 흐름은 **파일 기반 motion trace 학습**이다.

```text
1. VLA Graph의 Motion Learning Graph에서 영상 업로드
2. Motion Extract가 motion trace JSON 생성
3. 필요하면 Isaac Sim + C:\isaac_exts에서 모션 재생 확인
4. C:\vlagraph_isaaclab_bridge로 trace JSON을 IsaacLab에 전달
5. IsaacLab에서 viewer를 켜고 학습
6. 학습 telemetry를 VLA Graph에서 확인
```

추천하는 이유:

```text
MediaPipe와 IsaacLab Python 환경 충돌을 피할 수 있음
영상/센서 입력을 재사용 가능한 데이터셋으로 남길 수 있음
Isaac Sim 확인 단계와 IsaacLab 학습 단계를 분리해 디버깅하기 쉬움
RealSense 실시간 입력보다 먼저 안정적인 학습 루프를 만들 수 있음
```

템플릿 선택 기준:

```text
Motion Learning Graph
  -> 추천 기본값
  -> mp4 업로드
  -> motion trace JSON 생성
  -> IsaacLab 학습 데이터셋으로 사용

RealSense RGB-D Follow
  -> 실시간 추적/따라가기 확인용
  -> RGB-D pose 품질 확인
  -> 학습에 쓰려면 pose sequence를 trace JSON으로 저장하는 단계가 추가로 필요
```

따라서 지금 단계에서는 다음 순서가 좋다.

```text
먼저 Motion Learning Graph로 trace JSON 생성
-> IsaacLab 학습 연결 확인
-> 그 다음 RealSense RGB-D Follow 결과를 trace로 저장하도록 확장
-> 마지막에 live pose endpoint 기반 실시간 IsaacLab 연결로 확장
```

현재 추천 실행 경로:

```text
VLA Graph Motion Learning Graph
  -> uploads\motion_traces\walk_001.json
  -> C:\vlagraph_isaaclab_bridge\scripts\train_isaaclab.ps1
  -> IsaacLab train.py
```

개발 반영 사항:

```text
Motion Extract 실행 결과에 trace_path_host, isaaclab_bridge, train_command가 포함됨
VLA Graph Inspector에서 Motion Extract 노드를 선택하면 IsaacLab 실행 명령을 복사할 수 있음
scripts\train-latest-motion-trace.ps1로 가장 최근 trace를 바로 IsaacLab에 넘길 수 있음
```

## 실행 방식

프로세스는 별도로 실행한다.

```text
VLA Graph backend/frontend
Isaac Sim
IsaacLab train.py
```

하지만 기능적으로는 연결된다.

```text
motion trace JSON
  VLA Graph -> IsaacLab

WebSocket telemetry
  IsaacLab -> VLA Graph

Isaac Sim bridge
  VLA Graph -> Isaac Sim
```

즉 “별도 실행”이지만 “연결되지 않은 독립 프로그램”은 아니다.

## MediaPipe와 IsaacLab 환경 분리

MediaPipe는 IsaacLab Python 환경에 설치하지 않는다.

이유는 MediaPipe가 `numpy<2`, `protobuf 4.x` 계열을 요구할 수 있고, IsaacLab은 `numpy>=2`, `protobuf>=6.31.1,<7` 계열을 요구하기 때문이다.

정상 분리 구조:

```text
C:\Users\0\Desktop\vlagraph\.venv-motion
  -> MediaPipe 영상 추출용

C:\IsaacLab\isaaclab.bat -p
  -> IsaacLab 학습용
```

IsaacLab 환경이 MediaPipe 설치로 깨졌다면 복구:

```powershell
cd C:\IsaacLab

.\isaaclab.bat -p -m pip uninstall -y mediapipe opencv-contrib-python
.\isaaclab.bat -p -m pip install "numpy>=2" "protobuf>=6.31.1,<7" "psutil==5.9.8"
.\isaaclab.bat -p -m pip check
```

## 1. VLA Graph에서 motion trace 만들기

MediaPipe 전용 가상환경을 사용한다.

motion trace가 필요한 이유는 IsaacLab이 `mp4` 영상을 그대로 학습 입력으로 쓰는 구조가 아니기 때문이다. IsaacLab의 reward/action 계산에는 시간별 관절 위치, 몸 중심 이동, 팔/다리 각도, 이동 방향 같은 숫자 데이터가 필요하다.

```text
원본 영상
  -> MediaPipe pose 추출
  -> landmark / angle / timestamp 저장
  -> motion trace JSON
  -> IsaacLab reward/action target
```

따라서 trace는 “사람 영상을 로봇 학습에 쓸 수 있는 숫자 데이터셋으로 바꾼 중간 파일”이다.

방법은 두 가지다.

```text
방법 A: VLA Graph UI의 Motion Learning Graph에서 영상 업로드
방법 B: 로컬 스크립트 scripts\extract_video_motion.py 직접 실행
```

보통은 방법 A가 더 자연스럽다. VLA Graph 템플릿의 `Motion Learning Graph`에서 `Human Motion Video` 노드에 영상을 업로드하고 `Run Graph`를 실행하면 `Motion Extract` 노드가 motion trace JSON을 만든다.

```text
VLA Graph frontend
  -> Graph Template: Motion Learning Graph
  -> Human Motion Video 노드
  -> Upload Video
  -> Run Graph
  -> Motion Extract 결과의 trace_path 확인
```

이때 저장되는 trace는 보통 다음 위치 아래에 생성된다.

```text
C:\Users\0\Desktop\vlagraph\uploads\motion_traces
```

따라서 `C:\Users\0\Desktop\motions\walk.mp4` 같은 로컬 영상 파일을 직접 명령어에 넣지 않아도 된다. VLA Graph 화면에서 영상을 업로드해 생성된 `trace_path`를 IsaacLab 학습 단계에 넘기면 된다.

실행 후에는 `Motion Extract Node`를 클릭해 Inspector를 확인한다. 성공하면 다음 정보가 표시된다.

```text
trace
frames
Copy IsaacLab Command
```

`Copy IsaacLab Command`를 눌러 복사한 명령을 PowerShell 또는 cmd에서 실행하면 된다.

로컬 스크립트 방식이 필요한 경우는 VLA Graph UI를 거치지 않고 빠르게 trace만 만들고 싶을 때다.

입력 영상은 사람이 걷는 모습이면 된다. 처음 테스트용으로는 3~5초 정도의 짧은 전신 걷기 영상이 좋다.

좋은 영상 조건:

```text
사람 전신이 화면에 나옴
머리부터 발까지 잘리지 않음
한 명만 나옴
너무 어둡지 않음
카메라가 심하게 흔들리지 않음
2~10초 정도
mp4 권장
```

피하는 것이 좋은 영상:

```text
상반신만 나오는 영상
발이 안 보이는 영상
여러 사람이 동시에 나오는 영상
걷기와 다른 동작이 많이 섞인 영상
너무 긴 영상
```

```powershell
cd C:\Users\0\Desktop\vlagraph

python -m venv .venv-motion
.\.venv-motion\Scripts\python.exe -m pip install -r scripts\requirements-motion.txt
```

영상에서 trace 생성:

```powershell
.\.venv-motion\Scripts\python.exe scripts\extract_video_motion.py `
  --video C:\Users\0\Desktop\motions\walk.mp4 `
  --output uploads\motion_traces\walk_001.json `
  --label walk_forward `
  --prompt "walk forward"
```

생성되는 파일 예:

```text
C:\Users\0\Desktop\vlagraph\uploads\motion_traces\walk_001.json
```

## 1-1. RealSense RGB-D Follow와의 차이

`RealSense RGB-D Follow`도 같은 계열의 입력 처리 방식이지만, 목적이 다르다.

```text
Motion Learning Graph
  -> 업로드 영상 파일 사용
  -> 전체 프레임 분석
  -> motion trace JSON 저장
  -> IsaacLab 학습 데이터셋으로 바로 쓰기 좋음

RealSense RGB-D Follow
  -> RealSense 카메라 실시간 RGB-D 입력 사용
  -> 현재 사람 pose를 계속 추적
  -> live follow / 실시간 retargeting 확인에 적합
  -> IsaacLab 학습에 쓰려면 pose sequence를 trace JSON으로 저장하는 단계가 필요
```

따라서 추천 순서는 다음과 같다.

```text
1. Motion Learning Graph로 파일 기반 trace 학습 루프 먼저 안정화
2. RealSense RGB-D Follow로 실시간 pose 품질 확인
3. RealSense 결과를 trace JSON으로 저장하도록 확장
4. 마지막에 live pose endpoint를 IsaacLab이 직접 읽는 구조로 확장
```

지금 단계에서는 RealSense를 바로 학습 입력으로 연결하기보다, 먼저 Motion Learning Graph에서 생성한 trace JSON으로 IsaacLab 연결을 검증하는 것이 안전하다.

## 2. Isaac Sim에서 모션 확인

모션 확인은 다음 조합으로 한다.

```text
Isaac Sim
  + C:\isaac_exts\robotis.omy.motion
  + C:\isaac_exts\vlagraph.bridge.autostart
```

역할:

```text
VLA Graph에서 영상/포즈/명령 생성
-> Isaac Sim bridge로 전송
-> C:\isaac_exts extension이 수신
-> Isaac Sim 안의 로봇에 모션 적용
-> 화면에서 동작 확인
```

이 단계는 학습이 아니라 모션 재생과 시각 확인용이다.

일반 흐름:

```text
1. Isaac Sim 실행
2. Extension Manager에서 C:\isaac_exts 추가
3. robotis.omy.motion 활성화
4. vlagraph.bridge.autostart 활성화
5. VLA Graph 실행
6. Motion Learning Graph 실행
7. Isaac Sim 로봇 움직임 확인
```

## 3. 새 bridge 프로젝트

새 프로젝트 위치:

```text
C:\vlagraph_isaaclab_bridge
```

역할:

```text
VLA Graph motion trace
  -> 새 bridge 프로젝트 loader
  -> C:\isaac_exts retarget / G1 adapter
  -> IsaacLab reward wrapper
  -> VLA Graph telemetry
```

구성:

```text
C:\vlagraph_isaaclab_bridge
  ├─ README.md
  ├─ pyproject.toml
  ├─ examples\isaaclab\vlagraph_motion_imitation.py
  ├─ src\vlagraph_isaaclab_bridge
  │   ├─ motion_trace.py
  │   ├─ g1_adapter.py
  │   ├─ telemetry.py
  │   └─ wrapper.py
  └─ scripts
      ├─ check_bridge.ps1
      ├─ extract_motion_trace.ps1
      └─ train_isaaclab.ps1
```

IsaacLab의 기존 `--vlagraph_repo` import 방식과 호환되도록 `examples\isaaclab\vlagraph_motion_imitation.py` 경로를 제공한다.

## 4. bridge import 확인

PowerShell:

```powershell
cd C:\vlagraph_isaaclab_bridge
powershell -ExecutionPolicy Bypass -File .\scripts\check_bridge.ps1
```

성공 출력:

```text
bridge import ok
```

## 5. IsaacLab에서 학습 실행

IsaacLab은 학습을 담당한다.

```text
1. VLA Graph motion trace JSON 읽기
2. MediaPipe 모션을 target action 또는 G1 joint target으로 변환
3. IsaacLab task 안에서 로봇 시뮬레이션
4. 기존 task reward에 imitation reward 추가
5. RSL-RL로 policy 학습
6. 학습 상태를 VLA Graph WebSocket으로 전송
```

PowerShell 실행:

```powershell
cd C:\vlagraph_isaaclab_bridge

powershell -ExecutionPolicy Bypass -File .\scripts\train_isaaclab.ps1 `
  -Trace C:\Users\0\Desktop\vlagraph\uploads\motion_traces\walk_001.json `
  -Task Isaac-Cartpole-Direct-v0 `
  -NumEnvs 1 `
  -MaxIterations 200
```

VLA Graph 프로젝트에서 가장 최근 생성된 trace를 바로 학습에 넘기려면:

```powershell
cd C:\Users\0\Desktop\vlagraph

powershell -ExecutionPolicy Bypass -File .\scripts\train-latest-motion-trace.ps1 `
  -Task Isaac-Cartpole-Direct-v0 `
  -NumEnvs 1 `
  -MaxIterations 200
```

`NumEnvs 1`은 viewer에서 보기 쉽게 하기 위한 값이다. 많은 병렬 환경으로 학습하려면 64 이상으로 늘릴 수 있다.

## 6. cmd.exe에서 실행

명령 프롬프트에서는 PowerShell의 백틱 줄바꿈을 사용할 수 없다.

PowerShell 줄바꿈:

```text
`
```

cmd 줄바꿈:

```text
^
```

cmd 한 줄 실행:

```bat
cd /d C:\vlagraph_isaaclab_bridge

powershell -ExecutionPolicy Bypass -File .\scripts\train_isaaclab.ps1 -Trace C:\Users\0\Desktop\vlagraph\uploads\motion_traces\walk_001.json -Task Isaac-Cartpole-Direct-v0 -NumEnvs 1 -MaxIterations 200
```

cmd 여러 줄 실행:

```bat
cd /d C:\vlagraph_isaaclab_bridge

powershell -ExecutionPolicy Bypass -File .\scripts\train_isaaclab.ps1 ^
  -Trace C:\Users\0\Desktop\vlagraph\uploads\motion_traces\walk_001.json ^
  -Task Isaac-Cartpole-Direct-v0 ^
  -NumEnvs 1 ^
  -MaxIterations 200
```

## IsaacLab에서 모션 확인도 가능한가

가능하다. IsaacLab도 내부적으로 Isaac Sim/Kit viewer를 사용하기 때문에 `--headless` 없이 실행하면 viewer에서 로봇을 볼 수 있다.

다만 현재 구현 상태는 다음과 같다.

```text
IsaacLab viewer 표시: 가능
motion trace를 reward로 사용: 가능
VLA Graph telemetry 전송: 가능
G1 로봇에 motion trace를 정확히 직접 재생: 추가 작업 필요
```

즉 IsaacLab에서도 화면 확인은 가능하지만, Isaac Sim extension처럼 VLA Graph 모션을 G1/KyleRobot에 바로 재생하는 preview 기능은 아직 별도 스크립트가 필요하다.

다음 단계로 만들 기능:

```text
preview_motion_in_isaaclab.py
preview_motion_in_isaaclab.ps1
```

목표:

```text
VLA Graph trace
  -> IsaacLab viewer
  -> G1 로봇에 joint target 적용
  -> 학습 전 모션 preview
```

## 현재와 목표 구조

현재 구조:

```text
VLA Graph
  -> motion trace JSON 생성

Isaac Sim + C:\isaac_exts
  -> 모션 재생/확인

C:\vlagraph_isaaclab_bridge
  -> motion trace를 IsaacLab reward wrapper로 연결

IsaacLab
  -> 학습 실행
```

목표 구조:

```text
VLA Graph
  -> motion trace 또는 live pose 생성

IsaacLab
  -> G1/Humanoid 환경 로드
  -> motion trace preview
  -> MediaPipe/G1 joint target을 action space에 매핑
  -> imitation reward + balance/speed/contact reward
  -> policy 학습
  -> VLA Graph로 telemetry 전송
```

## 다음 개발 단계

```text
1. Cartpole으로 bridge 연결 확인
2. IsaacLab에서 사용할 G1/Humanoid task 선택
3. G1 task의 action dimension과 joint order 확인
4. C:\isaac_exts의 IsaacLabDigitalHumanAdapter 출력을 task action으로 변환
5. IsaacLab viewer용 motion preview 스크립트 추가
6. imitation reward에 balance, velocity, foot contact, smoothness reward 결합
7. VLA Graph 버튼에서 IsaacLab 실행까지 자동화
```
