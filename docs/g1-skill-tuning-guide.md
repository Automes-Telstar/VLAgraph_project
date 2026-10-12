# G1 Skill Decode 튜닝 가이드

이 문서는 VLA Graph에서 자연어 프롬프트를 Unitree G1 / GR00T humanoid motion으로 안정적으로 연결하기 위한 튜닝 기준을 정리합니다.

핵심 방향은 VLA/GR00T/LLM을 저수준 관절 제어기가 아니라 planner로 보고, 실제 Isaac Sim 실행에는 제한된 skill API를 넘기는 것입니다.

```text
Prompt
  -> GR00T / LLM planner
  -> g1_skill_decode 또는 action_decode
  -> safety_clamp
  -> robot_execute
  -> Isaac Sim locomotion / articulation controller
```

## 튜닝 기준 노드

### 1. g1_skill_decode

가장 권장하는 튜닝 기준 노드입니다.

역할:

```text
무한한 자연어 프롬프트
  -> 제한된 G1 skill command
```

예시:

```json
{
  "type": "g1_skill_command",
  "command": "apply_g1_skill",
  "skill": "walk",
  "direction": { "x": 0.0, "y": -1.0 },
  "velocity": {
    "forward": -0.55,
    "lateral": 0.0,
    "yaw": 0.0
  },
  "duration_sec": 3.0
}
```

이 노드에서 튜닝해야 하는 것:

- prompt -> skill 분류
- forward / backward / left / right 방향 해석
- turn angle / yaw velocity 해석
- duration, speed, amplitude 추론
- go_to_pose target pose 추출
- 지원하지 않는 프롬프트를 안전하게 stand 또는 unknown으로 처리

기준 파일:

```text
backend/executors/g1_skill_nodes.py
```

## 현재 그래프 유지 시 기준 노드

현재 기본 그래프가 아래처럼 구성되어 있다면 `action_decode`가 사실상 skill decoder 역할을 해야 합니다.

```text
prompt
  -> gr00t_infer
  -> action_decode
  -> safety_clamp
  -> robot_execute
```

이 경우 `action_decode`에서 해야 할 일:

- GR00T raw action을 그대로 통과시키지 않기
- prompt text를 복구하기
- `decodeMode=default` 또는 `decodeMode=g1_skill`에서 `g1_skill_command` 생성하기
- `left_arm`, `right_arm`, `navigate_command` 같은 raw policy action보다 prompt intent를 우선하기

기준 파일:

```text
backend/executors/vla_nodes.py
```

정상 로그 예시:

```text
node-5 (action_decode) -> {
  "decoded": {
    "type": "g1_skill_command",
    "command": "apply_g1_skill",
    "skill": "walk",
    "velocity": {
      "forward": -0.55
    }
  }
}
```

비정상 로그 예시:

```text
node-5 (action_decode) -> {
  "decoded": {
    "left_wrist_eef_9d": [...],
    "right_wrist_eef_9d": [...],
    "left_arm": [...],
    "right_arm": [...]
  }
}
```

비정상 로그처럼 raw GR00T action이 나오면 prompt별 동작이 전부 비슷해질 수 있습니다.

## 튜닝하면 안 좋은 노드

### robot_execute

`robot_execute`는 이미 결정된 action을 Isaac Sim, Unity, ROS 등으로 전송하는 실행 계층입니다.

여기서 prompt intent 튜닝을 하면 다음 문제가 생깁니다.

- planner와 executor 책임이 섞임
- Isaac 전용 예외 처리가 늘어남
- 같은 그래프를 다른 로봇이나 시뮬레이터에 재사용하기 어려움
- 로그상 어떤 노드가 의사결정을 했는지 추적하기 어려움

따라서 `robot_execute`는 action 전송과 ACK 확인에만 집중시키는 편이 좋습니다.

### gr00t_infer

`gr00t_infer`는 GR00T 모델의 raw policy action을 얻는 노드입니다.

2번 방식에서는 이 노드를 저수준 제어기로 쓰기보다 planner 보조 신호로 쓰는 것이 안정적입니다.

권장 역할:

- 이미지, 상태, 프롬프트를 보고 상황 판단
- 가능한 행동 후보 제공
- skill decoder가 참고할 raw action 또는 context 제공

비권장 역할:

- 모든 자연어 프롬프트를 직접 관절 action으로 완벽히 변환
- Isaac locomotion controller를 우회해서 raw joint action만으로 모든 동작 실행

## Skill API 기준

튜닝의 목표는 자연어를 아래처럼 제한된 skill API로 압축하는 것입니다.

기본 locomotion:

```text
stand
walk
run
sidestep
turn
go_to_pose
stop
reset
```

기본 gesture / whole-body motion:

```text
wave
dance
crouch
bow
kick
punch
stretch
raise_arms
lower_arms
reach
push
pull
clap
nod
shake_head
look_left
look_right
look_up
look_down
jump
```

새 action을 추가할 때는 자유로운 자연어 문장을 무한히 추가하는 것이 아니라, 먼저 skill API를 확장합니다.

예시:

```text
"make a greeting motion" -> wave
"move backward"          -> walk + direction.y = -1
"turn right 90 degrees"  -> turn + yaw < 0
"go to x=1 y=2 z=0"      -> go_to_pose + target_pose
```

## 룰 기반 튜닝

가장 먼저 적용할 방식입니다.

적합한 경우:

- 명령어가 비교적 짧음
- skill 종류가 제한적임
- 빠르게 안정성을 확보해야 함
- Isaac Sim에서 prompt별 동작 차이를 바로 보고 싶음

튜닝 위치:

```text
backend/executors/g1_skill_nodes.py
```

튜닝 항목:

- keyword alias 추가
- 한국어 / 영어 동의어 추가
- left / right / forward / backward 방향 규칙 추가
- duration / speed / angle parser 보강
- 모호한 prompt fallback 규칙 추가

주의할 점:

- `move` 같은 너무 일반적인 단어를 무조건 `walk`로 매핑하면 gesture prompt도 walk로 오인될 수 있음
- GR00T의 `navigate_command`가 prompt skill을 덮어쓰면 여러 프롬프트가 모두 forward walk가 될 수 있음
- prompt에서 명확한 skill이 나온 경우 raw policy action보다 prompt skill을 우선해야 함

## RAG 기반 튜닝

RAG는 모델을 직접 재학습하지 않고, skill 선택에 필요한 지식과 예시를 검색해서 decoder에 제공하는 방식입니다.

적합한 경우:

- skill 설명이 늘어남
- 같은 명령을 여러 표현으로 입력함
- 현장별 명령어 사전이 필요함
- 한국어/영어/혼합 표현을 유연하게 처리해야 함

RAG 문서 예시:

```json
{
  "utterances": [
    "walk backward",
    "move back",
    "뒤로 걸어",
    "후진해"
  ],
  "skill": "walk",
  "direction": { "x": 0.0, "y": -1.0 },
  "notes": "Backward locomotion. Do not map to turn."
}
```

권장 흐름:

```text
prompt
  -> retrieve similar skill examples
  -> LLM or rule decoder receives retrieved examples
  -> g1_skill_command
```

RAG를 붙이기 좋은 위치:

```text
g1_skill_decode 내부
또는
g1_skill_decode 앞의 별도 planner/retriever 노드
```

RAG가 해결하는 것:

- 동의어 확장
- site-specific 명령어
- skill 선택 설명 가능성
- 새 프롬프트 대응 속도

RAG가 해결하지 않는 것:

- 실제 보행 안정성
- 관절 제어 품질
- physics controller 성능

## LLM planner 기반 튜닝

LLM을 skill planner로 쓰는 방식입니다.

LLM 출력은 반드시 구조화된 JSON으로 제한해야 합니다.

권장 출력:

```json
{
  "skill": "turn",
  "duration_sec": 2.0,
  "speed": 0.55,
  "direction": { "x": 0.0, "y": 0.0 },
  "turn_degrees": 90,
  "target_pose": null
}
```

권장 검증:

- skill이 지원 목록에 있는지 확인
- duration 범위 clamp
- speed 범위 clamp
- direction normalize
- target_pose 길이 확인
- safety_clamp 통과

LLM planner는 자유롭게 말하게 두면 안 됩니다. 항상 제한된 schema로 출력하게 해야 합니다.

## LoRA / fine-tuning 기준

LoRA는 두 가지 방향이 있습니다.

### 1. LLM planner LoRA

자연어 prompt를 skill JSON으로 잘 바꾸도록 학습합니다.

학습 샘플:

```json
{
  "input": "walk backward slowly for 3 seconds",
  "output": {
    "skill": "walk",
    "direction": { "x": 0.0, "y": -1.0 },
    "speed": 0.28,
    "duration_sec": 3.0
  }
}
```

추천도:

```text
높음
```

이유:

- 데이터 만들기 쉬움
- 안정적으로 검증 가능
- 실제 로봇 physics와 분리됨
- RAG와 함께 쓰기 쉬움

### 2. GR00T policy LoRA

이미지/상태/언어를 보고 직접 저수준 action을 더 잘 만들도록 학습합니다.

추천도:

```text
중간 또는 낮음
```

이유:

- 데이터 수집 비용이 큼
- 관절 action 품질 검증이 어려움
- Isaac controller와 policy action space가 정확히 맞아야 함
- 실패 시 모든 prompt가 비슷한 locomotion으로 무너질 수 있음

현재 구조에서는 먼저 LLM planner 또는 g1_skill_decode 튜닝을 권장합니다.

## 데이터셋 포맷

튜닝 데이터는 prompt와 skill command를 한 쌍으로 저장하는 것이 좋습니다.

```json
{
  "prompt": "turn right 90 degrees",
  "expected": {
    "type": "g1_skill_command",
    "command": "apply_g1_skill",
    "skill": "turn",
    "velocity": {
      "forward": 0.0,
      "lateral": 0.0,
      "yaw": -0.5236
    },
    "duration_sec": 3.0
  }
}
```

최소 평가 세트:

```text
walk forward
walk backward
sidestep left
sidestep right
turn left 90 degrees
turn right 90 degrees
wave hello
raise arms
lower arms
crouch
stand still
stop
go to x=1 y=0 z=0
```

## 성공 기준

그래프 로그에서 `action_decode` 또는 `g1_skill_decode` 출력이 아래 조건을 만족해야 합니다.

필수:

```text
type == g1_skill_command
command == apply_g1_skill
skill != empty
```

locomotion 필수:

```text
walk backward -> velocity.forward < 0
walk forward  -> velocity.forward > 0
sidestep left -> velocity.lateral < 0
sidestep right -> velocity.lateral > 0
turn left -> velocity.yaw > 0
turn right -> velocity.yaw < 0
```

gesture 필수:

```text
wave hello -> skill == wave
raise arms -> skill == raise_arms
crouch -> skill == crouch
```

비정상 신호:

```text
모든 prompt가 skill == walk
모든 prompt가 velocity.forward > 0
action_decode 출력에 left_arm/right_arm만 있음
robot_execute에서 처음으로 skill을 추론함
```

## 디버깅 순서

1. `node-1 (prompt)`에 원하는 문장이 들어갔는지 확인합니다.
2. `node-5 (action_decode)`가 `g1_skill_command`를 출력하는지 확인합니다.
3. `node-6 (safety_clamp)` 이후에도 `skill`, `velocity`, `direction`이 유지되는지 확인합니다.
4. `node-7 (robot_execute)` result의 `action`에 `apply_g1_skill`이 들어갔는지 확인합니다.
5. Isaac Sim bridge 상태가 `skill applied: ...` 또는 `prompt intent applied: ...`인지 확인합니다.

가장 중요한 확인 지점:

```text
node-5 action_decode
```

여기서 raw GR00T joint/policy action이 그대로 보이면 아직 2번 방식이 적용되지 않은 것입니다.

## 권장 운영 방식

초기 안정화:

```text
rule-based g1_skill_decode
```

명령어가 늘어날 때:

```text
RAG examples + rule fallback
```

자연어 다양성이 커질 때:

```text
LLM planner with strict JSON schema
```

실제 policy 품질을 올릴 때:

```text
GR00T policy fine-tuning
```

권장 우선순위:

```text
1. g1_skill_decode rule tuning
2. RAG example retrieval
3. LLM planner JSON output
4. GR00T policy LoRA
```

