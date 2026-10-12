# Isaac Sim Spatial Learning RAG 개발 계획

작성일: 2026-06-16

## 목표

이 문서는 `C:\isaac_exts\robotis.omy.motion\docs\spatial-learning-rag-plan-2026-06-15.md`의 아이디어를 VLA Graph 현재 코드 구조에 맞춰 구현 가능한 개발 계획으로 정리한다.

목표는 Isaac Sim 공간 정보를 수집하고, JSONL 기반 공간 메모리로 저장한 뒤, 그래프 실행 시 관련 기억을 검색해서 OpenVLA 또는 GR00T 입력에 주입하는 것이다.

초기 목표는 완전한 자율 학습이 아니다. 먼저 신뢰할 수 있는 공간 record를 만들고, 이를 RAG context로 재사용하는 MVP를 만든다.

## 구현 상태

2026-06-16 현재 MVP 1차 구현 완료:

```text
완료:
- Isaac Sim bridge scan_scene command
- backend scene_scan 노드
- backend scene_context_reset 노드
- backend spatial_memory_save 노드
- backend spatial_rag_retrieve 노드
- backend spatial_context_builder 노드
- JSONL 저장/검색/context builder 유닛 테스트
- frontend Spatial 노드 등록
- frontend Spatial Data Collection 템플릿
- frontend Spatial RAG Graph 템플릿
- GR00T/OpenVLA prompt 입력에 spatial_context_builder.text 연결 가능
- robot_execute.result 기반 success/failure metadata 저장 경로

남은 후속:
- Isaac Sim 실제 stage에서 scan_scene object 품질 검증
- semantic label/custom attribute 품질 개선
- visible object/camera frustum 검증
- embedding retrieval 선택 기능
```

검증 완료:

```text
python -m unittest tests.test_spatial_nodes
python -m py_compile backend/executors/spatial_nodes.py backend/executors/registry.py examples/isaacsim/VlaGraphIsaacSimBridge.py
npm.cmd run build
/api/graph/run spatial save -> retrieve -> context builder smoke
```

## 전체 구조

```text
Isaac Sim scene
  -> scene_scan
  -> scene_context_reset
  -> spatial_memory_save
  -> spatial_memory.jsonl
  -> spatial_rag_retrieve
  -> spatial_context_builder
  -> OpenVLA or GR00T
  -> robot_execute
```

RAG는 로봇을 직접 제어하지 않는다. RAG는 모델과 planner가 참고할 공간 기억만 제공한다.

## 신규 노드

### scene_scan

Isaac Sim bridge에서 scene state를 읽어 구조화된 JSON으로 반환한다.

입력:

```text
state 또는 clientId
```

출력:

```text
scan: JSON
objects: JSON
robot: JSON
```

예상 데이터:

```json
{
  "scene_id": "lab_room_001",
  "robot": {
    "prim_path": "/World/GROOT_Humanoid",
    "position": [0.0, 0.0, 0.0],
    "rotation": [0.0, 0.0, 0.0]
  },
  "objects": [
    {
      "name": "table",
      "prim_path": "/World/Table",
      "position": [2.0, 1.0, 0.0],
      "size": [1.2, 0.8, 0.7]
    }
  ],
  "obstacles": []
}
```

### spatial_memory_save

`scene_scan` 결과, prompt, action, 실행 결과를 JSONL record로 저장한다.

기본 저장 위치:

```text
uploads/spatial_memory/spatial_memory.jsonl
```

출력:

```text
record: JSON
dataset: DATASET
```

### scene_context_reset

Isaac Sim scene이 바뀌었는지 감지하고, 현재 graph runtime의 spatial cache와 retrieval namespace를 재설정한다.

이 노드는 memory를 직접 삭제하지 않는다. 기본 정책은 이전 scene의 JSONL memory를 보존하고, 현재 실행에서 사용할 `scene_id`와 runtime cache만 새 scene 기준으로 바꾸는 것이다.

입력:

```text
scan: JSON
state: JSON
```

출력:

```text
scene: JSON
scene_id: TEXT
reset: JSON
```

출력 예:

```json
{
  "scene_changed": true,
  "previous_scene_id": "lab_room_001",
  "current_scene_id": "warehouse_002",
  "reset_applied": true,
  "memory_namespace": "warehouse_002",
  "message": "Scene changed; runtime spatial cache reset."
}
```

재설정 정책:

```text
runtime_only: 현재 그래프 실행 중 cache/history만 초기화
memory_namespace: scene_id별로 memory 검색 범위 분리
clear_scene_memory: 명시적으로 켠 경우에만 해당 scene memory 삭제
archive_previous: 이전 scene memory는 기본 보존
```

권장 기본값:

```text
scene이 바뀌면 runtime cache만 reset
JSONL memory는 삭제하지 않고 scene_id namespace로 분리
retrieval은 current scene_id를 우선 검색
```

### spatial_rag_retrieve

prompt, scene ID, visible object, robot pose를 기준으로 JSONL 공간 메모리를 검색한다.

MVP 검색 방식:

```text
scene_id match
object keyword match
task keyword match
success metadata boost
distance-to-waypoint boost
```

초기에는 embedding 없이 keyword + metadata scoring으로 시작한다.

### spatial_context_builder

검색된 memory record를 OpenVLA 또는 GR00T prompt에 붙일 짧은 context로 변환한다.

출력 예:

```text
Known spatial context:
- red box is on the table at [2.1, 0.4, 0.7].
- approach waypoint is [1.8, 0.2, 0.0].
- previous successful action: navigate_to table.

User task:
빨간 박스 앞으로 이동해.
```

## 구현 대상 파일

Backend:

```text
backend/executors/spatial_nodes.py
backend/executors/registry.py
backend/runtime/session_manager.py
backend/server.py
```

Frontend:

```text
frontend/src/types/graph.ts
frontend/src/nodeDefs.ts
frontend/src/components/layout/Sidebar.tsx
frontend/src/components/layout/Inspector.tsx
frontend/src/components/nodes/index.ts
frontend/src/pages/GraphPage.tsx
```

Isaac Sim bridge:

```text
examples/isaacsim/VlaGraphIsaacSimBridge.py
```

## 구현 순서

### 1. Isaac Sim scene scan command 추가

`VlaGraphIsaacSimBridge.py`에 command를 추가한다.

권장 command:

```text
scan_scene
```

처리 내용:

```text
/World 아래 prim 순회
robot prim pose 수집
object prim transform 수집
bbox 또는 scale 수집
semantic label 또는 name 추출
camera-visible 여부는 후속 단계로 분리
```

완료 기준:

```text
backend 또는 Script Editor에서 scan_scene 요청 시 objects 배열이 반환된다.
```

### 2. backend scene_scan 노드 추가

`backend/executors/spatial_nodes.py`를 만들고 `exec_scene_scan`을 구현한다.

처리 내용:

```text
node data에서 omniverseEndpoint 읽기
Isaac Sim bridge websocket으로 scan_scene 요청
응답을 scene_id, robot, objects, obstacles 구조로 정규화
```

`backend/executors/registry.py`에 등록한다.

완료 기준:

```text
그래프에서 scene_scan 노드 실행 시 scan JSON이 context에 저장된다.
```

### 3. spatial_memory_save 구현

같은 `spatial_nodes.py`에 `exec_spatial_memory_save`를 추가한다.

처리 내용:

```text
scene scan record 수신
prompt, action, result 수신
record id 생성
text field 생성
metadata 생성
uploads/spatial_memory/spatial_memory.jsonl에 append
```

JSONL record 예:

```json
{
  "id": "lab_room_001_red_box_table_001",
  "text": "lab_room_001에서 red box는 table 위 x=2.1 y=0.4 z=0.7 위치에 있다. 접근 waypoint는 x=1.8 y=0.2 yaw=0.0이다.",
  "metadata": {
    "scene_id": "lab_room_001",
    "object": "red box",
    "object_position": [2.1, 0.4, 0.7],
    "approach_waypoint": [1.8, 0.2, 0.0],
    "source": "isaac_sim",
    "success": true
  }
}
```

완료 기준:

```text
그래프 실행 후 uploads/spatial_memory/spatial_memory.jsonl에 record가 누적된다.
```

### 4. scene_context_reset 구현

`exec_scene_context_reset`을 추가한다.

처리 내용:

```text
scene_scan 결과에서 scene_id, stage identifier, object signature 추출
이전 scene signature와 현재 signature 비교
scene_changed=true이면 runtime spatial cache 초기화
현재 scene_id를 memory_namespace로 설정
clear_scene_memory 옵션이 true일 때만 해당 scene memory 삭제
```

scene signature 후보:

```text
scene_id
omniverse stage url
root prim path
object prim path 목록 hash
robot prim path
```

완료 기준:

```text
Isaac Sim stage 또는 scene_id가 바뀌면 scene_changed=true가 출력된다.
다른 scene의 memory가 기본 retrieval 결과에 섞이지 않는다.
```

### 5. spatial_rag_retrieve 구현

`exec_spatial_rag_retrieve`를 추가한다.

처리 내용:

```text
JSONL 파일 읽기
prompt token 추출
scene_id filter
object keyword match
metadata boost
top_k 반환
```

초기 scoring:

```text
+3 scene_id match
+2 object/name keyword match
+1 task keyword match
+1 success=true
- distance penalty, waypoint가 있을 경우
```

완료 기준:

```text
prompt "red box 앞으로 이동" 입력 시 red box 관련 memory가 top result로 나온다.
```

### 6. spatial_context_builder 구현

`exec_spatial_context_builder`를 추가한다.

처리 내용:

```text
retrieved memories를 3~5줄 context로 압축
원본 prompt와 결합
TEXT output으로 반환
```

완료 기준:

```text
builder 출력 text를 openvla_infer 또는 gr00t_infer prompt input에 연결할 수 있다.
```

### 7. frontend 노드 등록

`frontend/src/types/graph.ts`에 node type 추가:

```text
scene_scan
scene_context_reset
spatial_memory_save
spatial_rag_retrieve
spatial_context_builder
```

`frontend/src/nodeDefs.ts`에 node def 추가:

```text
scene_scan: outputs scan, objects, robot
scene_context_reset: inputs scan/state, outputs scene/scene_id/reset
spatial_memory_save: inputs scan, prompt, action, result
spatial_rag_retrieve: inputs prompt, scan/state
spatial_context_builder: inputs prompt, memories
```

`Sidebar.tsx`에 Spatial 그룹을 추가한다.

완료 기준:

```text
UI에서 신규 노드를 추가하고 edge를 연결할 수 있다.
```

### 8. 그래프 템플릿 추가

`frontend/src/pages/GraphPage.tsx`에 두 템플릿을 추가한다.

Spatial Data Collection Graph:

```text
Prompt
  -> Scene Scan
  -> Scene Context Reset
  -> Spatial Memory Save
  -> Print or Dataset Preview
```

권장 확장:

```text
Unity/Isaac State
Remote Image
Remote LiDAR
Robot Execute Result
```

Spatial RAG Graph:

```text
Prompt
  -> Scene Scan
  -> Scene Context Reset
  -> Spatial RAG Retrieve
  -> Spatial Context Builder
  -> GR00T or OpenVLA
  -> Robot Execute
```

완료 기준:

```text
Graph Template 드롭다운에서 두 템플릿을 선택할 수 있다.
```

### 9. OpenVLA / GR00T 연결

MVP에서는 `openvla_infer`, `gr00t_infer` executor를 크게 바꾸지 않는다.

연결 방식:

```text
spatial_context_builder.text -> openvla_infer.prompt
spatial_context_builder.text -> gr00t_infer.prompt
```

후속 개선:

```text
payload.spatial_context 필드를 별도로 추가
request debug에 retrieved memory 표시
```

완료 기준:

```text
infer request 로그에 공간 context가 포함된다.
```

### 10. success/failure metadata 저장

`robot_execute.result`를 `spatial_memory_save`에 연결해서 성공 여부를 저장한다.

저장 metadata:

```text
success
error
action_type
waypoint
target_object
executed_at
```

완료 기준:

```text
성공한 action이 retrieval에서 우선 검색된다.
```

### 11. embedding retrieval 추가

JSONL 포맷이 안정화된 뒤 embedding을 추가한다.

후보:

```text
local sentence-transformers
OpenAI embeddings
FAISS 또는 sqlite-vss
```

초기에는 선택 기능으로 두고 keyword retrieval이 항상 fallback 되게 한다.

## 테스트 계획

### Unit 테스트

```text
JSONL append/read
keyword scoring
context builder formatting
scene scan response normalization
```

### 통합 테스트

```text
Isaac Sim bridge scan_scene 응답 확인
Spatial Data Collection Graph 실행
spatial_memory.jsonl record 생성 확인
Spatial RAG Graph 실행
OpenVLA/GR00T request에 context 포함 확인
```

### 수동 검증 시나리오

1. Isaac Sim에서 table, red box, obstacle이 있는 stage를 연다.
2. Spatial Data Collection Graph를 실행한다.
3. `uploads/spatial_memory/spatial_memory.jsonl`에 record가 저장되는지 확인한다.
4. Prompt에 "red box 앞으로 이동해"를 입력한다.
5. Spatial RAG Graph를 실행한다.
6. context에 red box 위치와 waypoint가 들어가는지 확인한다.
7. robot_execute가 기존 safety 경로를 통해 실행되는지 확인한다.

## 사용법

### 1. Docker backend/frontend 다시 빌드

spatial 노드와 frontend 템플릿이 추가되었으므로 코드 변경 후에는 backend/frontend를 다시 빌드한다.

```powershell
cd C:\Users\0\Desktop\vlagraph
docker compose up -d --build backend frontend
```

RealSense RGB-D 그래프도 함께 사용할 경우 Windows host bridge를 먼저 켠다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_realsense_host_bridge.ps1 -NoMockFallback
```

### 2. Isaac Sim bridge 다시 실행

`scan_scene` command는 `examples/isaacsim/VlaGraphIsaacSimBridge.py` 안에 있으므로 Isaac Sim Script Editor에서 bridge를 새로 실행해야 한다.

```python
exec(open(r"C:\Users\0\Desktop\vlagraph\examples\isaacsim\run_kyle_camera_bridge.py").read())
```

Isaac Sim console에 아래와 같은 WebSocket 주소가 보이면 정상이다.

```text
command_ws=ws://0.0.0.0:9900/omniverse
```

VLA Graph backend에서는 보통 아래 endpoint로 접근한다.

```text
ws://host.docker.internal:9900/omniverse
```

### 3. Spatial Data Collection으로 공간 기억 저장

브라우저에서 VLA Graph를 연다.

```text
http://localhost:9173
```

상단 `Graph Template`에서 아래 템플릿을 선택한다.

```text
Spatial Data Collection
```

그래프 흐름:

```text
Prompt
-> Robot State (Isaac Sim)
-> Scene Scan
-> Scene Context Reset
-> Spatial Memory Save
-> Print
```

권장 설정:

```text
Prompt.text = red box 앞으로 이동해

Scene Scan.omniverseEndpoint = ws://host.docker.internal:9900/omniverse
Scene Scan.omniversePrimPath = /World/KyleRobot
Scene Scan.sceneRootPath = /World
Scene Scan.maxObjects = 256

Spatial Memory Save.memoryPath = spatial_memory/spatial_memory.jsonl
Spatial Memory Save.success = true
```

`Run Graph`를 누르면 아래 JSONL 파일에 공간 기억이 누적된다.

```text
uploads/spatial_memory/spatial_memory.jsonl
```

저장 record 예:

```json
{
  "text": "In scene lab_room_001, red box is at x=2.1 y=0.4 z=0.7. Approach waypoint is x=1.8 y=0.2 yaw=0.0.",
  "metadata": {
    "scene_id": "lab_room_001",
    "object": "red box",
    "object_position": [2.1, 0.4, 0.7],
    "approach_waypoint": [1.8, 0.2, 0.0],
    "source": "isaac_sim",
    "success": true
  }
}
```

저장 결과는 PowerShell에서 확인할 수 있다.

```powershell
Get-Content uploads\spatial_memory\spatial_memory.jsonl -Tail 5
```

### 4. Spatial RAG Graph로 기억 검색 및 prompt 주입

상단 `Graph Template`에서 아래 템플릿을 선택한다.

```text
Spatial RAG Graph
```

그래프 흐름:

```text
Prompt
-> Robot State (Isaac Sim)
-> Scene Scan
-> Scene Context Reset
-> Spatial RAG Retrieve
-> Spatial Context Builder
-> GR00T Infer
-> Safety Clamp
-> Robot Execute
-> Print
```

`Prompt.text`에 작업을 입력한다.

```text
red box 앞으로 이동해
```

`Spatial RAG Retrieve`는 기본적으로 아래 파일에서 관련 기억을 검색한다.

```text
spatial_memory/spatial_memory.jsonl
```

MVP 검색 기준:

```text
scene_id 일치
object/name keyword 일치
prompt/task keyword 일치
success=true 우대
approach waypoint 거리 보정
```

`Spatial Context Builder`는 검색된 기억을 짧은 context로 압축한 뒤 원래 prompt와 결합한다.

```text
Known spatial context:
- In scene lab_room_001, red box is at x=2.1 y=0.4 z=0.7. Approach waypoint is x=1.8 y=0.2 yaw=0.0.

User task:
red box 앞으로 이동해
```

이 `text` 출력은 `gr00t_infer.prompt` 또는 `openvla_infer.prompt`에 연결해서 사용한다.

### 5. 정상 동작 확인

backend container에서 spatial 노드가 등록되었는지 확인한다.

```powershell
docker exec openvla_backend python -c "from backend.executors.registry import NODE_EXECUTORS; print('scene_scan' in NODE_EXECUTORS, 'spatial_rag_retrieve' in NODE_EXECUTORS)"
```

예상 출력:

```text
True True
```

그래프 실행 로그에서 아래 메시지를 확인한다.

```text
Scene scan returned N objects.
Saved spatial memory record for scene=...
Retrieved N spatial memories for scene=...
Built spatial context with N memory lines.
```

### 6. 현재 MVP 주의점

현재 retrieval은 embedding 기반이 아니라 keyword + metadata scoring 기반이다. 따라서 Isaac Sim prim 이름과 semantic label 품질이 중요하다.

좋은 prim 이름:

```text
red_box
table
obstacle_wall
target_marker
```

피해야 할 prim 이름:

```text
Cube_01
Xform_12
mesh_003
```

현재 `scan_scene`은 `/World` 아래 prim transform, bbox, name, semantic attribute를 중심으로 저장한다. 카메라에 실제로 보이는지 여부, semantic segmentation, visible object filtering은 후속 단계로 둔다.

## 우선순위

1. `scene_scan` + bridge command
2. `scene_context_reset`으로 scene 변경 감지 및 namespace 분리
3. JSONL save
4. keyword retrieve
5. context builder
6. frontend node/template
7. OpenVLA/GR00T prompt 연결
8. success/failure feedback
9. embedding retrieval

## 리스크

Isaac Sim scene scan의 가장 큰 리스크는 prim 이름과 semantic label의 품질이다. 초기에는 name 기반으로 시작하고, 이후 semantic label 또는 custom attribute를 추가한다.

Depth, LiDAR, camera visible object까지 한 번에 완벽하게 처리하려고 하면 범위가 커진다. MVP에서는 scene graph transform을 먼저 저장하고, visible object 검증은 후속 단계로 둔다.

RAG context가 너무 길면 OpenVLA/GR00T 행동이 흔들릴 수 있다. context builder는 3~5개 bullet로 제한한다.

## 최종 완료 기준

다음이 가능하면 1차 완료로 본다.

```text
1. Isaac Sim stage에서 scene_scan이 object 위치를 읽는다.
2. scene_context_reset이 scene 변경을 감지하고 current scene namespace를 설정한다.
3. 공간 정보가 JSONL로 저장된다.
4. prompt 기반으로 관련 memory가 검색된다.
5. 검색 결과가 prompt context로 변환된다.
6. OpenVLA 또는 GR00T 그래프 실행 request에 context가 포함된다.
7. robot_execute는 기존 safety/action stack을 그대로 사용한다.
```
