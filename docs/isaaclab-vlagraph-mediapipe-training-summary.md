# Isaac Lab + VLA Graph + MediaPipe 학습 연결 요약

이 문서는 VLA Graph, MediaPipe, Isaac Lab을 연결해 로봇 움직임을 보면서 학습하는 흐름을 정리한다.

## 핵심 결론

가능한 연결은 다음과 같다.

```text
웹캠 / 업로드 비디오 / RealSense
  -> VLA Graph sensor or motion nodes
  -> MediaPipe pose / RGB-D pose fusion
  -> motion trace JSON or live pose
  -> Isaac Lab RSL-RL train.py
  -> imitation reward
  -> 학습 상태를 VLA Graph로 전송
```

현재 구현된 것은 **업로드 비디오 또는 저장된 MediaPipe motion trace를 Isaac Lab 학습 reward에 섞고, 학습 상태를 VLA Graph로 보내는 연결**이다.

아직 구현되지 않은 것은 **웹캠/RealSense 실시간 pose가 Isaac Lab action을 직접 지시하는 완전한 폐루프 학습**이다. 이 부분은 다음 단계에서 `--vlagraph_live_pose_url` 같은 옵션으로 확장하는 것이 좋다.

## play.py와 train.py의 역할

`play.py`는 이미 학습된 checkpoint를 재생하는 파일이다. 학습 중 로봇 움직임을 보려면 `play.py`가 아니라 Isaac Lab의 RSL-RL `train.py`를 사용해야 한다.

```text
play.py  : 학습된 policy 재생
train.py : policy 학습
```

따라서 MediaPipe 기반 학습 연결은 `C:\IsaacLab\scripts\reinforcement_learning\rsl_rl\train.py`에 붙였다.

## 추가된 코드

VLA Graph 저장소에 Isaac Lab 학습 wrapper를 추가했다.

```text
examples/isaaclab/vlagraph_motion_imitation.py
```

이 wrapper는 다음을 담당한다.

- VLA Graph MediaPipe motion trace JSON 읽기
- trace의 label과 heuristic label에서 `walk`, `left`, `right`, `arm` intent 추출
- Isaac Lab action shape에 맞는 간단한 target action 생성
- 기존 task reward에 imitation bonus 추가
- 선택적으로 VLA Graph backend websocket에 학습 telemetry 전송

reward 형태:

```text
reward = task_reward + imitation_weight * exp(-action_error)
```

Isaac Lab의 기존 RSL-RL 학습 스크립트에는 옵션을 추가했다.

```text
C:\IsaacLab\scripts\reinforcement_learning\rsl_rl\train.py
```

추가된 주요 옵션:

```text
--vlagraph_motion_trace
--vlagraph_repo
--vlagraph_imitation_weight
--vlagraph_action_scale
--vlagraph_publish_interval
--vlagraph_client_id
--vlagraph_backend_ws
```

## 현재 가능한 센서 입력

VLA Graph 기준으로 연결 가능한 입력은 다음과 같다.

```text
1. 업로드 비디오
   -> Motion Extract
   -> MediaPipe trace JSON
   -> Isaac Lab imitation reward

2. 일반 웹캠
   -> Sensor Camera
   -> MediaPipe Pose
   -> Motion Retarget

3. RealSense D435i RGB
   -> RealSense bridge
   -> Remote Image Sensor
   -> MediaPipe Pose

4. RealSense Depth / RGB-D
   -> RealSense D435i Sensor
   -> RGB-D Pose Fusion
   -> 더 안정적인 3D pose

5. Isaac Lab 학습 상태
   -> websocket state
   -> VLA Graph frontend에서 확인
```

현재 바로 안정적으로 쓸 수 있는 학습 경로는 **업로드 비디오 또는 저장된 trace 기반 학습**이다.

## 실행 순서

### 1. MediaPipe trace 만들기

```powershell
cd C:\Users\0\Desktop\vlagraph

python -m venv .venv-motion
.\.venv-motion\Scripts\python.exe -m pip install -r scripts\requirements-motion.txt

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

주의: 이 의존성은 MediaPipe 영상 추출용이다. Isaac Lab Python 환경에서 설치하면 `numpy`, `protobuf`, `psutil` 버전이 Isaac Lab/RSL-RL 요구사항과 충돌할 수 있으므로 별도 `.venv-motion` 또는 Docker backend에서만 설치한다.

JSON에는 다음 정보가 들어간다.

```text
frames[].landmarks
frames[].features.angles_deg
frames[].features.hip_center
summary.heuristic_labels
```

### 2. VLA Graph 백엔드 실행

학습 상태를 VLA Graph에서 보고 싶으면 백엔드를 먼저 실행한다.

```powershell
cd C:\Users\0\Desktop\vlagraph
powershell -ExecutionPolicy Bypass -File scripts\docker-compose-up.ps1
```

state websocket:

```text
ws://127.0.0.1:8000/ws/unity/state?client_id=isaaclab-motion-train
```

Docker 네트워크 상황에 따라 `127.0.0.1` 대신 `host.docker.internal`이 필요할 수 있다.

### 3. Isaac Lab에서 viewer를 켜고 학습

`--headless`를 붙이지 않으면 Isaac Lab viewer에서 움직임을 보면서 학습할 수 있다.

```powershell
cd C:\IsaacLab

.\isaaclab.bat -p scripts\reinforcement_learning\rsl_rl\train.py `
  --task Isaac-Cartpole-Direct-v0 `
  --num_envs 64 `
  --max_iterations 200 `
  --vlagraph_motion_trace C:\Users\0\Desktop\vlagraph\uploads\motion_traces\walk_001.json `
  --vlagraph_repo C:\Users\0\Desktop\vlagraph `
  --vlagraph_imitation_weight 0.05 `
  --vlagraph_publish_interval 100 `
  --vlagraph_backend_ws "ws://127.0.0.1:8000/ws/unity/state?client_id=isaaclab-motion-train"
```

`Isaac-Cartpole-Direct-v0`는 연결 검증용 예시다. 실제 G1/휴머노이드 학습에는 해당 task의 action space에 맞춘 target action 매핑을 추가해야 한다.

## VLA Graph에서 확인되는 telemetry

학습 중 wrapper가 일정 step마다 다음 payload를 보낸다.

```text
client_id: isaaclab-motion-train
source: isaaclab_motion_imitation
motion_label
motion_command
imitation_reward
reward_preview
action_preview
motion_frame
```

VLA Graph frontend에서는 `Robot State (Unity)` 계열 state client로 `isaaclab-motion-train`을 확인하면 된다.

## 한계와 다음 개발 단계

현재 구현은 범용적인 첫 연결이다. MediaPipe label에서 간단한 intent를 뽑아 action vector 앞쪽에 target을 넣는다. 따라서 모든 Isaac Lab task에서 로봇다운 움직임을 보장하지 않는다.

권장 다음 단계:

```text
1. 업로드 비디오 기반 trace 학습 성공 확인
2. G1/휴머노이드 task의 action space 확인
3. motion_retarget의 G1 joint_targets 또는 joint_trajectory를 Isaac Lab action target으로 변환
4. velocity, balance, energy, smoothness reward와 결합
5. 웹캠/RealSense live pose endpoint를 train wrapper가 읽도록 확장
```

실시간 센서 학습 확장안:

```text
--vlagraph_live_pose_url http://127.0.0.1:8000/api/...
```

이 옵션을 추가하면 파일 trace가 아니라 VLA Graph의 최신 MediaPipe/RGB-D pose를 주기적으로 읽어 학습 target으로 사용할 수 있다.

## 검증 기록

다음 검증을 완료했다.

```text
python -m py_compile examples/isaaclab/vlagraph_motion_imitation.py
python -m py_compile C:\IsaacLab\scripts\reinforcement_learning\rsl_rl\train.py
```

샘플 trace로 `MotionTraceTarget`이 label과 command를 생성하는 것도 확인했다.

주의: `C:\Users\0\Desktop\vlagraph\.git` 폴더는 존재하지만, 작업 당시 git이 유효한 저장소로 인식하지 못했다. 그래서 git status 기반 검증은 하지 못했다.
