# FANUC LS → OMY3M 리타게팅 템플릿

그래프 템플릿 목록에서 `FANUC LS → OMY3M Retarget`을 선택합니다.

1. `FANUC LS 파일 업로드` 노드에서 `.LS` 파일을 업로드합니다.
2. `FANUC LS 파싱` 노드가 `/MN` 모션 명령과 `/POS` 위치를 읽습니다.
3. `FANUC → OMY3M 리타게팅` 노드가 관절 각도를 degree에서 radian으로 변환하고, 직교 좌표를 OMY3M 작업공간 좌표로 정규화한 뒤 수치 IK를 풉니다.
4. `변환 결과 확인`에서 프레임 수, 직접 관절 프레임, IK 필요 프레임을 확인합니다.

현재 전용 템플릿은 Isaac Sim 실행용으로 `previewOnly=false`, `enableExecution=true`, 실행 노드의 `dryRun=false`가 설정되어 있습니다. `requireAllIk=false`이므로 IK에 성공한 관절 프레임만 궤적으로 전송하고 실패한 Cartesian 프레임은 건너뜁니다.

## 현재 지원 범위

- FANUC `J P[...]` 및 `L P[...]` 명령 파싱
- `J1`~`J6` 관절 위치 degree→radian 변환
- `X/Y/Z/W/P/R` 직교 위치의 OMY3M 기준 미리보기 변환
- UF/UT 번호와 속도, FINE/CNT 메타데이터 보존
- 공식 ROBOTIS OMY-3M 링크/관절 모델 기반 damped-least-squares 수치 IK
- IK 실패 수, 위치·자세 오차와 `execution_ready` 출력

실행 안전 게이트는 `previewOnly`, `enableExecution`, `requireAllIk`, 실행 노드의 `dryRun` 네 단계입니다. IK가 모두 풀리지 않으면 `execution_ready=false`가 되어 실행되지 않습니다.

검증이 끝난 뒤에만 리타게팅 노드의 `previewOnly=false`, `enableExecution=true`와 실행 노드의 `dryRun=false`를 설정합니다. 실제 장비 또는 중요한 Isaac Sim 장면에 적용하기 전에는 FANUC `UF`/`UT`와 OMY3M 베이스·툴 좌표를 현장에서 측정하고 충돌 검사를 수행해야 합니다.

Windows의 `E:\로봇os\S05PROC.LS` 경로는 Docker 컨테이너에서 직접 보이지 않을 수 있으므로, 그래프의 업로드 노드를 이용하는 방식이 권장됩니다.
