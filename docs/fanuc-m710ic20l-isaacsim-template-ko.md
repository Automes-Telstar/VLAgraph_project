# FANUC M-710iC/20L Isaac Sim 실행 템플릿

Graph Template에서 `FANUC M-710iC/20L Execute`를 선택합니다.

1. `FANUC M-710 LS 파일 업로드`에서 `.LS` 파일을 선택합니다.
2. `FANUC LS 파싱`이 `/MN`, `/POS` 레코드를 읽습니다.
3. `M-710 J1~J6 명령 준비`가 joint 레코드와 Cartesian 레코드를 전용 bridge action으로 변환합니다.
4. 안전 요약에서 실행 프레임, IK 성공 및 실패 프레임 수를 확인합니다.
5. `FANUC M-710 Isaac Sim 실행`이 `ws://host.docker.internal:9910/omniverse`로 명령을 보냅니다.

Isaac Sim에서 `fanuc.m710ic20l.motion` 확장을 먼저 활성화합니다. 창의 bridge 상태가
`running`이고 로봇 상태가 `physics_ready=true`인지 확인하십시오. 초기화가 필요하면
bridge에 `{"command":"init"}`를 보내거나 확장 UI에서 로드 및 물리 초기화를 실행합니다.

`J1`~`J6` 레코드는 그대로 실행합니다. `XYZ/WPR` 레코드는 확장에 포함된 M-710 USD의
링크·축·관절 한계를 이용해 수치 IK로 변환합니다. 실제 UFRAME/UTOOL Stage 보정값이
없으므로 각 UF/UT 그룹의 첫 위치를 기준으로 이동과 회전을 상대 변환합니다. 기본 위치
스케일과 상대 회전 스케일은 각각 1.0이며, IK 기본 허용 오차는 위치 0.001m, 자세 1도입니다.
자세 가중치는 0.75로 설정되어 TCP 방향을 이전보다 강하게 추종합니다. `CONFIG : 'N U T, ...'`
값은 raw flag와 turn 값으로 보존되어 이후 configuration IK에 사용할 수 있습니다.
`uframeTransforms`에 실제 UFRAME Stage 변환을 넣으면 상대 anchor 대신 보정된 절대 pose를
사용합니다. 값은 예를 들어 `{"4":{"xyzMm":[0,0,0],"wprDeg":[0,0,0]}}` 형태입니다.
`utoolTransforms`에는 실제 TCP offset/orientation을 같은 형식으로 넣을 수 있습니다.

USD의 joint-frame 회전을 반영해 J3~J6의 회전축 부호를 계산합니다. 수치 IK가 이전 seed에서
140도 이상 떨어진 branch로 이동하면 configuration 유지 실패로 간주해 해당 Cartesian 프레임을
건너뜁니다. `requireAllIk=false`이므로 IK 실패 프레임은 건너뛰고 성공 프레임은 실행합니다.
기본 `timingMode=source_speed`에서는 LS의 `mm/sec`와 `%` 속도로 timestamp를 생성하고,
`FINE/CNTn`은 `cnt_percent` 메타데이터로 bridge에 전달합니다. 기존처럼 전체 시간을 균등
분배하려면 `timingMode=fixed_total`과 `totalDurationSec`를 사용합니다.

이 IK는 UF/UT 그룹별 상대 이동 재현용입니다. FANUC 절대 좌표를 Isaac Stage에서 정확히
재현하려면 각 UFRAME의 Stage 변환과 UTOOL/TCP 오프셋을 별도로 입력해야 합니다.

독립 JSON 템플릿은 `examples/graphs/isaacsim_fanuc_m710ic20l_graph.json`에 있습니다.
