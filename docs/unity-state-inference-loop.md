# Unity 상태 기반 추론 루프 문서

이 문서는 Unity에서 보낸 로봇 상태를 백엔드 그래프 런타임이 읽고, OpenVLA 추론 결과를 다시 Unity 로봇 명령으로 보내는 전체 루틴을 정리합니다.

## 전체 흐름

```text
Unity
  -> /ws/unity/state
  -> backend/server.py
  -> backend/state_store.py
  -> Robot State (Unity) 노드
  -> OpenVLA Infer 노드
  -> Action Decode 노드
  -> Safety Clamp 노드
  -> Robot Execute 노드
  -> ws://host.docker.internal:9081/robot
  -> Unity
```

핵심은 `Robot State (Unity)` 노드가 Unity WebSocket 메시지를 직접 받는 것이 아니라는 점입니다. Unity 상태 메시지는 먼저 백엔드 WebSocket 엔드포인트가 받고, `state_store`에 저장됩니다. 그래프 런타임은 실행 시점에 `state_store`에서 최신 상태를 읽습니다.

## 1. Unity가 상태를 백엔드로 보냄

Unity 브리지는 로봇 상태를 JSON으로 만들어 백엔드 WebSocket에 전송합니다.

주요 코드 위치:

- `examples/unity/UnityHumanoidRobotBridge.cs`
  - `BuildStateWebSocketUrl`: 백엔드 상태 WebSocket URL 생성
  - `EnsureStateWebSocket`: 상태 전송용 WebSocket 연결 준비
  - `SendStateOnce`: 현재 Unity 로봇 상태를 한 번 전송
  - `BuildRobotState`: Unity의 트랜스폼, 관절, 그리퍼 등 상태를 JSON으로 구성

상태 전송 대상:

```text
ws://<backend-host>/ws/unity/state?client_id=<stateClientId>
```

Unity 쪽에서 중요한 설정:

- `backendBaseUrl`: 백엔드 주소
- `stateClientId`: Unity 상태 클라이언트 ID
- `sendStateContinuously`: 상태를 주기적으로 보낼지 여부
- `stateSendInterval`: 상태 전송 간격
- `sendStateAfterCommand`: 명령 적용 후 상태를 다시 보낼지 여부

예시 상태 메시지:

```json
{
  "client_id": "RobotKyle",
  "timestamp": 1710000000.0,
  "robot_state": {
    "pose": {
      "position": [0.1, 0.8, 0.2],
      "rotation": [0.0, 90.0, 0.0]
    },
    "joints": {
      "left_arm": [0.0, 0.2, -0.1],
      "right_arm": [0.0, -0.2, 0.1]
    },
    "gripper": {
      "left": 0.0,
      "right": 1.0
    }
  }
}
```

## 2. 백엔드가 Unity 상태를 수신하고 저장함

백엔드는 Unity가 보낸 상태 WebSocket 메시지를 받고, 최신 상태 저장소에 기록합니다.

주요 코드 위치:

- `backend/server.py`
  - `unity_state_ws`: `/ws/unity/state` WebSocket 수신 엔드포인트
- `backend/state_store.py`
  - `update_state`: Unity 상태 저장
  - `get_latest_state`: 특정 `client_id`의 최신 상태 조회
  - `list_clients`: 현재 연결 또는 기록된 Unity 클라이언트 목록 조회

저장 구조는 대략 다음 역할을 합니다.

- `client_id`별 최신 Unity 상태 저장
- 상태 수신 시각 저장
- 그래프 실행 시 `Robot State (Unity)` 노드가 읽을 수 있게 제공
- `client_id`가 `default`, `auto`, 빈 문자열이고 Unity 클라이언트가 하나뿐이면 해당 클라이언트를 자동 선택

상태 확인용 API:

```text
GET /api/unity/state/clients
GET /api/unity/state?client_id=<clientId>
```

## 3. 그래프 런타임이 노드를 실행함

프론트엔드에서 그래프를 실행하면 백엔드 런타임이 노드 연결 순서에 따라 실행합니다.

주요 코드 위치:

- `backend/runtime/runner.py`
  - `run_graph`: 그래프 노드들을 위상 순서로 실행
- `backend/runtime/session_manager.py`
  - `_run_session`: 세션 실행 루프
  - Unity 상태와 Unity 실행 노드가 있으면 피드백 기반 반복 실행을 관리
- `backend/executors/registry.py`
  - 노드 타입 문자열을 실제 실행 함수에 연결

중요한 노드 등록:

```python
"unity_state": exec_unity_state
"openvla_infer": exec_openvla_infer
"action_decode": exec_action_decode
"safety_clamp": exec_safety_clamp
"robot_execute": exec_robot_execute
```

## 4. Robot State (Unity) 노드가 최신 상태를 읽음

`Robot State (Unity)` 노드는 Unity에서 직접 메시지를 받지 않습니다. 이미 `state_store`에 저장된 최신 상태를 읽습니다.

주요 코드 위치:

- `backend/executors/common_nodes.py`
  - `exec_unity_state`: `state_store.get_latest_state`를 호출해 Unity 상태를 반환

노드 출력은 대략 다음 값을 포함합니다.

- `state`: OpenVLA 추론에 넘길 Unity 로봇 상태
- `client_id`: 실제로 사용된 Unity 클라이언트 ID
- `requested_client_id`: 그래프에서 요청한 클라이언트 ID
- `age_seconds`: 상태가 얼마나 오래되었는지

프론트엔드 노드 정의 위치:

- `frontend/src/nodeDefs.ts`
  - `Robot State (Unity)` 노드 UI와 입력값 정의

중요 설정:

- `clientId`: Unity의 `stateClientId`와 맞추는 것이 가장 안전합니다.
- Unity 클라이언트가 하나뿐이면 `default`나 `auto`도 자동 선택될 수 있습니다.

## 5. OpenVLA Infer 노드가 상태와 이미지를 이용해 액션을 추론함

`OpenVLA Infer` 노드는 프롬프트, 이미지, Unity 로봇 상태를 VLA 서비스로 보냅니다.

주요 코드 위치:

- `backend/executors/vla_nodes.py`
  - `exec_openvla_infer`: VLA 추론 요청 생성 및 전송

추론 요청에 들어가는 핵심 값:

- `prompt`: 사용자가 원하는 작업 설명
- `image`: 카메라 또는 이미지 입력
- `state`: `Robot State (Unity)`에서 읽은 Unity 로봇 상태
- `model_name`: 사용할 VLA 모델 이름

그래프 연결에서 특히 중요한 부분:

```text
Robot State (Unity).state -> OpenVLA Infer.state
```

이 연결이 없으면 Unity 상태를 받더라도 OpenVLA 추론 요청에 상태가 들어가지 않습니다.

## 6. Action Decode와 Safety Clamp가 액션을 정리함

OpenVLA 결과는 바로 Unity에 보내기 전에 그래프의 후처리 노드를 거칩니다.

주요 코드 위치:

- `backend/executors/vla_nodes.py`
  - `exec_action_decode`: 모델 출력을 실행 가능한 액션 형태로 변환
  - `exec_safety_clamp`: 액션 값을 안전 범위로 제한

역할:

- 모델 출력에서 로봇 명령 필드 추출
- 좌표, 회전, 그리퍼, 관절 값 등을 실행 형식으로 정리
- 너무 큰 이동량이나 위험한 값 제한

## 7. Robot Execute 노드가 Unity로 명령을 보냄

`Robot Execute` 노드는 `mode`가 `unity`일 때 Unity 로봇 WebSocket으로 명령을 전송합니다.

주요 코드 위치:

- `backend/executors/robot_execute.py`
  - `exec_robot_execute`: 로봇 실행 진입점
- `backend/executors/vla_nodes.py`
  - `_unity_execute`: Unity WebSocket으로 명령 전송

기본 Unity 명령 엔드포인트:

```text
ws://host.docker.internal:9081/robot
```

`Robot Execute` 노드의 주요 설정:

- `mode`: `unity`
- `unityEndpoint`: Unity 로봇 명령 WebSocket 주소
- `unityStateClientId`: Unity 상태를 업데이트할 때 사용할 클라이언트 ID
- `waitForAck`: Unity ACK 응답을 기다릴지 여부
- `timeout`: Unity 응답 대기 시간

Unity로 보내는 명령은 대략 다음 형태입니다.

```json
{
  "type": "robot_command",
  "request_id": "graph-node-id-or-generated-id",
  "action": {
    "move": [0.01, 0.0, 0.0],
    "rotate": [0.0, 5.0, 0.0],
    "gripper": {
      "left": 0.0,
      "right": 1.0
    }
  }
}
```

Unity가 명령 처리 후 `robot_state`를 응답하면 백엔드는 그 상태를 다시 `state_store`에 저장합니다. 그래서 다음 루프에서 `Robot State (Unity)` 노드는 갱신된 Unity 상태를 읽을 수 있습니다.

## 8. Unity가 명령을 받아 적용함

Unity 쪽 WebSocket 서버는 백엔드에서 온 `robot_command` 메시지를 받고, Unity 메인 스레드에서 로봇 오브젝트에 적용합니다.

주요 코드 위치:

- `examples/unity/UnityHumanoidRobotBridge.cs`
  - `StartServer`: Unity 내부 WebSocket 서버 시작
  - `HumanoidRobotWsBehavior.OnMessage`: WebSocket 메시지 수신
  - `ProcessIncomingRequest`: 요청 하나를 처리하고 ACK/state 응답 묶음 생성
  - `ApplyRequest`: 요청 검증 후 `command` 값에 따라 실제 적용 함수로 분기
  - `TryMoveTargetDelta`: 이동 명령을 `NavMeshAgent` 또는 `Transform`에 적용
  - `ApplyJointTargetsCommand`: `ArticulationBody` 조인트 명령 적용
  - `SendResult`: 처리 결과 ACK와 선택적 최신 상태 전송

### 8.1 Unity WebSocket 서버 시작

Unity 브리지의 `StartServer`는 백엔드 `Robot Execute` 노드가 접속할 WebSocket 서버를 엽니다.

```csharp
_server = new WebSocketServer(port);
_server.AddWebSocketService<HumanoidRobotWsBehavior>(normalizedRoute);
HumanoidRobotWsBehavior.ProcessRequest = ProcessIncomingRequest;
_server.Start();
```

기본 설정이면 Unity는 다음 주소에서 명령을 기다립니다.

```text
ws://<unity-host>:9081/robot
```

Docker 컨테이너의 백엔드에서 호스트 PC의 Unity로 접속할 때는 보통 다음 주소를 사용합니다.

```text
ws://host.docker.internal:9081/robot
```

### 8.2 명령 JSON 수신

실제 WebSocket 메시지 수신은 `HumanoidRobotWsBehavior.OnMessage`에서 시작됩니다.

처리 순서:

```text
OnMessage
  -> JsonUtility.FromJson<HumanoidBridgeRobotCommandRequest>
  -> Unity 메인 스레드로 처리 예약
  -> ProcessIncomingRequest 호출
  -> SendResult로 ACK/state 응답
```

WebSocketSharp 콜백은 Unity 메인 스레드가 아닌 곳에서 호출될 수 있습니다. 그래서 `OnMessage`는 Unity 오브젝트, `NavMeshAgent`, `ArticulationBody`를 직접 만지지 않고 `Enqueue`를 통해 메인 스레드에서 실행되도록 예약합니다.

Unity API는 대부분 메인 스레드에서 접근해야 하므로 이 구조가 중요합니다.

### 8.3 명령 payload 구조

백엔드가 Unity로 보내는 요청 DTO는 `HumanoidBridgeRobotCommandRequest`입니다.

주요 필드:

```csharp
public string type;          // robot_command
public string request_id;    // 요청 추적 ID
public string scene;         // 적용할 Unity scene 이름
public string @object;       // 대상 Unity 오브젝트 이름
public string command;       // apply_action, apply_base_velocity 등
public string robot_type;    // generic, humanoid, arm 등
public string controller_mode;
public HumanoidBridgeRobotAction action;
```

예시:

```json
{
  "type": "robot_command",
  "request_id": "run-001",
  "scene": "SampleScene",
  "object": "RobotKyle",
  "command": "apply_humanoid_step",
  "robot_type": "humanoid",
  "controller_mode": "task",
  "action": {
    "move_x": 0.0,
    "move_z": 0.1,
    "turn_yaw": 5.0,
    "speed": 1.0
  }
}
```

### 8.4 요청 처리와 검증

`ProcessIncomingRequest`는 WebSocket으로 받은 요청 하나를 처리하고, 백엔드에 돌려줄 응답 묶음을 만듭니다.

흐름:

```text
대상 오브젝트 이름 결정
  -> 현재 scene 이름 확인
  -> ApplyRequest로 실제 명령 적용
  -> sendStateAfterCommand가 켜져 있으면 최신 robot_state 생성
  -> ACK와 state를 묶어 반환
```

`ApplyRequest`는 실제 명령을 적용하기 전에 다음을 확인합니다.

- `request`가 비어 있지 않은가
- `type`이 `robot_command`인가
- `action`이 존재하는가
- `requireSceneMatch`가 켜져 있을 때 요청 scene과 현재 scene이 같은가
- 명령 대상 Unity 오브젝트를 찾을 수 있는가

검증에 실패하면 Unity는 명령을 적용하지 않고 실패 ACK를 반환합니다.

### 8.5 command별 실제 적용 함수

`ApplyRequest`는 `command` 문자열을 정규화한 뒤 명령별 함수로 분기합니다.

지원되는 주요 명령:

```text
apply_action
apply_joint_targets
apply_joint_deltas
apply_joint_velocities
apply_base_velocity
apply_base_waypoint
apply_humanoid_step
stop
```

각 명령의 역할:

- `apply_action`: `translation`, `rotation` 기반의 기본 이동/회전 명령입니다.
- `apply_humanoid_step`: `move_x`, `move_z`, `turn_yaw`, `speed`를 사용해 휴머노이드형 캐릭터를 한 스텝 움직입니다.
- `apply_base_velocity`: `linear`, `angular` 또는 `linear_x`, `linear_z`, `angular_yaw`를 사용해 베이스 속도 명령처럼 처리합니다.
- `apply_base_waypoint`: `target_position`, `target_rotation`을 목표 위치/회전으로 해석합니다.
- `apply_joint_targets`: 조인트 목표 위치를 설정합니다.
- `apply_joint_deltas`: 현재 조인트 목표에 delta를 더합니다.
- `apply_joint_velocities`: 조인트 목표 속도를 설정합니다.
- `stop`: 이동 중인 `NavMeshAgent` 경로를 중지합니다.

### 8.6 이동 적용 방식

위치 이동은 `TryMoveTargetDelta`에서 처리됩니다.

`preferNavMeshAgent`가 켜져 있고 대상에 `NavMeshAgent`가 있으면:

```text
NavMesh.SamplePosition
  -> targetAgent.speed 설정
  -> targetAgent.SetDestination
```

그렇지 않으면:

```text
targetObject.transform.position = nextPoint
```

즉 캐릭터형 로봇은 `NavMeshAgent`로 이동할 수 있고, 단순 오브젝트는 `Transform`을 직접 변경합니다.

회전은 명령 종류에 따라 `targetObject.transform.eulerAngles`를 수정합니다.

### 8.7 조인트 적용 방식

조인트 명령은 `ApplyJointTargetsCommand`에서 처리됩니다.

처리 순서:

```text
대상 오브젝트의 ArticulationBody 목록 조회
  -> action에서 joint 값 배열 선택
  -> jointCommandScale 적용
  -> xDrive.target 또는 xDrive.targetVelocity 수정
```

명령별 사용 필드:

- `apply_joint_targets`: `joint_targets` 또는 `joint_positions`
- `apply_joint_deltas`: `joint_deltas`
- `apply_joint_velocities`: `joint_velocities`

이 경로는 로봇 팔이나 관절형 로봇을 제어할 때 사용합니다.

### 8.8 ACK와 최신 상태 응답

명령 적용이 끝나면 `SendResult`가 백엔드로 결과를 보냅니다.

응답 순서:

```text
1. robot_ack 전송
2. state가 있으면 robot_state 추가 전송
```

ACK 예시:

```json
{
  "ok": true,
  "type": "robot_ack",
  "request_id": "run-001",
  "applied": true,
  "message": "step=(1.00, 0.00, 2.00)",
  "error": "",
  "scene": "SampleScene",
  "target": "RobotKyle",
  "command": "apply_humanoid_step"
}
```

`sendStateAfterCommand`가 켜져 있으면 Unity는 `BuildRobotStateMessage`로 최신 상태를 만들어 추가로 보냅니다. 백엔드는 이 상태를 다시 `state_store`에 저장할 수 있고, 다음 그래프 루프에서 `Robot State (Unity)` 노드가 갱신된 상태를 읽습니다.

### 8.9 ApplyVlaAction과의 차이

`ApplyVlaAction`은 Unity가 직접 VLA 서버에 요청하고 받은 결과를 적용하는 직접 VLA 경로에서 사용됩니다.

반면 백엔드 그래프 런타임 경로는 다음 흐름을 사용합니다.

```text
Robot Execute
  -> Unity /robot WebSocket
  -> HumanoidRobotWsBehavior.OnMessage
  -> ProcessIncomingRequest
  -> ApplyRequest
  -> command별 적용 함수
```

따라서 `Robot State (Unity) -> OpenVLA Infer -> Robot Execute` 그래프 루틴을 디버깅할 때는 `ApplyVlaAction`보다 `OnMessage`, `ProcessIncomingRequest`, `ApplyRequest`, 각 `Apply*Command` 함수를 먼저 확인하는 것이 맞습니다.

요약하면 Unity에서 명령을 받아 수행하는 부분은 다음 순서로 보면 됩니다.

```text
백엔드 Robot Execute
  -> Unity /robot WebSocket
  -> OnMessage
  -> JSON 파싱
  -> 메인 스레드에서 ProcessIncomingRequest
  -> ApplyRequest
  -> command별 적용 함수
  -> Transform/NavMeshAgent/ArticulationBody 변경
  -> ACK 전송
  -> 필요하면 최신 robot_state 전송
```

## 권장 그래프 연결

최소 권장 연결은 다음과 같습니다.

```text
Prompt/Text 입력
  -> OpenVLA Infer.prompt

Camera/Image 입력
  -> OpenVLA Infer.image

Robot State (Unity).state
  -> OpenVLA Infer.state

OpenVLA Infer.action
  -> Action Decode.action
  -> Safety Clamp.action
  -> Robot Execute.action
```

`Robot Execute` 노드는 다음처럼 설정합니다.

```text
mode = unity
unityEndpoint = ws://host.docker.internal:9081/robot
unityStateClientId = Unity의 stateClientId와 동일한 값
```

## 반복 실행 모드

그래프에 `Robot State (Unity)`와 `Robot Execute(mode=unity)`가 함께 있으면 세션 런타임은 Unity 피드백을 기다리며 반복 실행할 수 있습니다.

흐름:

```text
초기 Unity 상태 대기
  -> 그래프 1회 실행
  -> Unity 명령 전송
  -> Unity ACK 또는 상태 갱신 대기
  -> 최신 상태로 다음 실행
```

이때 timeout이 발생하면 보통 다음 원인 중 하나입니다.

- Unity가 `/ws/unity/state`로 상태를 보내지 않음
- Unity의 `stateClientId`와 그래프의 `clientId`가 다름
- Unity 로봇 WebSocket 주소가 틀림
- Unity WebSocket 서버가 실행되지 않음
- Docker 컨테이너에서 Unity 호스트를 `localhost`로 접근하려고 함

Docker에서 백엔드 컨테이너가 호스트 PC의 Unity에 접근할 때는 보통 다음 주소를 사용합니다.

```text
ws://host.docker.internal:9081/robot
```

## 디버깅 체크리스트

Unity 상태 수신 확인:

```text
GET /api/unity/state/clients
GET /api/unity/state?client_id=RobotKyle
GET /api/unity/state?client_id=default
```

확인할 것:

- 클라이언트 목록에 Unity `stateClientId`가 보이는가
- `age_seconds`가 계속 작게 유지되는가
- `robot_state`가 비어 있지 않은가
- 그래프의 `Robot State (Unity).clientId`와 Unity `stateClientId`가 맞는가
- `Robot Execute.mode`가 `unity`인가
- `Robot Execute.unityEndpoint`가 Unity WebSocket 서버 주소와 맞는가
- Unity 콘솔에 `/robot` WebSocket 연결 로그가 있는가
- 백엔드 로그에 `/ws/unity/state` 연결 로그가 있는가

그래프 연결 확인:

- `Robot State (Unity).state`가 `OpenVLA Infer.state`에 연결되어 있는가
- `OpenVLA Infer.action`이 `Action Decode` 또는 `Robot Execute`까지 이어져 있는가
- `Safety Clamp`를 거친 출력이 최종 `Robot Execute.action`으로 들어가는가

## 직접 VLA Unity 모드와 그래프 런타임의 차이

`UnityHumanoidRobotBridge.cs`에는 Unity에서 직접 VLA 추론 API를 호출하는 경로도 있습니다.

관련 함수:

- `SendVlaInferRequest`
- `ApplyVlaAction`

이 경로는 Unity가 직접 VLA 서버에 요청하고 결과를 적용합니다. 백엔드 그래프 런타임의 `Robot State (Unity) -> OpenVLA Infer -> Robot Execute` 흐름과는 별도입니다.

그래프 기반 실행을 사용하려면 Unity는 상태를 백엔드로 보내고, 백엔드가 추론과 명령 전송을 담당해야 합니다.

## 요약

- Unity 상태는 `/ws/unity/state`로 백엔드에 전송됩니다.
- 백엔드는 상태를 `state_store`에 저장합니다.
- `Robot State (Unity)` 노드는 저장된 최신 상태를 읽습니다.
- `OpenVLA Infer`는 프롬프트, 이미지, Unity 상태를 이용해 액션을 추론합니다.
- `Action Decode`와 `Safety Clamp`가 액션을 실행 가능한 안전한 형태로 정리합니다.
- `Robot Execute(mode=unity)`가 Unity의 `/robot` WebSocket으로 명령을 보냅니다.
- Unity는 명령을 적용하고 ACK 및 최신 상태를 반환합니다.
