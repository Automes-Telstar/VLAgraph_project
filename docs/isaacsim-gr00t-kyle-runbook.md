# Isaac Sim KyleRobot + GR00T 실행 가이드

이 문서는 VLA Graph FastAPI 백엔드, NVIDIA GR00T 그래프, Isaac Sim의 `/World/KyleRobot` 브리지를 처음부터 실행하는 순서입니다.

## 1. VLA Graph 서버 실행

PowerShell에서 프로젝트 폴더로 이동합니다.

```powershell
cd C:\Users\0\Desktop\vlagraph
docker compose up -d --build
```

컨테이너 상태를 확인합니다.

```powershell
docker compose ps
```

브라우저에서 프론트를 엽니다.

```text
http://localhost:9173
```

주요 주소:

```text
Frontend: http://localhost:9173
Backend:  http://localhost:9000
GR00T stub: http://localhost:9071
```

## 2. Isaac Sim Stage 준비

Isaac Sim에서 KyleRobot이 포함된 Stage를 엽니다.

Prim 경로가 아래와 같은지 확인합니다.

```text
/World/KyleRobot
```

브리지가 자동으로 생성하거나 사용하는 카메라 경로는 아래입니다.

```text
/World/KyleRobot/VlaGraphCamera
```

## 3. Isaac Sim 브리지 실행

Isaac Sim에서 `Window > Script Editor`를 열고 아래 한 줄만 실행합니다.

```python
exec(open(r"C:\Users\0\Desktop\vlagraph\examples\isaacsim\run_kyle_camera_bridge.py").read())
```

정상 실행 시 Isaac Sim 콘솔에 비슷한 로그가 표시됩니다.

```text
[VlaGraphIsaacSimBridge] started command_ws=ws://0.0.0.0:9900/omniverse ...
[VlaGraphIsaacSimBridge] created camera=/World/KyleRobot/VlaGraphCamera ...
```

9900 포트가 이미 사용 중이면 Isaac Sim을 재시작하거나, 기존 브리지를 중지한 뒤 다시 실행합니다.

```python
shutdown()
exec(open(r"C:\Users\0\Desktop\vlagraph\examples\isaacsim\run_kyle_camera_bridge.py").read())
```

## 4. VLA Graph에서 GR00T 그래프 선택

브라우저의 VLA Graph 화면에서 상단 `Graph Template` 메뉴를 `GR00T Graph`로 선택합니다.

`Robot Execute Node` 설정을 확인합니다.

```text
mode = omniverse
omniverseEndpoint = ws://host.docker.internal:9900/omniverse
omniverseStage = /World
omniversePrimPath = /World/KyleRobot
omniverseCommand = execute_policy
```

`Remote Image Sensor` 설정:

```text
remoteImageUrl = http://localhost:9000/api/unity/image?client_id=isaacsim01
```

`Robot State (Isaac Sim)` 설정:

```text
clientId = isaacsim01
```

## 5. 그래프 실행

VLA Graph에서 `Run Graph`를 누릅니다.

성공하면 실행 로그에서 `robot_execute` 결과가 `ok: True`로 나와야 합니다.

```text
node-7 (robot_execute) -> {'result': {'ok': True, 'mode': 'omniverse', ...}}
```

Isaac Sim 콘솔에는 프롬프트 수신 로그가 표시됩니다.

```text
[VlaGraphIsaacSimBridge] prompt received request_id=... command=execute_policy text=walk forward toward the checkpoint...
```

## 6. 프롬프트별 KyleRobot 행동 매핑

기본 `gr00t_stub`는 실제 모델이 아니라 테스트용 행동 생성기입니다. 그래도 프롬프트별로 다음 동작을 구분하도록 설정되어 있습니다.

```text
walk forward / 전진 / 앞으로       -> 앞으로 이동
turn left / 왼쪽 / 좌측            -> 좌회전 또는 좌측 이동
turn right / 오른쪽 / 우측         -> 우회전 또는 우측 이동
back / backward / 뒤 / 후진        -> 뒤로 이동
stop / halt / 정지 / 멈춰          -> 정지
slowly / 천천히 / 조심             -> 속도 감소
fast / quickly / 빨리 / 빠르게     -> 속도 증가
checkpoint / waypoint / target     -> 목표 이동 의도
```

좌표가 프롬프트에 있으면 waypoint/patrol 액션에서 목표 위치로 사용합니다.

```text
walk to checkpoint at [1.0, 0.0, 2.5]
move to x=1.0 y=0.0 z=2.5
```

실제 NVIDIA GR00T 서버로 바꾸면 이 규칙 기반 stub 대신 모델 출력이 사용됩니다. 실제 서버 연결 절차는 [실제 NVIDIA Isaac GR00T 서버 연결](gr00t-real-policy-adapter.md)을 참고하세요.

## 7. 카메라 화면 수신 확인

PowerShell에서 최신 Isaac Sim 카메라 프레임 저장 여부를 확인합니다.

```powershell
$img = Invoke-RestMethod "http://localhost:9000/api/unity/image?client_id=isaacsim01"
$img.ok
$img.width
$img.height
```

`$img.ok`가 `True`이면 백엔드가 Isaac Sim 카메라 화면을 받고 있습니다.

## 8. 프롬프트 수신 확인

PowerShell에서 Isaac Sim 브리지가 마지막으로 받은 프롬프트를 확인합니다.

```powershell
$r = Invoke-RestMethod "http://localhost:9000/api/unity/state?client_id=isaacsim01"
$r.state.last_prompt
$r.state.last_instruction
```

정상이라면 현재 Prompt Node의 문장이 출력됩니다.

```text
walk forward toward the checkpoint and turn slightly left
```

전체 상태를 확인하려면:

```powershell
Invoke-RestMethod "http://localhost:9000/api/unity/state?client_id=isaacsim01" | ConvertTo-Json -Depth 10
```

## 9. 애니메이션 재생 확인

KyleRobot의 Stage 구조에 `Skeleton`과 `Take_001`이 있어도 자동으로 애니메이션이 재생되지 않을 수 있습니다.

주요 원인:

- `Take_001` `SkelAnimation`이 `Skeleton` 또는 `SkelRoot`에 바인딩되지 않음
- Isaac Sim 타임라인이 정지 상태임
- VLA Graph 명령은 `/World/KyleRobot` Transform 이동만 적용하고, 골격 애니메이션 재생은 별도 설정이 필요함

현재 브리지 실행 스크립트는 아래 경로를 자동 바인딩하고 타임라인을 재생합니다.

```python
os.environ["VLAGRAPH_ENABLE_ANIMATION"] = "true"
os.environ["VLAGRAPH_PLAY_TIMELINE"] = "true"
os.environ["VLAGRAPH_ANIMATION_LOOP"] = "true"
os.environ["VLAGRAPH_SKELETON_PRIM"] = "/World/KyleRobot/ROOT/Hips/Skeleton"
os.environ["VLAGRAPH_ANIMATION_PRIM"] = "/World/KyleRobot/Take_001"
```

Isaac Sim 콘솔에 아래 로그가 나오면 애니메이션 연결이 준비된 것입니다.

```text
[VlaGraphIsaacSimBridge] skeletal animation ready skeleton=/World/KyleRobot/ROOT/Hips/Skeleton animation=/World/KyleRobot/Take_001 ...
```

FastAPI 상태 API로도 확인할 수 있습니다.

```powershell
$r = Invoke-RestMethod "http://localhost:9000/api/unity/state?client_id=isaacsim01"
$r.state.animation_ready
$r.state.skeleton_prim_path
$r.state.animation_prim_path
```

`animation_ready`가 `False`이면 Isaac Sim Stage의 실제 Skeleton/Animation 경로가 문서와 다를 수 있습니다. Stage 트리에서 실제 경로를 복사한 뒤 `examples/isaacsim/run_kyle_camera_bridge.py`의 `VLAGRAPH_SKELETON_PRIM`, `VLAGRAPH_ANIMATION_PRIM` 값을 수정하세요.

## 10. 자주 생기는 문제

### `robot_execute`가 `ok: False`

`Robot Execute Node`의 Prim 값이 KyleRobot과 맞는지 확인합니다.

```text
omniverseStage = /World
omniversePrimPath = /World/KyleRobot
```

기존 세션이 예전 값으로 메모리에 올라가 있을 수 있으니 VLA Graph에서 `Cancel Run` 후 다시 `Run Graph`를 실행합니다.

### 프론트 메뉴나 기본값이 예전 값으로 보임

프론트 컨테이너를 다시 빌드합니다.

```powershell
docker compose up -d --build frontend
```

브라우저에서 `Ctrl+F5`로 강력 새로고침합니다.

### 프롬프트가 `last_prompt`에 안 보임

백엔드가 예전 코드로 실행 중일 수 있습니다.

```powershell
docker compose up -d --build backend
```

그 다음 Isaac Sim 브리지를 다시 실행하고, VLA Graph에서 `Cancel Run` 후 새로 실행합니다.

### 카메라 경고 또는 화면 미수신

Isaac Sim Script Editor에서 브리지를 다시 실행합니다.

```python
exec(open(r"C:\Users\0\Desktop\vlagraph\examples\isaacsim\run_kyle_camera_bridge.py").read())
```

카메라 Transform은 `examples/isaacsim/run_kyle_camera_bridge.py`의 아래 값으로 조정합니다.

```python
os.environ["VLAGRAPH_CAMERA_LOCAL_POSITION"] = "0,2.55796,-4.08236"
os.environ["VLAGRAPH_CAMERA_LOCAL_ROTATION_DEG"] = "-194.14137,1.0457,-179.11757"
os.environ["VLAGRAPH_CAMERA_LOCAL_SCALE"] = "1,1,1"
```
