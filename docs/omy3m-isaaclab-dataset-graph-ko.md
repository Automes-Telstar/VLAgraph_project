# OMY3M 6DOF + IsaacLab Dataset 그래프

그래프 템플릿 메뉴에서 `OMY3M 6DOF + IsaacLab Dataset`을 선택한다.

## 실행 전 조건

1. Isaac Sim에서 OMY3M USD와 `robotis.omy6dof.learning` 확장을 로드한다.
2. Stage에 `/World/OMY3M_Learning/Robot`이 존재해야 한다.
3. VLAGRAPH Isaac Sim 브리지가 `ws://127.0.0.1:9900/omniverse`에서 실행 중이어야 한다.
4. 브리지가 `isaacsim01` client ID로 상태와 손목 이미지를 backend에 publish해야 한다.
5. 실제 USD 관절 이름이 기본 `joint1`~`joint6`과 다르면 두 OMY3M 노드의 `jointNames`를 수정한다.

## 그래프 흐름

```text
작업 지시 ───────────────┐
                         ├→ OMY3M 6축 Action → Isaac Sim 실행 ─┐
손목 카메라 ─────────────┤                                  │
로봇 상태 ───────────────┴→ IsaacLab 데이터 저장 ←───────────┘
```

`OMY3M 6축 관절 Action`의 `jointPositions`는 라디안 단위이며 정확히 6개여야 한다.
`jointLimitRad` 범위를 넘는 값은 전송 전에 제한된다.

## 저장 결과

Docker backend에서는 기본적으로 다음 위치에 저장한다.

```text
/tmp/openvla_uploads/isaaclab_datasets/omy3m/<episodeName>/
├── metadata.json
├── steps.jsonl
└── images/
    └── wrist/
```

기본 Docker volume 설정에서는 Windows 호스트의 다음 폴더에 대응한다.

```text
C:\Users\0\Desktop\vlagraph\uploads\isaaclab_datasets\omy3m\<episodeName>\
```

각 JSONL step에는 다음 값이 들어간다.

- 언어 작업 지시
- 실행 전 로봇 상태
- 브리지 응답에 포함된 실행 후 로봇 상태
- 손목 RGB 이미지 파일 경로
- VLAGRAPH가 명령한 6축 action
- Isaac Sim 실행 결과
- reward, terminated, success

그래프를 실행할 때마다 같은 `episodeName`의 `steps.jsonl`에 한 step이 추가된다.
새 demonstration을 시작할 때는 `episodeName`을 변경한다.

이 형식은 `vlagraph.isaaclab.omy3m.v1` 사용자 정의 demonstration 스키마다.
Isaac Lab 온라인 RL 자체의 표준 데이터 파일을 의미하지 않으며, 모방학습 또는
사용자 정의 dataset loader에서 읽도록 설계되어 있다.
