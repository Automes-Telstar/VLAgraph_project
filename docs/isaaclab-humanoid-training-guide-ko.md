# VLAGRAPH + IsaacLab 휴머노이드 훈련 방법

이 문서는 사람의 전신 동작 영상을 VLAGRAPH에서 처리하고, 저장된 모션 데이터를 IsaacLab 휴머노이드 학습에 사용하는 방법을 설명한다.

## 1. 전체 학습 흐름

```text
사람 전신 동작 영상
  → VLAGRAPH Motion Learning Graph
  → MediaPipe 전신 포즈 추출
  → motion trace JSON 저장
  → 휴머노이드 학습 JSONL 저장
  → IsaacLab Bridge
  → G1/휴머노이드 관절 목표 생성
  → 모방학습 + 균형 강화학습
  → 학습된 policy/checkpoint 저장
```

각 프로그램의 역할은 다음과 같다.

| 구성 요소 | 역할 |
|---|---|
| VLAGRAPH | 영상 업로드, 포즈 추출, 의미 해석, 데이터 저장 |
| MediaPipe 환경 | 사람의 전신 랜드마크 추출 |
| IsaacLab Bridge | VLAGRAPH 데이터를 IsaacLab 입력과 보상으로 변환 |
| IsaacLab | 물리 시뮬레이션, 강화학습, 체크포인트 저장 |
| Isaac Sim Viewer | 훈련 중 휴머노이드 동작 확인 |

## 2. 준비 사항

기본 경로는 다음과 같이 가정한다.

```text
VLAGRAPH:        C:\Users\0\Desktop\vlagraph
IsaacLab:        C:\IsaacLab
IsaacLab Bridge: C:\vlagraph_isaaclab_bridge
```

다음 경로가 실제로 존재하는지 확인한다.

```powershell
Test-Path C:\Users\0\Desktop\vlagraph
Test-Path C:\IsaacLab
Test-Path C:\vlagraph_isaaclab_bridge
```

IsaacLab Bridge의 import 상태를 확인한다.

```powershell
cd C:\vlagraph_isaaclab_bridge

powershell -ExecutionPolicy Bypass `
  -File .\scripts\check_bridge.ps1
```

정상이면 다음 메시지가 표시된다.

```text
bridge import ok
```

> MediaPipe를 IsaacLab Python 환경에 설치하지 않는다. MediaPipe는 VLAGRAPH Docker backend 또는 `.venv-motion`에서만 사용한다. IsaacLab과 MediaPipe의 `numpy`, `protobuf` 요구 버전이 충돌할 수 있다.

## 3. 학습용 영상 준비

처음에는 다음 조건의 짧은 영상을 권장한다.

- 사람 한 명만 촬영
- 머리부터 발까지 전신이 보임
- 3~10초 길이
- 카메라가 고정되어 있음
- 조명이 충분함
- MP4 형식
- 한 영상에 한 종류의 동작만 포함

예를 들어 보행 학습 영상에는 걷기만 포함하고, 팔 들기나 앉기 동작은 별도 영상으로 준비한다.

## 4. VLAGRAPH에서 학습 데이터 생성

### 4.1 VLAGRAPH 실행

```powershell
cd C:\Users\0\Desktop\vlagraph

powershell -ExecutionPolicy Bypass `
  -File .\scripts\docker-compose-up.ps1
```

브라우저에서 다음 주소 중 실제로 열리는 주소에 접속한다.

```text
http://localhost:9173
http://127.0.0.1:9173
```

### 4.2 Motion Learning Graph 실행

1. `Graph Template`에서 `Motion Learning Graph`를 선택한다.
2. `Human Motion Video` 노드에서 `Upload Video`를 누른다.
3. 사람의 전신 동작 MP4 파일을 선택한다.
4. `Run Graph`를 누른다.
5. `Motion Extract Node`가 성공 상태인지 확인한다.

Motion Extract는 동작을 휴머노이드 관점에서 해석한다.

```text
보행 유사 동작
전신 이동
다리 협응
왼팔/오른팔 들기
전신 자세 변화
루트 위치 및 균형 제어
```

### 4.3 생성되는 파일

원본 모션 추적 데이터:

```text
C:\Users\0\Desktop\vlagraph\uploads\motion_traces\*.json
```

휴머노이드 관측–행동 학습 데이터:

```text
C:\Users\0\Desktop\vlagraph\uploads\humanoid_datasets\*.humanoid.jsonl
```

두 파일의 용도는 다르다.

| 파일 | 현재 용도 |
|---|---|
| `motion_traces\*.json` | IsaacLab Bridge가 읽는 시간 순서 모션 trace |
| `humanoid_datasets\*.jsonl` | 행동복제 또는 정책 사전학습용 관측–목표 동작 샘플 |

JSONL의 한 줄은 다음 관계를 나타낸다.

```text
현재 프레임 observation
  → 다음 프레임 action.target_landmarks
```

스키마 이름:

```text
vlagraph.humanoid_imitation.v1
```

## 5. 연결 확인용 IsaacLab 학습

처음에는 휴머노이드 Task를 사용하기 전에 Bridge와 데이터 로딩을 확인한다.

VLAGRAPH 화면에서 `Motion Extract Node`를 선택하고 `Copy IsaacLab Command`를 누른 뒤, 복사된 명령을 PowerShell에서 실행한다.

명령 예:

```powershell
powershell -ExecutionPolicy Bypass `
  -File "C:\vlagraph_isaaclab_bridge\scripts\train_isaaclab.ps1" `
  -Trace "C:\Users\0\Desktop\vlagraph\uploads\motion_traces\동작파일.json" `
  -Task Isaac-Cartpole-Direct-v0 `
  -NumEnvs 1 `
  -MaxIterations 200
```

가장 최근에 생성된 trace를 자동으로 선택하려면 다음 명령을 사용한다.

```powershell
cd C:\Users\0\Desktop\vlagraph

powershell -ExecutionPolicy Bypass `
  -File .\scripts\train-latest-motion-trace.ps1 `
  -Task Isaac-Cartpole-Direct-v0 `
  -NumEnvs 1 `
  -MaxIterations 200
```

`Isaac-Cartpole-Direct-v0`는 데이터 전달과 학습 프로세스 실행을 확인하기 위한 Task다. 이 Task로 실제 휴머노이드 보행을 학습할 수는 없다.

## 6. 실제 휴머노이드 Task 선택

설치된 IsaacLab Task 목록에서 G1 또는 사용할 휴머노이드 Task ID를 확인한다. IsaacLab 버전에 따라 Task 이름이 달라질 수 있으므로 임의로 이름을 만들지 말고 설치된 목록을 사용해야 한다.

IsaacLab App이 없는 가벼운 목록 명령을 지원하는 설치라면 다음과 같이 확인한다.

```powershell
cd C:\IsaacLab
.\isaaclab.bat -p scripts\environments\list_envs.py
```

출력에서 다음 키워드를 찾는다.

```text
G1
Humanoid
Locomotion
Velocity
Walk
```

Task 목록 스크립트의 위치가 다른 IsaacLab 버전에서는 설치된 `scripts` 폴더에서 `list_envs.py`를 검색한다.

```powershell
Get-ChildItem C:\IsaacLab\scripts -Recurse -Filter list_envs.py
```

선택한 Task가 휴머노이드 로봇과 원하는 action space를 사용하는지 확인한다.

## 7. 실제 휴머노이드 학습 실행

`<HUMANOID_TASK_ID>`를 설치된 실제 Task ID로 바꾼다.

```powershell
cd C:\vlagraph_isaaclab_bridge

powershell -ExecutionPolicy Bypass `
  -File .\scripts\train_isaaclab.ps1 `
  -Trace "C:\Users\0\Desktop\vlagraph\uploads\motion_traces\동작파일.json" `
  -Task "<HUMANOID_TASK_ID>" `
  -NumEnvs 1 `
  -MaxIterations 200
```

처음에는 viewer에서 동작과 오류를 확인하기 위해 `NumEnvs 1`을 사용한다. 학습 루프가 정상인 것을 확인한 다음 GPU 메모리에 맞춰 병렬 환경 수와 반복 횟수를 높인다.

예:

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\scripts\train_isaaclab.ps1 `
  -Trace "C:\Users\0\Desktop\vlagraph\uploads\motion_traces\동작파일.json" `
  -Task "<HUMANOID_TASK_ID>" `
  -NumEnvs 256 `
  -MaxIterations 2000
```

## 8. 휴머노이드 관절 매핑

실제 학습을 위해서는 VLAGRAPH 관절 목표와 IsaacLab Task의 action 순서가 일치해야 한다.

```text
MediaPipe landmark
  → G1 joint target
  → IsaacLab Task action vector
```

반드시 확인할 항목:

- IsaacLab Task의 action 차원
- 휴머노이드 관절 이름과 순서
- 각 관절의 최소·최대 각도
- action이 절대 관절 위치인지 상대 위치인지
- action scale
- 제어 주기와 모션 trace의 시간 간격

관절 순서가 다르면 로봇이 넘어지거나 전혀 다른 관절이 움직일 수 있다. action vector를 단순히 앞에서부터 채우는 방식은 연결 시험에만 사용하고, 실제 학습에는 관절 이름 기반 매핑을 사용한다.

## 9. 권장 보상 구성

모방학습 보상만 사용하면 자세를 따라 하면서도 넘어질 수 있다. 실제 휴머노이드 학습에서는 다음 보상을 함께 사용한다.

```text
전체 관절 자세 추종 보상
+ 루트 위치/방향 추종 보상
+ 목표 속도 추종 보상
+ 몸통 균형 보상
+ 발 접촉 보상
+ 발 미끄러짐 억제
+ 부드러운 action 보상
- 과도한 토크 패널티
- 에너지 사용 패널티
- 넘어짐 패널티
```

개념적인 보상식:

```text
total_reward =
    task_reward
    + imitation_weight × pose_tracking_reward
    + balance_weight × upright_reward
    + contact_weight × foot_contact_reward
    - energy_weight × energy_penalty
    - smoothness_weight × action_change_penalty
```

초기에는 모방 보상 비중을 너무 높이지 않고, 서 있기와 균형 보상이 안정적으로 작동하는지 먼저 확인한다.

## 10. 권장 학습 단계

### 단계 1: 연결 확인

```text
Task: Isaac-Cartpole-Direct-v0
NumEnvs: 1
MaxIterations: 200
목표: trace 로딩과 학습 스크립트 실행 확인
```

### 단계 2: 휴머노이드 정지 자세

```text
Task: 설치된 휴머노이드 Task
NumEnvs: 1
목표: 관절 매핑, 서 있기, 균형 확인
```

### 단계 3: 짧은 단일 동작

```text
입력: 3~5초 걷기 또는 팔 들기 영상
NumEnvs: 16~64
목표: 한 종류의 동작 모방
```

### 단계 4: 병렬 학습

```text
NumEnvs: 64~1024
MaxIterations: 1000 이상
목표: 안정적인 정책 학습과 체크포인트 생성
```

### 단계 5: 다양한 데이터

```text
여러 영상과 속도
좌우 방향
시작 자세 변화
물리 파라미터 랜덤화
목표: 실제 환경 변화에 대한 일반화
```

## 11. 학습 결과 확인

viewer를 사용하려면 학습 명령에 `--headless`를 추가하지 않는다.

학습 중 확인할 사항:

- 휴머노이드가 초기화 직후 넘어지는지
- 영상과 같은 신체 부위가 움직이는지
- 왼쪽과 오른쪽 관절이 뒤바뀌지 않았는지
- 발이 바닥을 과도하게 미끄러지는지
- reward가 장시간 상승하는지
- action 값이 관절 제한 범위를 벗어나지 않는지

체크포인트 저장 위치는 사용 중인 IsaacLab/RSL-RL Task 설정에 따라 달라진다. 학습 로그에 출력되는 `log_dir`와 checkpoint 경로를 확인한다.

학습된 policy 실행은 `train.py`가 아니라 해당 Task의 `play.py`를 사용한다.

```text
train.py: 정책 학습
play.py: 저장된 checkpoint 재생
```

## 12. 문제 해결

### trace 파일을 찾지 못하는 경우

```powershell
Get-ChildItem C:\Users\0\Desktop\vlagraph\uploads\motion_traces\*.json |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 5
```

VLAGRAPH에서 영상 업로드와 `Run Graph`를 다시 실행한다.

### 학습 샘플 수가 0인 경우

- 영상에서 전신이 보이는지 확인한다.
- 발이나 팔이 화면 밖으로 잘리지 않았는지 확인한다.
- 조명과 영상 선명도를 확인한다.
- `Motion Extract Node`의 visibility 설정을 확인한다.

### IsaacLab Bridge를 찾지 못하는 경우

```powershell
Test-Path C:\vlagraph_isaaclab_bridge\scripts\train_isaaclab.ps1
```

경로가 다르면 VLAGRAPH가 생성한 명령 또는 `train-latest-motion-trace.ps1`의 `BridgeRoot` 값을 실제 경로로 변경한다.

### 로봇이 즉시 넘어지는 경우

- 관절 순서가 IsaacLab Task와 일치하는지 확인한다.
- action scale을 낮춘다.
- 초기 자세와 trace 첫 프레임을 맞춘다.
- 균형 및 upright 보상을 높인다.
- 모방 보상 비중을 일시적으로 낮춘다.
- 발 접촉과 루트 높이 조건을 확인한다.

### 움직임이 영상과 반대인 경우

- 좌우 관절 매핑을 확인한다.
- MediaPipe 좌표계와 IsaacLab 좌표계를 확인한다.
- Y-up/Z-up 변환과 정면 방향 부호를 확인한다.
- 절대 관절각과 상대 관절 변화량을 혼동하지 않았는지 확인한다.

### MediaPipe 설치 후 IsaacLab이 실행되지 않는 경우

MediaPipe 관련 패키지를 IsaacLab 환경에서 제거하고 IsaacLab 의존성을 복구한다.

```powershell
cd C:\IsaacLab

.\isaaclab.bat -p -m pip uninstall -y mediapipe opencv-contrib-python
.\isaaclab.bat -p -m pip install "numpy>=2" "protobuf>=6.31.1,<7" "psutil==5.9.8"
.\isaaclab.bat -p -m pip check
```

## 13. 핵심 실행 명령

가장 최근 VLAGRAPH trace로 연결 확인:

```powershell
cd C:\Users\0\Desktop\vlagraph

powershell -ExecutionPolicy Bypass `
  -File .\scripts\train-latest-motion-trace.ps1 `
  -Task Isaac-Cartpole-Direct-v0 `
  -NumEnvs 1 `
  -MaxIterations 200
```

실제 휴머노이드 학습:

```powershell
cd C:\vlagraph_isaaclab_bridge

powershell -ExecutionPolicy Bypass `
  -File .\scripts\train_isaaclab.ps1 `
  -Trace "C:\Users\0\Desktop\vlagraph\uploads\motion_traces\동작파일.json" `
  -Task "<설치된 실제 휴머노이드 Task ID>" `
  -NumEnvs 256 `
  -MaxIterations 2000
```

## 14. 현재 구현 범위

현재 바로 가능한 기능:

- 업로드 영상에서 MediaPipe 전신 포즈 추출
- 휴머노이드 관점의 동작 의미 생성
- motion trace JSON 저장
- 휴머노이드 학습 JSONL 저장
- trace를 IsaacLab Bridge에 전달
- 모방 보상을 포함한 학습 연결
- 학습 telemetry를 VLAGRAPH로 전송

실제 G1 학습 전에 추가 확인이 필요한 기능:

- 설치된 G1/휴머노이드 Task ID
- Task의 실제 관절 순서와 action 차원
- 관절 이름 기반 action 매핑
- 균형, 발 접촉, 속도 및 에너지 보상 튜닝
- 학습된 checkpoint의 실제 로봇 적용 전 안전 검증

