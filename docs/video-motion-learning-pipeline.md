# 영상 기반 모션 인식/학습 파이프라인

이 문서는 사람 동작 영상에서 모션을 인식하고, 그 결과를 VLA Graph / Isaac Sim / GR00T 학습 흐름으로 연결하는 방법을 정리합니다.

핵심은 강화학습 하나로 바로 시작하는 것이 아니라, 먼저 영상에서 사람 포즈와 시간 변화를 뽑아 **모방학습 데이터**를 만들고, 그 뒤 Isaac Lab이나 GR00T fine-tune으로 확장하는 것입니다.

참고 공식 문서:

- MediaPipe Pose Landmarker: https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker
- NVIDIA Isaac Lab: https://developer.nvidia.com/isaac/lab
- NVIDIA Isaac-GR00T: https://github.com/NVIDIA/Isaac-GR00T

## 1. 전체 구조

```text
Human motion video
  -> pose extraction
  -> motion trace JSON
  -> motion label / skill dataset
  -> retargeting to robot skeleton
  -> imitation learning or GR00T fine-tune
  -> Isaac Sim policy execution
  -> optional RL fine-tuning in Isaac Lab
```

## 2. 영상에서 모션 trace 추출

먼저 영상에서 사람의 2D/3D 포즈 landmark, 관절 각도, 시간별 변화량을 뽑습니다.

## 2-1. VLA Graph에서 실행

프론트 상단 **Graph Template** 메뉴에서 `Motion Learning Graph`를 선택하면 아래 흐름이 생성됩니다.

```text
Motion Prompt
  -> Motion Extract
  -> Motion Retarget
  -> Robot Execute
  -> Print Omniverse Result

Human Motion Video
  -> Motion Extract
  -> Motion Retarget
```

사용 순서:

1. `Motion Learning Graph` 선택
2. `Human Motion Video` 노드에서 `Upload Video`
3. 필요하면 `motionLabel`을 `walk_forward`, `turn_left`, `raise_arm`처럼 수정
4. `Run Graph`
5. `Motion Extract` 결과의 `trace_path`에 JSON이 저장됨
6. `Motion Retarget`이 `apply_humanoid_motion` 액션으로 변환
7. `Robot Execute`가 Isaac Sim의 `/World/GR00T_Humanoid`에 명령 전송

`Motion Extract` 노드는 다음 값을 출력합니다.

```text
motion   : compact motion trace JSON
skill    : 추정/지정된 skill label
dataset  : 저장된 trace JSON 경로
pose_preview: 미리보기용 MediaPipe landmark 점/선 데이터
```

`Motion Retarget` 노드는 추출된 모션을 Isaac Sim의 G1/GR00T Humanoid용 중간 명령으로 바꿉니다.

```text
action.command : apply_humanoid_motion
action.skill   : walk_forward / turn_left / raise_arm 등
action.move_z  : 전후 이동량
action.turn_yaw: 좌우 회전량
action.pose_sequence: Hips / Spine1 / LeftLeg / RightLeg / Arm 회전 시퀀스
```

기본값으로 `fullBodyRetarget=true`와 `targetEmbodiment=REAL_G1`이 켜져 있습니다. Motion Learning Graph에서는 영상 전체 싱크를 우선하기 위해 `emitG1JointTargets=false`, `durationSec=0`, `maxPoseFrames=120`을 기본값으로 둡니다. 이렇게 하면 `Motion Retarget`이 저장된 trace JSON을 다시 읽고, MediaPipe landmark/angle을 `pose_sequence` 전체로 변환한 뒤 Isaac Sim timeline이 원본 영상 timestamp에 맞춰 재생합니다. `Robot Execute`는 기본 `dryRun=false`라 Omniverse로 바로 명령을 보냅니다.

조절값:

```text
durationSec   : 0이면 원본 영상 timestamp/span 사용, 양수이면 해당 초 단위로 리타이밍
maxPoseFrames : Isaac Sim으로 보낼 포즈 샘플 수
poseScale     : 팔/다리/몸통 회전 배율
stepScale     : root 이동 크기
turnScale     : root 회전 크기
```

기본값은 프론트 표시가 무거워지지 않도록 전체 frame 목록을 결과에 직접 넣지 않습니다. 전체 landmark frame을 결과에도 포함하려면 `includeFrames=true`로 바꿉니다. 저장된 JSON 파일에는 항상 전체 frame이 포함됩니다.

`Human Motion Video` 미리보기는 그래프 실행 후 `pose_preview`를 받아 영상 위에 MediaPipe 관절 점과 주요 연결선을 그립니다. 영상 재생 위치에 맞춰 가장 가까운 landmark frame이 표시됩니다.

주의: 이 노드는 FastAPI backend 컨테이너에서 MediaPipe/OpenCV를 실행합니다. backend 이미지를 다시 빌드해야 새 의존성이 들어갑니다.

```powershell
docker compose build backend
docker compose up -d --no-deps backend
```

영상 업로드 크기가 크면 `.env`의 `MAX_UPLOAD_MB` 값을 늘린 뒤 backend를 재시작하세요.

```env
MAX_UPLOAD_MB=200
```

## 2-2. 로컬 스크립트로 실행

의존성 설치:

```powershell
cd C:\Users\0\Desktop\vlagraph
python -m venv .venv-motion
.\.venv-motion\Scripts\python.exe -m pip install -r scripts\requirements-motion.txt
```

예시 실행:

```powershell
.\.venv-motion\Scripts\python.exe scripts\extract_video_motion.py `
  --video C:\Users\0\Desktop\motions\walk_left.mp4 `
  --output uploads\motion_traces\walk_left.json `
  --label walk_forward_turn_left `
  --prompt "walk forward and turn slightly left"
```

`cmd.exe`에서는 한 줄로 실행합니다.

```bat
python scripts\extract_video_motion.py --video C:\Users\0\Desktop\motions\walk_left.mp4 --output uploads\motion_traces\walk_left.json --label walk_forward_turn_left --prompt "walk forward and turn slightly left"
```

주의: 이 의존성은 MediaPipe 영상 추출용이다. Isaac Lab Python 환경에서 설치하면 `numpy`, `protobuf`, `psutil` 버전이 Isaac Lab/RSL-RL 요구사항과 충돌할 수 있으므로 별도 `.venv-motion` 또는 Docker backend에서만 설치한다.

출력 JSON에는 아래 정보가 들어갑니다.

```text
frames[].landmarks
frames[].features.hip_center
frames[].features.angles_deg
frames[].features.arm_state
summary.heuristic_labels
```

이 단계의 목적은 완벽한 로봇 제어가 아니라, 영상이 어떤 동작인지 기계가 읽을 수 있는 시계열 데이터로 바꾸는 것입니다.

## 3. 모션 인식 모델

초기에는 큰 모델보다 작은 분류기부터 시작하는 것이 좋습니다.

입력:

```text
landmark sequence
joint angle sequence
hip/shoulder movement
arm/leg state
```

출력:

```text
walk_forward
turn_left
turn_right
stop
raise_left_arm
pick_motion
```

권장 순서:

1. 규칙 기반 label 확인
2. 랜드마크 시계열을 저장
3. 동작별 영상 20~50개 수집
4. 간단한 temporal classifier 학습
5. VLA Graph에 `motion_recognition` 노드로 연결

## 4. 로봇 동작으로 바꾸기

영상 landmark를 바로 KyleRobot joint에 넣으면 잘 맞지 않습니다. 사람과 로봇의 관절 구조가 다르기 때문입니다.

중간 표현을 둡니다.

```text
video pose
  -> skill label
  -> normalized motion command
  -> robot action
```

예:

```json
{
  "skill": "walk_forward_turn_left",
  "target_vx": 0.45,
  "target_yaw_rate": -0.2,
  "duration_sec": 2.0
}
```

VLA Graph의 GR00T stub / 실제 GR00T / RL policy는 이 명령을 받아 로봇 제어 action을 만들 수 있습니다.

현재 프로젝트에서는 `Motion Retarget` 노드가 이 중간 표현을 만들고, `Robot Execute` 노드가 Omniverse WebSocket으로 Isaac Sim bridge에 전달합니다. Isaac Sim 쪽 bridge는 `apply_humanoid_motion`을 받으면 KyleRobot의 root 이동/회전을 적용합니다. `pose_sequence`가 있으면 `/World/KyleRobot/VlaGraphPoseAnimation`이라는 새 `UsdSkel.Animation`을 만들고 KyleRobot Skeleton에 바인딩한 뒤 타임라인을 재생합니다. 이 경로가 실패하면 Skeleton 아래의 `OmniJoint` prim에 직접 time-sample 회전을 기록하는 fallback을 사용합니다. `pose_sequence`가 없으면 가능한 경우 기존 `SkelAnimation` 타임라인을 다시 재생합니다.

주의: 이 단계는 “실제 리깅 아티스트 수준의 retargeting”이 아니라, MediaPipe 2D/3D landmark를 KyleRobot의 대표 관절에 맞춘 1차 자동 매핑입니다. 축이 반대로 보이면 `poseScale`을 줄이거나 bridge의 joint 축 매핑을 조정해야 합니다.

Isaac Sim Script Editor에서 bridge를 다시 로드해야 최신 명령 처리가 반영됩니다.

```python
exec(open(r"C:\Users\0\Desktop\vlagraph\examples\isaacsim\run_kyle_camera_bridge.py").read())
```

## 5. 학습 방식 선택

### A. 모션 인식만 학습

가장 빠른 단계입니다.

```text
video -> skill label
```

이 방식은 “이 영상은 걷기다”, “이 영상은 왼쪽 회전이다”를 인식합니다. 로봇 제어는 기존 `gr00t_stub`나 Isaac Sim bridge가 담당합니다.

### B. 모방학습

사람 영상에서 추출한 동작을 로봇 명령으로 변환해 학습합니다.

```text
video pose + prompt -> robot command
```

이 방식은 GR00T fine-tune이나 별도 behavior cloning 정책에 연결하기 좋습니다.

### C. RL 보정

모방학습만으로는 발 접촉, 균형, 충돌 대응이 부족할 수 있습니다. 이 부분은 Isaac Lab에서 강화학습으로 보정합니다.

```text
imitation policy
  -> Isaac Lab simulation
  -> reward: forward speed, balance, energy, smoothness
  -> robust locomotion policy
```

## 6. 현재 프로젝트에 붙이는 추천 순서

1. `Motion Learning Graph`에서 영상 업로드
2. `Motion Extract`로 trace 생성
3. `Motion Retarget`으로 KyleRobot용 `apply_humanoid_motion`과 `pose_sequence` 생성
4. `Robot Execute`로 Isaac Sim `/World/KyleRobot`에 적용
5. 동작 label별 JSON을 `uploads/motion_traces`에 모으기
6. 실제 GR00T/Isaac Lab policy로 교체

## 6-1. Isaac Lab에서 보면서 학습하기

`play.py`는 checkpoint 재생용이므로 학습에는 `train.py`를 사용한다. 이 저장소에는 VLA Graph motion trace를 Isaac Lab RSL-RL 학습 보상에 섞는 wrapper가 추가되어 있다.

추가된 파일:

```text
examples/isaaclab/vlagraph_motion_imitation.py
```

패치된 Isaac Lab 파일:

```text
C:\IsaacLab\scripts\reinforcement_learning\rsl_rl\train.py
```

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

### 2. VLA Graph 백엔드 실행

학습 상태를 VLA Graph에서 보고 싶으면 백엔드를 먼저 실행한다.

```powershell
cd C:\Users\0\Desktop\vlagraph
powershell -ExecutionPolicy Bypass -File scripts\docker-compose-up.ps1
```

백엔드를 Docker가 아니라 로컬에서 실행한다면 websocket 주소는 보통 아래와 같다.

```text
ws://127.0.0.1:8000/ws/unity/state?client_id=isaaclab-motion-train
```

Docker Desktop 경유가 필요하면 `host.docker.internal`을 사용한다.

### 3. Viewer를 켠 상태로 RSL-RL 학습

`--headless`를 주지 않으면 Isaac Lab viewer에서 로봇 움직임을 보면서 학습할 수 있다.

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

초기 구현은 안전한 범용 wrapper다. MediaPipe label에서 `walk`, `left`, `right`, `arm` 같은 intent를 뽑고, Isaac Lab action 벡터의 앞쪽 차원에 작은 imitation target을 만든 뒤 기존 reward에 bonus를 더한다.

```text
reward = task_reward + imitation_weight * exp(-action_error)
```

따라서 모든 로봇 task에 완벽한 retargeting을 보장하지는 않는다. 실제 G1 보행 task에서는 action 차원과 의미가 다르므로 다음 단계에서 task별 매핑을 추가해야 한다.

추천 확장:

```text
MediaPipe trace
  -> motion_retarget의 G1 joint_targets / joint_trajectory
  -> Isaac Lab task action space에 맞춘 target_action
  -> velocity, balance, smoothness reward와 함께 학습
```

### 4. VLA Graph에서 상태 확인

telemetry websocket을 켜면 wrapper가 일정 step마다 `robot_state` payload를 보낸다.

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

프론트에서는 `Robot State (Unity)` 또는 state client 목록에서 `isaaclab-motion-train`을 확인하면 된다.

## 7. 주의점

- 단일 RGB 영상은 깊이/발 접촉/힘 정보를 정확히 알기 어렵습니다.
- 보행 학습에는 단순 `SkelAnimation`보다 물리 기반 Articulation 로봇이 필요합니다.
- 사람 모션을 그대로 로봇 joint에 복사하면 넘어지기 쉽습니다.
- 처음에는 `walk`, `turn`, `stop`, `raise_arm` 같은 큰 skill부터 학습하는 편이 안정적입니다.
- 실제 GR00T fine-tune은 영상만이 아니라 robot state/action 데이터가 함께 있을 때 가장 좋습니다.
