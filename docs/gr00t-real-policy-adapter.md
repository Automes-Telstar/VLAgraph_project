# 실제 NVIDIA Isaac GR00T 서버 연결

VLA Graph의 `NVIDIA GR00T Infer` 노드는 HTTP `/infer`를 호출하고, Docker의 `gr00t_policy_adapter`가 이 요청을 Isaac-GR00T `PolicyClient.get_action()` 호출로 변환합니다. 실제 모델 로딩은 `gr00t_policy_server`가 맡습니다.

## 실행 구조

```text
VLA Graph backend
  -> http://gr00t_policy_adapter:9072/infer
  -> gr00t_policy_adapter
  -> PolicyClient(host=gr00t_policy_server, port=5555)
  -> gr00t_policy_server
  -> /models/GR00T-N1.7-3B + /models/Cosmos-Reason2-2B
```

현재 Compose 기본값은 stub fallback을 사용하지 않습니다.

```env
COMPOSE_PROFILES=gr00t-real
ENABLE_REAL_GR00T=true
ROUTE_GR00T_REAL=http://gr00t_policy_adapter:9072
GR00T_FALLBACK_TO_STUB=false
```

## 실행

모델 Docker volume `vlagraph_gr00t_models`에 아래 경로가 있어야 합니다.

```text
/models/GR00T-N1.7-3B
/models/Cosmos-Reason2-2B
```

실행 명령:

```powershell
cd C:\Users\0\Desktop\vlagraph
docker compose up -d --build
```

기본 `.env`가 `gr00t-real` profile을 자동 활성화하므로 별도 `--profile` 옵션이 필요하지 않습니다.

상태 확인:

```powershell
Invoke-RestMethod "http://localhost:9072/health" | ConvertTo-Json -Depth 10
```

## G1 입력 매핑

`GR00T-N1.7-3B`의 `REAL_G1` processor 설정을 읽어서 observation을 자동 구성합니다.

```text
video    -> ego_view
language -> annotation.human.task_description
state    -> left_wrist_eef_9d, right_wrist_eef_9d,
            left_hand, right_hand, left_arm, right_arm, waist
```

Isaac Sim bridge가 VLA Graph backend로 camera/state를 올리고, 그래프의 `Remote Image Sensor`와 `Robot State (Unity)` 노드가 이를 `NVIDIA GR00T Infer` 노드에 연결합니다. `actionHorizon` 기본값은 G1 정책 chunk와 맞춘 `40`입니다.

## 로컬 Cosmos 참조

`gr00t_policy_server`는 read-only 모델 volume을 직접 수정하지 않고 `/tmp/vlagraph_gr00t_model`에 얕은 overlay를 만든 뒤 `config.json`과 `processor_config.json`만 로컬 `/models/Cosmos-Reason2-2B`를 보도록 조정합니다. 그래서 Hugging Face repo ID로 다시 다운로드하지 않고 Docker volume의 모델을 사용합니다.
