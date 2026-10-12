using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using System.Text;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using StarterAssets;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif
using WebSocketSharp;
using WebSocketSharp.Server;
using ClientWebSocket = System.Net.WebSockets.ClientWebSocket;
using NetWebSocketCloseStatus = System.Net.WebSockets.WebSocketCloseStatus;
using NetWebSocketMessageType = System.Net.WebSockets.WebSocketMessageType;
using NetWebSocketState = System.Net.WebSockets.WebSocketState;

// 백엔드 또는 직접 VLA 클라이언트가 Unity에 전달하는 로봇 액션 본문입니다.
// 이 클래스의 public field는 JsonUtility 직렬화/역직렬화 대상입니다.
[Serializable]
public class HumanoidBridgeRobotAction
{
    // OpenVLA/백엔드가 Unity로 보내는 "로봇 동작 payload"입니다.
    // Unity의 JsonUtility는 public field 이름을 JSON 키로 그대로 사용하므로,
    // 여기의 변수명은 backend/executors/vla_nodes.py에서 만드는 action 키와 맞아야 합니다.
    //
    // 모든 명령이 모든 필드를 쓰지는 않습니다. command 값에 따라 필요한 필드만 채워지고,
    // 비어 있는 배열(null 또는 Length == 0)은 아래 처리 함수에서 기본값으로 대체됩니다.

    // apply_action 계열의 기본 위치 이동량입니다.
    // 보통 [x, y, z] 순서의 3개 float이며, translationScale을 곱해 적용됩니다.
    // translationSpace가 World이면 월드 좌표 기준, Self이면 로봇 로컬 좌표 기준으로 해석됩니다.
    public float[] translation;

    // apply_action 계열의 기본 회전 이동량입니다.
    // 보통 [x, y, z] 오일러 각도 형식이며, 현재 구현에서는 주로 y축 yaw 회전에 사용됩니다.
    // rotationScale을 곱해 적용됩니다.
    public float[] rotation;

    // apply_joint_targets 명령에서 쓰는 관절 목표 위치 배열입니다.
    // articulatedJoints 순서 또는 대상 오브젝트 하위 ArticulationBody 탐색 순서와 같은 인덱스로 매칭됩니다.
    // 절대 목표값으로 취급되며 jointCommandScale을 곱해 drive.target에 반영됩니다.
    public float[] joint_targets;

    // joint_targets와 같은 의미의 별칭 입력입니다.
    // 백엔드/모델이 joint_positions라는 이름으로 절대 관절 위치를 줄 때 fallback으로 사용됩니다.
    public float[] joint_positions;

    // apply_joint_deltas 명령에서 쓰는 관절 상대 변화량 배열입니다.
    // 각 관절의 현재 drive.target에 delta를 더해 새 목표값을 만듭니다.
    public float[] joint_deltas;

    // apply_joint_velocities 명령에서 쓰는 관절 속도 배열입니다.
    // 각 관절의 xDrive.targetVelocity에 반영됩니다.
    public float[] joint_velocities;

    // apply_base_velocity 명령에서 쓰는 선형 속도 벡터입니다.
    // 값이 있으면 linear_x/linear_z보다 우선하며, [x, y, z] 중 x와 z가 이동에 사용됩니다.
    public float[] linear;

    // apply_base_velocity 명령에서 쓰는 각속도 벡터입니다.
    // 값이 있으면 angular_yaw보다 우선하며, [x, y, z] 중 y가 yaw 회전에 사용됩니다.
    public float[] angular;

    // apply_base_waypoint 명령에서 쓰는 목표 위치입니다.
    // 값이 없으면 translation을 waypoint 위치로 대신 사용합니다.
    // NavMeshAgent가 있으면 이 위치를 목적지로 설정하고, 없으면 Transform을 직접 이동합니다.
    public float[] target_position;

    // apply_base_waypoint 명령에서 쓰는 목표 회전입니다.
    // 값이 없으면 rotation을 waypoint 회전으로 대신 사용합니다.
    public float[] target_rotation;

    // 그리퍼 상태 명령입니다.
    // "open"/"opened"이면 gripperOpen=true, "close"/"closed"이면 gripperOpen=false로 갱신합니다.
    // 휴머노이드처럼 실제 그리퍼가 없는 프로필에서도 상태 메시지에 gripper_open으로 남습니다.
    public string gripper;

    // apply_base_velocity 명령의 스칼라 선형 x 속도입니다.
    // linear 배열이 비어 있을 때 fallback으로 사용됩니다.
    public float linear_x;

    // apply_base_velocity 명령의 스칼라 선형 z 속도입니다.
    // Unity의 일반적인 지면 이동에서 전후 이동축으로 사용됩니다.
    public float linear_z;

    // apply_base_velocity 명령의 스칼라 yaw 각속도입니다.
    // angular 배열이 비어 있을 때 y축 회전값으로 사용됩니다.
    public float angular_yaw;

    // apply_humanoid_step 명령의 한 스텝 x 이동량입니다.
    // NavMeshAgent가 있으면 다음 목적지 계산에 쓰이고, 없으면 Transform 이동에 쓰입니다.
    public float move_x;

    // apply_humanoid_step 명령의 한 스텝 z 이동량입니다.
    // 휴머노이드/캐릭터형 로봇의 평면 이동에서 주로 사용됩니다.
    public float move_z;

    // apply_humanoid_step 명령의 한 스텝 yaw 회전량입니다.
    // applyRotationDelta가 true일 때 Transform에 y축 회전 delta로 적용됩니다.
    public float turn_yaw;

    // 이동 속도입니다.
    // NavMeshAgent가 있을 때 agent.speed에 반영되며, 0 이하 값은 내부에서 최소 속도로 보정됩니다.
    public float speed;

    // 현재 이동을 멈추라는 신호입니다.
    // apply_base_velocity/apply_base_waypoint/apply_humanoid_step에서 정지 요청으로 처리됩니다.
    // stopOnTerminate가 true이면 robot_command 처리에서도 NavMeshAgent 정지에 사용됩니다.
    public bool stop;

    // 그래프 런타임을 끝내도 된다는 상위 레벨 종료 신호입니다.
    // Unity 쪽에서는 stopOnTerminate가 true일 때 현재 이동을 멈추는 데도 사용되고,
    // 백엔드 런타임은 robot_execute 결과의 terminate를 보고 반복 세션 종료 여부를 판단합니다.
    public bool terminate;

    // 액션의 의미를 설명하는 선택적 메타데이터입니다.
    // 예: "safe_action", "decoded_action", "raw_action" 등. 현재 Unity 적용 로직에는 직접적인 분기 조건으로 쓰지 않습니다.
    public string type;

    // ThirdPersonController 자율 순찰 제어 명령입니다.
    // apply_patrol_control 명령에서 "enable", "disable", "internal", "target", "direction" 중 하나를 사용합니다.
    public string patrol_mode;

    // patrol_mode="target"일 때 월드 좌표 목표점입니다. 비어 있으면 target_position을 fallback으로 씁니다.
    public float[] patrol_target_position;

    // patrol_mode="direction"일 때 월드 기준 이동 방향입니다. 비어 있으면 linear/translation을 fallback으로 씁니다.
    public float[] patrol_direction;

    // 0보다 크면 ThirdPersonController.AutonomousPatrolSpeed에 반영합니다.
    public float patrol_speed;
}

// 백엔드 graph runtime의 robot_execute 노드가 Unity WebSocket 서버로 보내는 명령 요청입니다.
// type/request_id/scene/object/command는 요청 메타데이터이고, action이 실제 로봇 제어값입니다.
[Serializable]
public class HumanoidBridgeRobotCommandRequest
{
    public string type;
    public string request_id;
    public string scene;
    public string @object;
    public string command;
    public string robot_type;
    public string controller_mode;
    public HumanoidBridgeRobotAction action;
}

// Unity가 robot_command를 처리한 직후 백엔드로 돌려주는 ACK 응답입니다.
// applied가 true이면 Unity 쪽에서 명령을 실제로 반영했다는 뜻입니다.
[Serializable]
public class HumanoidBridgeRobotAckResponse
{
    public bool ok;
    public string type = "robot_ack";
    public string request_id;
    public bool applied;
    public string message;
    public string error;
    public string scene;
    public string target;
    public string command;
}

// Unity가 백엔드로 보내는 최신 로봇 상태 스냅샷입니다.
// command 처리 후 응답으로도 보내고, state websocket으로 주기 전송할 때도 같은 형식을 씁니다.
[Serializable]
public class HumanoidBridgeRobotState
{
    public string type = "robot_state";
    public string request_id;
    public string scene;
    public string object_name;
    public string client_id;
    public string robot_type;
    public string controller_mode;
    public float[] position;
    public float[] rotation;
    public float[] velocity;
    public float[] joint_positions;
    public bool gripper_open;
    public float[] eef_pose;
    public float[] goal_position;
    public float distance_to_goal;
    public bool has_line_of_sight;
    public bool stuck;
    public float timestamp;
    public string source = "unity_humanoid_bridge";
}

// 직접 VLA 클라이언트 모드에서 모델에 전달하는 에이전트 현재 상태입니다.

[Serializable]
public class HumanoidBridgeImageFrame
{
    public string type = "image_frame";
    public string client_id;
    public string scene;
    public string object_name;
    public string source = "unity_rawimage";
    public string content_type = "image/jpeg";
    public int width;
    public int height;
    public float timestamp;
    public string image;
}

[Serializable]
public class HumanoidBridgeLidarFrame
{
    public string type = "lidar_frame";
    public string client_id;
    public string scene;
    public string object_name;
    public string source = "unity_lidar_raycast";
    public string frame_id;
    public float[] origin;
    public float[] rotation;
    public float[] forward;
    public int range_count;
    public float angle_min;
    public float angle_max;
    public float angle_increment;
    public float range_min;
    public float range_max;
    public float min_range;
    public float max_observed_range;
    public float timestamp;
    public float[] ranges;
    public float[] points_flat;
    public string[] hit_names;
}

[Serializable]
public class HumanoidBridgeAgentState
{
    public float[] position;
    public float[] forward;
    public float[] velocity;
}

// 직접 VLA 클라이언트 모드에서 모델에 전달하는 목표 위치입니다.
[Serializable]
public class HumanoidBridgeGoalState
{
    public float[] position;
}

// 직접 VLA 클라이언트 모드에서 모델에 전달하는 간단한 시뮬레이션 진단값입니다.
[Serializable]
public class HumanoidBridgeSimulationState
{
    public float distance_to_goal;
    public bool has_line_of_sight;
    public bool stuck;
}

// Unity가 VLA WebSocket 서버에 직접 추론을 요청할 때 보내는 payload입니다.
// 일반 graph runtime 경로를 거치지 않고 Unity가 관측값을 모아 모델에 질의할 때 사용합니다.
[Serializable]
public class HumanoidBridgeInferRequest
{
    public string type = "infer_request";
    public string request_id;
    public string instruction;
    public string image_b64;
    public HumanoidBridgeAgentState agent_state;
    public HumanoidBridgeGoalState goal;
    public HumanoidBridgeSimulationState simulation;
}

// 직접 VLA 클라이언트 모드에서 VLA 응답으로 받는 단순 휴머노이드 이동 액션입니다.
// move_x/move_z/speed/stop 중심의 경량 명령이며 ApplyVlaAction에서 처리합니다.
[Serializable]
public class HumanoidBridgeVlaAction
{
    public string type;
    public string command;
    public float[] translation;
    public float[] rotation;
    public float[] target_position;
    public float[] target_rotation;
    public string gripper;
    public float move_x;
    public float move_z;
    public float speed;
    public bool stop;
    public bool terminate;
}

// 직접 VLA 클라이언트가 받는 추론 응답입니다.
// request_id로 요청과 응답을 느슨하게 매칭하고, action이 null이면 실패로 처리합니다.
[Serializable]
public class HumanoidBridgeInferResponse
{
    public string type = "infer_response";
    public string request_id;
    public HumanoidBridgeVlaAction action;
    public string message;
    public string error;
}

// 직접 VLA 클라이언트가 모델 서버로 다시 보내는 적용 결과 ACK입니다.
[Serializable]
public class HumanoidBridgeVlaAckResponse
{
    public bool ok;
    public string type = "robot_ack";
    public string request_id;
    public bool applied;
    public string message;
    public string error;
    public string command;
}

// WebSocket 요청 하나를 처리한 결과를 묶어 반환하는 내부 결과 객체입니다.
// ACK는 항상 보내고, state는 설정에 따라 추가 전송합니다.
public class HumanoidBridgeProcessResult
{
    public HumanoidBridgeRobotAckResponse ack;
    public HumanoidBridgeRobotState state;
}

// Unity 씬 안에서 백엔드와 휴머노이드/로봇 GameObject 사이를 이어주는 핵심 브리지입니다.
// 1) 백엔드가 보내는 robot_command를 WebSocket 서버로 받고,
// 2) Unity 오브젝트/NavMeshAgent/ArticulationBody에 명령을 적용하고,
// 3) ACK와 로봇 상태를 다시 백엔드로 전송합니다.
public class UnityHumanoidRobotBridge : MonoBehaviour
{
    public enum TranslationSpace
    {
        World,
        Self,
    }

    [Header("Server")]
    public int port = 9081;
    public string routePath = "/robot";
    public string defaultTargetObject = "RobotKyle";
    public bool requireSceneMatch = false;
    public string unityRobotType = "generic";
    public string unityControllerMode = "task";

    [Header("Articulated Robot")]
    public ArticulationBody[] articulatedJoints;
    public float jointCommandScale = 1.0f;

    [Header("Humanoid Control")]
    public NavMeshAgent agent;
    public Transform controlledTransform;
    public bool preferNavMeshAgent = true;
    public TranslationSpace translationSpace = TranslationSpace.World;
    public float translationScale = 1.0f;
    public float rotationScale = 1.0f;
    public float minTranslationMagnitude = 0.001f;
    public float navSampleRadius = 2.0f;
    public bool applyRotationDelta = true;
    public bool stopOnTerminate = true;
    public bool gripperOpen = true;

    [Header("Direct VLA Client")]
    public bool enableDirectVlaClient = false;
    public string vlaWsUrl = "ws://localhost:9060/infer";
    public float vlaRequestInterval = 0.5f;
    public float vlaReconnectIntervalSec = 2.0f;
    public float vlaStepScale = 2.0f;
    public float vlaMinMoveMagnitude = 0.05f;

    [TextArea(2, 4)]
    public string vlaInstruction = "Go to the goal safely";

    public Transform goal;
    public Camera simCamera;
    public bool includeCameraImage = false;
    public int cameraCaptureWidth = 384;
    public int cameraCaptureHeight = 384;
    [Range(1, 100)]
    public int cameraJpegQuality = 75;
    public float stuckVelocityThreshold = 0.05f;
    public float stuckDistanceThreshold = 1.0f;

    [Header("Unity State WebSocket")]
    public bool sendStateContinuously = true;
    public bool sendStateAfterCommand = true;
    public string backendBaseUrl = "http://localhost:9000";
    public string stateClientId = "default";
    public float stateSendIntervalSec = 0.1f;
    public float stateReconnectIntervalSec = 2.0f;

    [Header("Runtime Compatibility")]
    public bool autoRewriteLegacyPorts = true;
    public bool autoEnableStateStreaming = true;
    public bool autoEnableImageStreaming = true;
    public bool autoEnableLidarStreaming = true;

    [Header("Unity Image WebSocket")]
    public bool sendImageContinuously = true;
    public RawImage imageSourceRawImage;
    public bool autoUseMainCameraForImage = true;
    public string imageClientId = "default";
    public float imageSendIntervalSec = 0.2f;
    public float imageReconnectIntervalSec = 2.0f;

    [Header("Unity LiDAR WebSocket")]
    public bool sendLidarContinuously = true;
    public bool sendLidarAfterCommand = true;
    public bool showLidarHitOverlay = true;
    public bool updateLidarOverlayWithoutBackend = true;
    public Transform lidarOrigin;
    public bool autoCreateVirtualLidar = true;
    public string virtualLidarObjectName = "VirtualLiDAR";
    public Vector3 virtualLidarLocalPosition = new Vector3(0.0f, 1.2f, 0.15f);
    public Vector3 virtualLidarLocalEulerAngles = Vector3.zero;
    public string lidarClientId = "default";
    public string lidarFrameId = "humanoid_lidar";
    public int lidarRayCount = 181;
    public float lidarHorizontalFovDeg = 180.0f;
    public float lidarMinRange = 0.05f;
    public float lidarMaxRange = 12.0f;
    public float lidarHeightOffset = 1.2f;
    public float lidarPitchDeg = 0.0f;
    public LayerMask lidarLayerMask = ~0;
    public bool lidarIgnoreTriggers = true;
    public bool lidarDrawDebugRays = false;
    public float lidarSendIntervalSec = 0.1f;
    public float lidarReconnectIntervalSec = 2.0f;
    public float lidarOverlayUpdateIntervalSec = 0.1f;
    [Range(1, 32)]
    public int maxLidarOverlayHitObjects = 8;

    [Header("Idle Patrol")]
    public bool enableIdlePatrol = true;
    public string idlePatrolTargetObject = "";
    public float idlePatrolDelaySec = 30.0f;
    public float idlePatrolSpeed = 2.0f;
    public bool idlePatrolUseInternalMode = true;
    public bool stopIdlePatrolOnNewCommand = true;
    public bool stopIdlePatrolOnPlayerInput = true;
    public bool keepPlayerInputEnabledDuringIdlePatrol = true;
    public bool idlePatrolRequiresStoppedMotion = true;
    public float idlePatrolStoppedVelocityThreshold = 0.05f;
    public float idlePatrolMaxStoppedMotionWaitSec = 3.0f;
    public float idlePatrolRetryIntervalSec = 2.0f;
    public float playerMoveInputThreshold = 0.05f;
    public bool playerLookInputCountsAsActivity = false;
    public float playerLookInputThreshold = 0.2f;

    [Header("Idle Patrol Debug")]
    public bool idlePatrolActive = false;
    public float idleSecondsSinceLastCommand = 0.0f;

    [TextArea(2, 4)]
    public string idlePatrolSummary = "Idle patrol waiting for command inactivity.";

    [TextArea(2, 4)]
    public string lastPlayerInputSummary = "No player input yet.";

    [Header("Command Monitor")]
    public bool showCommandOverlay = true;
    public int maxCommandHistory = 8;
    public int receivedCommandCount = 0;

    [TextArea(2, 4)]
    public string lastCommandSummary = "Waiting for command...";

    [TextArea(3, 8)]
    public string lastReceivedRawJson = "";

    [TextArea(2, 4)]
    public string lastAckSummary = "";

    [TextArea(2, 4)]
    public string lastStateSummary = "";

    [TextArea(2, 4)]
    public string lastImageSummary = "No image frame sent yet.";

    [TextArea(2, 4)]
    public string lastVlaRequestSummary = "No VLA request sent yet.";

    [TextArea(2, 4)]
    public string lastVlaResponseSummary = "No VLA response yet.";

    [TextArea(2, 4)]
    public string lastVlaAckSummary = "No VLA ACK sent yet.";

    [TextArea(2, 4)]
    public string lastLidarSummary = "No LiDAR frame sent yet.";

    [TextArea(3, 8)]
    public string lastLidarHitSummary = "No LiDAR hits yet.";

    [TextArea(3, 8)]
    public string lastVlaRawJson = "";

    [TextArea(6, 16)]
    public string recentCommandLog = "";

    private WebSocketServer _server;
    private WebSocket _stateSocket;
    private ClientWebSocket _imageSocket;
    private WebSocket _lidarSocket;
    private WebSocket _vlaSocket;
    private float _nextStateSendAt = 0f;
    private float _nextReconnectAt = 0f;
    private float _nextImageSendAt = 0f;
    private float _nextImageReconnectAt = 0f;
    private float _nextImageNotReadyLogAt = 0f;
    private float _nextLidarSendAt = 0f;
    private float _nextLidarReconnectAt = 0f;
    private float _nextLidarOverlayAt = 0f;
    private float _lastCommandActivityAt = -1f;
    private float _nextIdlePatrolAttemptAt = 0f;
    private float _idlePatrolStoppedMotionWaitStartedAt = -1f;
    private bool _playerInputWasActive = false;
    private bool _hasIdlePatrolInputModeSnapshot = false;
    private bool _idlePatrolDefaultDisablePlayerInputDuringPatrol = true;
    private ThirdPersonController _idlePatrolController;
    private string _imageSocketCloseContext = "";
    private string _imageSocketUrl = "";
    private CancellationTokenSource _imageSocketCts;
    private Task _imageReceiveTask;
    private bool _isImageConnecting = false;
    private bool _isImageSending = false;
    private float _nextVlaRequestAt = 0f;
    private float _nextVlaReconnectAt = 0f;
    private bool _isVlaConnected = false;
    private bool _isVlaRequesting = false;
    private string _lastVlaRequestId = "";
    private int _vlaRequestSeq = 0;
    private string _activeRobotType = "generic";
    private string _activeControllerMode = "task";

    private static readonly Queue<Action> MainThreadQueue = new Queue<Action>();
    private readonly Queue<string> _recentEvents = new Queue<string>();
    private static int _mainThreadManagedThreadId = -1;
    private static UnityHumanoidRobotBridge _instance;

    private GUIStyle _overlayBoxStyle;
    private GUIStyle _overlayTitleStyle;
    private GUIStyle _overlayTextStyle;
    private Vector2 _logScrollPos = Vector2.zero;

    // Unity 오브젝트가 생성될 때 전역 인스턴스와 메인 스레드 ID를 기록합니다.
    // WebSocket 콜백은 별도 스레드에서 들어올 수 있으므로, 이후 메인 스레드 판별에 사용합니다.
    private void Awake()
    {
        _instance = this;
        _mainThreadManagedThreadId = Thread.CurrentThread.ManagedThreadId;
        NormalizeLegacyInspectorSettings();
    }

    // 씬 시작 시 제어 대상, 로봇 프로필, WebSocket 서버/클라이언트 연결을 초기화합니다.
    private void Start()
    {
        NormalizeLegacyInspectorSettings();

        if (agent == null)
        {
            agent = GetComponent<NavMeshAgent>();
        }

        if (controlledTransform == null)
        {
            controlledTransform = agent != null ? agent.transform : transform;
        }

        if (autoCreateVirtualLidar && (sendLidarContinuously || sendLidarAfterCommand))
        {
            EnsureVirtualLidarOrigin(false);
        }

        if (autoUseMainCameraForImage)
        {
            EnsureImageCamera();
        }

        _activeRobotType = ResolveConfiguredRobotType();
        _activeControllerMode = ResolveConfiguredControllerMode();
        _lastCommandActivityAt = Time.realtimeSinceStartup;
        idlePatrolSummary = enableIdlePatrol
            ? $"Waiting {Mathf.Max(0.1f, idlePatrolDelaySec):0.0}s before idle patrol."
            : "Idle patrol disabled.";

        StartServer();

        if (autoEnableStateStreaming)
        {
            sendStateContinuously = true;
        }

        if (autoEnableImageStreaming)
        {
            sendImageContinuously = true;
        }

        if (autoEnableLidarStreaming)
        {
            sendLidarContinuously = true;
        }

        if (sendStateContinuously)
        {
            ConnectStateSocket();
        }

        if (sendImageContinuously)
        {
            ConnectImageSocket();
        }

        if (sendLidarContinuously || sendLidarAfterCommand || showLidarHitOverlay)
        {
            ConnectLidarSocket();
        }

        if (enableDirectVlaClient)
        {
            ConnectVlaSocket();
        }
    }

    // 매 프레임 메인 스레드 큐를 비우고, 옵션에 따라 상태 전송/VLA 직접 요청 루프를 돌립니다.
    private void Update()
    {
        lock (MainThreadQueue)
        {
            while (MainThreadQueue.Count > 0)
            {
                var action = MainThreadQueue.Dequeue();
                action?.Invoke();
            }
        }

        if (sendStateContinuously)
        {
            UpdateStateSocketLoop();
        }

        if (sendImageContinuously)
        {
            UpdateImageSocketLoop();
        }

        if (sendLidarContinuously)
        {
            UpdateLidarSocketLoop();
        }

        if (showLidarHitOverlay && updateLidarOverlayWithoutBackend)
        {
            UpdateLidarHitOverlayLoop();
        }

        if (enableDirectVlaClient)
        {
            UpdateVlaClientLoop();
        }

        UpdatePlayerInputPriorityLoop();
        UpdateIdlePatrolLoop();
    }

    // 컴포넌트가 제거될 때 열린 WebSocket 리소스를 정리합니다.
    private void OnDestroy()
    {
        Shutdown();
    }

    // 앱 종료 시점에도 서버와 소켓을 안전하게 닫습니다.
    private void OnApplicationQuit()
    {
        Shutdown();
    }

    // WebSocketSharp 콜백처럼 메인 스레드가 아닌 곳에서 Unity API를 호출해야 할 때 작업을 예약합니다.
    public static void EnqueueOnMainThread(Action action)
    {
        lock (MainThreadQueue)
        {
            MainThreadQueue.Enqueue(action);
        }
    }

    // 현재 호출 위치가 Unity 메인 스레드인지 확인합니다.
    public static bool IsOnMainThread()
    {
        return Thread.CurrentThread.ManagedThreadId == _mainThreadManagedThreadId;
    }

    // 백엔드 robot_execute 노드가 접속할 Unity WebSocket 서버를 시작합니다.
    // routePath 예: /robot -> ws://<unity-host>:9081/robot
    private void StartServer()
    {
        try
        {
            var normalizedRoute = NormalizeRoutePath(routePath);

            _server = new WebSocketServer(port);
            _server.AddWebSocketService<HumanoidRobotWsBehavior>(normalizedRoute);
            HumanoidRobotWsBehavior.Enqueue = EnqueueOnMainThread;
            HumanoidRobotWsBehavior.ProcessRequest = ProcessIncomingRequest;
            HumanoidRobotWsBehavior.RecordIncoming = RecordIncomingCommand;
            HumanoidRobotWsBehavior.RecordOutcome = RecordCommandOutcome;
            HumanoidRobotWsBehavior.RecordState = RecordStateMessage;
            HumanoidRobotWsBehavior.RecordNotice = RecordNotice;
            _server.Start();

            AppendRecentEvent($"Server started on ws://0.0.0.0:{port}{normalizedRoute}");
        }
        catch (Exception ex)
        {
            Debug.LogError($"[UnityHumanoidBridge] Server start failed: {ex.Message}");
            AppendRecentEvent($"Server start failed: {ex.Message}");
        }
    }

    // 서버, 상태 전송 소켓, 직접 VLA 소켓을 모두 닫고 static 콜백 참조를 해제합니다.
    private void Shutdown()
    {
        if (_server != null)
        {
            try
            {
                _server.Stop();
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[UnityHumanoidBridge] Server stop warning: {ex.Message}");
            }
            _server = null;
        }

        if (_stateSocket != null)
        {
            try
            {
                _stateSocket.Close();
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[UnityHumanoidBridge] State socket close warning: {ex.Message}");
            }
            _stateSocket = null;
        }

        if (_imageSocket != null)
        {
            try
            {
                CloseImageSocket("shutdown");
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[UnityHumanoidBridge] Image socket close warning: {ex.Message}");
            }
        }

        if (_lidarSocket != null)
        {
            try
            {
                _lidarSocket.Close();
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[UnityHumanoidBridge] LiDAR socket close warning: {ex.Message}");
            }
            _lidarSocket = null;
        }

        if (_vlaSocket != null)
        {
            try
            {
                _vlaSocket.Close();
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[UnityHumanoidBridge] VLA socket close warning: {ex.Message}");
            }
            _vlaSocket = null;
        }

        _isVlaConnected = false;
        _isVlaRequesting = false;

        if (_instance == this)
        {
            _instance = null;
        }

        HumanoidRobotWsBehavior.Enqueue = null;
        HumanoidRobotWsBehavior.ProcessRequest = null;
        HumanoidRobotWsBehavior.RecordIncoming = null;
        HumanoidRobotWsBehavior.RecordOutcome = null;
        HumanoidRobotWsBehavior.RecordState = null;
        HumanoidRobotWsBehavior.RecordNotice = null;
    }

    // 백엔드 상태 수집 WebSocket에 연결되어 있는지 확인하고, 주기적으로 로봇 상태를 보냅니다.
    private void UpdateStateSocketLoop()
    {
        if (!IsStateSocketActive())
        {
            if (Time.unscaledTime >= _nextReconnectAt)
            {
                _nextReconnectAt = Time.unscaledTime + Mathf.Max(0.5f, stateReconnectIntervalSec);
                ConnectStateSocket();
            }

            return;
        }

        if (Time.unscaledTime < _nextStateSendAt)
        {
            return;
        }

        _nextStateSendAt = Time.unscaledTime + Mathf.Max(0.02f, stateSendIntervalSec);
        SendStateOnce();
    }

    // Existing scene components may still hold serialized Inspector values from the old port layout.
    // Normalize them at runtime so old scenes keep working after the backend moved to 9xxx ports.
    private void NormalizeLegacyInspectorSettings()
    {
        if (autoEnableStateStreaming)
        {
            sendStateContinuously = true;
        }

        if (autoEnableImageStreaming)
        {
            sendImageContinuously = true;
        }

        if (autoEnableLidarStreaming)
        {
            sendLidarContinuously = true;
        }

        if (!autoRewriteLegacyPorts)
        {
            return;
        }

        if (port == 8081)
        {
            port = 9081;
        }

        backendBaseUrl = RewriteLegacyPortText(backendBaseUrl);
        vlaWsUrl = RewriteLegacyPortText(vlaWsUrl);
    }

    private static string RewriteLegacyPortText(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return value;
        }

        return value
            .Replace(":8000", ":9000")
            .Replace(":8040", ":9040")
            .Replace(":8060", ":9060")
            .Replace(":8061", ":9061")
            .Replace(":8081", ":9081")
            .Replace(":8090", ":9090")
            .Replace(":8091", ":9091")
            .Replace(":8092", ":9092")
            .Replace(":8899", ":9899")
            .Replace(":5173", ":9173");
    }

    // Check the image websocket and periodically send the latest RawImage or camera frame.
    private void UpdateImageSocketLoop()
    {
        if (!IsImageSocketActive())
        {
            if (Time.unscaledTime >= _nextImageReconnectAt)
            {
                _nextImageReconnectAt = Time.unscaledTime + Mathf.Max(0.5f, imageReconnectIntervalSec);
                ConnectImageSocket();
            }

            return;
        }

        if (Time.unscaledTime < _nextImageSendAt)
        {
            return;
        }

        _nextImageSendAt = Time.unscaledTime + Mathf.Max(0.02f, imageSendIntervalSec);
        SendImageOnce();
    }

    // Check the LiDAR websocket and periodically send the latest raycast scan.
    private void UpdateLidarSocketLoop()
    {
        if (!IsLidarSocketActive())
        {
            if (Time.unscaledTime >= _nextLidarReconnectAt)
            {
                _nextLidarReconnectAt = Time.unscaledTime + Mathf.Max(0.5f, lidarReconnectIntervalSec);
                ConnectLidarSocket();
            }

            return;
        }

        if (Time.unscaledTime < _nextLidarSendAt)
        {
            return;
        }

        _nextLidarSendAt = Time.unscaledTime + Mathf.Max(0.02f, lidarSendIntervalSec);
        SendLidarOnce();
    }

    // Keep the on-screen LiDAR hit list fresh even when the backend websocket is not connected.
    private void UpdateLidarHitOverlayLoop()
    {
        if (Time.unscaledTime < _nextLidarOverlayAt)
        {
            return;
        }

        _nextLidarOverlayAt = Time.unscaledTime + Mathf.Max(0.02f, lidarOverlayUpdateIntervalSec);

        var frame = BuildLidarFrameMessage(ResolveActiveTargetName(), SceneManager.GetActiveScene().name);
        if (frame == null)
        {
            lastLidarHitSummary = "LiDAR origin is not ready.";
            return;
        }

        UpdateLidarSummaries(frame);
    }

    // Unity가 직접 VLA 서버에 관측값을 보내는 모드의 주기 루프입니다.
    // 요청이 이미 진행 중이면 중복 요청을 보내지 않습니다.
    private void UpdateVlaClientLoop()
    {
        if (!IsVlaSocketActive())
        {
            if (Time.unscaledTime >= _nextVlaReconnectAt)
            {
                _nextVlaReconnectAt = Time.unscaledTime + Mathf.Max(0.5f, vlaReconnectIntervalSec);
                ConnectVlaSocket();
            }

            return;
        }

        if (_isVlaRequesting || Time.unscaledTime < _nextVlaRequestAt)
        {
            return;
        }

        _nextVlaRequestAt = Time.unscaledTime + Mathf.Max(0.05f, vlaRequestInterval);
        SendVlaInferRequest();
    }

    // backendBaseUrl을 기반으로 /ws/unity/state에 연결합니다.
    // 이 연결은 백엔드 runtime이 기다리는 Unity state store를 계속 갱신합니다.
    private void ConnectStateSocket()
    {
        var url = BuildStateWebSocketUrl();

        try
        {
            if (_stateSocket != null)
            {
                var readyState = _stateSocket.ReadyState;
                var currentUrl = _stateSocket.Url != null ? _stateSocket.Url.ToString() : "";
                if (string.Equals(currentUrl, url, StringComparison.OrdinalIgnoreCase) &&
                    (readyState == WebSocketState.Open || readyState == WebSocketState.Connecting))
                {
                    return;
                }

                _stateSocket.Close();
            }

            _stateSocket = new WebSocket(url);
            _stateSocket.OnOpen += (_, __) =>
            {
                EnqueueOnMainThread(() =>
                {
                    _nextStateSendAt = 0f;
                    AppendRecentEvent($"State WS connected -> {url}");
                });
            };
            _stateSocket.OnMessage += (_, messageEvent) =>
            {
                var payload = messageEvent.Data;
                EnqueueOnMainThread(() =>
                {
                    if (!string.IsNullOrWhiteSpace(payload) &&
                        payload.IndexOf("\"ok\":false", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        AppendRecentEvent($"State ACK -> {TrimForLog(payload)}");
                    }
                });
            };
            _stateSocket.OnError += (_, e) =>
            {
                EnqueueOnMainThread(() =>
                {
                    AppendRecentEvent($"State WS error: {e.Message}");
                });
            };
            _stateSocket.OnClose += (_, __) =>
            {
                EnqueueOnMainThread(() =>
                {
                    AppendRecentEvent("State WS closed");
                });
            };
            _stateSocket.ConnectAsync();
        }
        catch (Exception ex)
        {
            Debug.LogError($"[UnityHumanoidBridge] State WS connect failed: {ex.Message}");
            AppendRecentEvent($"State WS connect failed: {ex.Message}");
        }
    }

    [ContextMenu("Enable Unity State Streaming")]
    public void EnableUnityStateStreaming()
    {
        sendStateContinuously = true;
        ConnectStateSocket();
        AppendRecentEvent($"State streaming enabled for client_id={stateClientId}");
    }

    [ContextMenu("Enable Unity Image Streaming")]
    public void EnableUnityImageStreaming()
    {
        sendImageContinuously = true;
        EnsureImageCamera();
        ConnectImageSocket();
        AppendRecentEvent($"Image streaming enabled for client_id={imageClientId}");
    }

    [ContextMenu("Enable Unity LiDAR Streaming")]
    public void EnableUnityLidarStreaming()
    {
        sendLidarContinuously = true;
        EnsureVirtualLidarOrigin(false);
        ConnectLidarSocket();
        AppendRecentEvent($"LiDAR streaming enabled for client_id={lidarClientId}");
    }

    // Connect to /ws/unity/image on the backend.
    // This forwards the latest RawImage or camera frame into the backend image store.
    private void ConnectImageSocket()
    {
        var url = BuildImageWebSocketUrl();

        if (_imageSocket != null)
        {
            var readyState = _imageSocket.State;
            if (string.Equals(_imageSocketUrl, url, StringComparison.OrdinalIgnoreCase) &&
                (readyState == NetWebSocketState.Open || readyState == NetWebSocketState.Connecting))
            {
                return;
            }

            CloseImageSocket("reconnect");
        }

        var socket = new ClientWebSocket();
        socket.Options.KeepAliveInterval = TimeSpan.FromSeconds(20.0);
        var cts = new CancellationTokenSource();

        _imageSocket = socket;
        _imageSocketCts = cts;
        _imageSocketUrl = url;
        _isImageConnecting = true;
        _isImageSending = false;

        Task.Run(async () =>
        {
            try
            {
                await socket.ConnectAsync(new Uri(url), cts.Token);
                EnqueueOnMainThread(() =>
                {
                    if (!ReferenceEquals(_imageSocket, socket))
                    {
                        return;
                    }

                    _isImageConnecting = false;
                    _nextImageSendAt = 0f;
                    AppendRecentEvent($"Image WS connected -> {url}");
                    SendImageOnce();
                });

                _imageReceiveTask = ReceiveImageSocketLoopAsync(socket, cts.Token);
            }
            catch (OperationCanceledException)
            {
                EnqueueOnMainThread(() =>
                {
                    if (ReferenceEquals(_imageSocket, socket))
                    {
                        _isImageConnecting = false;
                    }
                });
            }
            catch (Exception ex)
            {
                EnqueueOnMainThread(() =>
                {
                    if (ReferenceEquals(_imageSocket, socket))
                    {
                        _isImageConnecting = false;
                        AppendRecentEvent($"Image WS connect failed: {ex.Message}");
                    }
                });

                try
                {
                    socket.Dispose();
                }
                catch
                {
                }

                try
                {
                    cts.Dispose();
                }
                catch
                {
                }
            }
        });
    }

    // Connect to /ws/unity/lidar on the backend.
    // The Remote LiDAR Sensor node can read the latest frame through /api/unity/lidar.
    private void ConnectLidarSocket()
    {
        var url = BuildLidarWebSocketUrl();

        try
        {
            if (_lidarSocket != null)
            {
                var readyState = _lidarSocket.ReadyState;
                var currentUrl = _lidarSocket.Url != null ? _lidarSocket.Url.ToString() : "";
                if (string.Equals(currentUrl, url, StringComparison.OrdinalIgnoreCase) &&
                    (readyState == WebSocketState.Open || readyState == WebSocketState.Connecting))
                {
                    return;
                }

                _lidarSocket.Close();
            }

            _lidarSocket = new WebSocket(url);
            _lidarSocket.OnOpen += (_, __) =>
            {
                EnqueueOnMainThread(() =>
                {
                    _nextLidarSendAt = 0f;
                    AppendRecentEvent($"LiDAR WS connected -> {url}");
                    SendLidarOnce();
                });
            };
            _lidarSocket.OnMessage += (_, messageEvent) =>
            {
                var payload = messageEvent.Data;
                EnqueueOnMainThread(() =>
                {
                    if (!string.IsNullOrWhiteSpace(payload) &&
                        payload.IndexOf("\"ok\":false", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        AppendRecentEvent($"LiDAR ACK -> {TrimForLog(payload)}");
                    }
                });
            };
            _lidarSocket.OnError += (_, e) =>
            {
                EnqueueOnMainThread(() =>
                {
                    AppendRecentEvent($"LiDAR WS error: {e.Message}");
                });
            };
            _lidarSocket.OnClose += (_, __) =>
            {
                EnqueueOnMainThread(() =>
                {
                    AppendRecentEvent("LiDAR WS closed");
                });
            };
            _lidarSocket.ConnectAsync();
        }
        catch (Exception ex)
        {
            Debug.LogError($"[UnityHumanoidBridge] LiDAR WS connect failed: {ex.Message}");
            AppendRecentEvent($"LiDAR WS connect failed: {ex.Message}");
        }
    }

    private void CloseImageSocket(string context)
    {
        _imageSocketCloseContext = context;
        _isImageConnecting = false;
        _isImageSending = false;

        var socket = _imageSocket;
        var cts = _imageSocketCts;
        _imageSocket = null;
        _imageSocketCts = null;
        _imageSocketUrl = "";
        _imageReceiveTask = null;

        if (cts != null)
        {
            try
            {
                cts.Cancel();
            }
            catch
            {
            }
        }

        if (socket == null)
        {
            if (cts != null)
            {
                try
                {
                    cts.Dispose();
                }
                catch
                {
                }
            }
            return;
        }

        Task.Run(async () =>
        {
            try
            {
                if (socket.State == NetWebSocketState.Open ||
                    socket.State == NetWebSocketState.CloseReceived ||
                    socket.State == NetWebSocketState.CloseSent)
                {
                    await socket.CloseAsync(NetWebSocketCloseStatus.NormalClosure, context, CancellationToken.None);
                }
                else
                {
                    socket.Abort();
                }
            }
            catch
            {
                try
                {
                    socket.Abort();
                }
                catch
                {
                }
            }
            finally
            {
                try
                {
                    socket.Dispose();
                }
                catch
                {
                }

                if (cts != null)
                {
                    try
                    {
                        cts.Dispose();
                    }
                    catch
                    {
                    }
                }
            }
        });
    }

    private async Task ReceiveImageSocketLoopAsync(ClientWebSocket socket, CancellationToken token)
    {
        var buffer = new byte[8192];
        using var stream = new MemoryStream();

        try
        {
            while (!token.IsCancellationRequested &&
                   (socket.State == NetWebSocketState.Open || socket.State == NetWebSocketState.CloseSent))
            {
                var result = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), token);
                if (result.MessageType == NetWebSocketMessageType.Close)
                {
                    EnqueueOnMainThread(() =>
                    {
                        var details = $"Image WS closed (status={socket.CloseStatus})";
                        if (!string.IsNullOrWhiteSpace(socket.CloseStatusDescription))
                        {
                            details += $", reason={socket.CloseStatusDescription}";
                        }
                        else if (!string.IsNullOrWhiteSpace(_imageSocketCloseContext))
                        {
                            details += $", context={_imageSocketCloseContext}";
                        }

                        AppendRecentEvent(details);
                        _imageSocketCloseContext = "";
                        if (ReferenceEquals(_imageSocket, socket))
                        {
                            _isImageConnecting = false;
                            _isImageSending = false;
                        }
                    });
                    break;
                }

                if (result.Count > 0)
                {
                    stream.Write(buffer, 0, result.Count);
                }

                if (!result.EndOfMessage)
                {
                    continue;
                }

                if (result.MessageType == NetWebSocketMessageType.Text)
                {
                    var payload = Encoding.UTF8.GetString(stream.ToArray());
                    EnqueueOnMainThread(() =>
                    {
                        if (!string.IsNullOrWhiteSpace(payload) &&
                            payload.IndexOf("\"ok\":false", StringComparison.OrdinalIgnoreCase) >= 0)
                        {
                            AppendRecentEvent($"Image ACK -> {TrimForLog(payload)}");
                        }
                    });
                }

                stream.SetLength(0);
            }
        }
        catch (OperationCanceledException)
        {
        }
        catch (Exception ex)
        {
            EnqueueOnMainThread(() =>
            {
                if (ReferenceEquals(_imageSocket, socket))
                {
                    AppendRecentEvent($"Image WS error: {ex.Message}");
                    _isImageConnecting = false;
                    _isImageSending = false;
                }
            });
        }
        finally
        {
            if (ReferenceEquals(_imageSocket, socket) && socket.State != NetWebSocketState.Open)
            {
                EnqueueOnMainThread(() =>
                {
                    _isImageConnecting = false;
                    _isImageSending = false;
                });
            }
        }
    }

    // Return true while the state websocket is open or still connecting.
    private bool IsStateSocketActive()
    {
        if (_stateSocket == null)
        {
            return false;
        }

        if (_stateSocket.IsAlive)
        {
            return true;
        }

        return _stateSocket.ReadyState == WebSocketState.Open ||
               _stateSocket.ReadyState == WebSocketState.Connecting;
    }


    // Return true while the image websocket is open or still connecting.
    private bool IsImageSocketActive()
    {
        if (_imageSocket == null)
        {
            return false;
        }

        if (_isImageConnecting)
        {
            return true;
        }

        return _imageSocket.State == NetWebSocketState.Open ||
               _imageSocket.State == NetWebSocketState.Connecting;
    }

    // Return true while the LiDAR websocket is open or still connecting.
    private bool IsLidarSocketActive()
    {
        if (_lidarSocket == null)
        {
            return false;
        }

        if (_lidarSocket.IsAlive)
        {
            return true;
        }

        return _lidarSocket.ReadyState == WebSocketState.Open ||
               _lidarSocket.ReadyState == WebSocketState.Connecting;
    }

    // 직접 VLA 서버 WebSocket에 연결합니다.
    // enableDirectVlaClient가 켜져 있을 때 Unity가 backend graph 없이 직접 모델에 질의합니다.
    private void ConnectVlaSocket()
    {
        var url = string.IsNullOrWhiteSpace(vlaWsUrl) ? "ws://localhost:9060/infer" : vlaWsUrl.Trim();

        try
        {
            if (_vlaSocket != null)
            {
                var readyState = _vlaSocket.ReadyState;
                var currentUrl = _vlaSocket.Url != null ? _vlaSocket.Url.ToString() : "";
                if (string.Equals(currentUrl, url, StringComparison.OrdinalIgnoreCase) &&
                    (readyState == WebSocketState.Open || readyState == WebSocketState.Connecting))
                {
                    return;
                }

                _vlaSocket.Close();
            }

            _isVlaConnected = false;
            _isVlaRequesting = false;
            _vlaSocket = new WebSocket(url);
            _vlaSocket.OnOpen += (_, __) =>
            {
                EnqueueOnMainThread(() =>
                {
                    _isVlaConnected = true;
                    _nextVlaRequestAt = 0f;
                    AppendRecentEvent($"VLA WS connected -> {url}");
                });
            };
            _vlaSocket.OnMessage += (_, messageEvent) =>
            {
                var payload = messageEvent.Data;
                EnqueueOnMainThread(() =>
                {
                    lastVlaRawJson = payload ?? "";
                    HandleIncomingVlaMessage(payload);
                });
            };
            _vlaSocket.OnError += (_, e) =>
            {
                EnqueueOnMainThread(() =>
                {
                    _isVlaConnected = false;
                    _isVlaRequesting = false;
                    lastVlaAckSummary = "VLA socket error: " + e.Message;
                    AppendRecentEvent(lastVlaAckSummary);
                });
            };
            _vlaSocket.OnClose += (_, __) =>
            {
                EnqueueOnMainThread(() =>
                {
                    _isVlaConnected = false;
                    _isVlaRequesting = false;
                    AppendRecentEvent("VLA WS closed");
                });
            };
            _vlaSocket.ConnectAsync();
        }
        catch (Exception ex)
        {
            _isVlaConnected = false;
            _isVlaRequesting = false;
            Debug.LogError($"[UnityHumanoidBridge] VLA WS connect failed: {ex.Message}");
            AppendRecentEvent($"VLA WS connect failed: {ex.Message}");
        }
    }

    // 직접 VLA WebSocket이 사용 가능한 상태인지 확인합니다.
    private bool IsVlaSocketActive()
    {
        if (_vlaSocket == null)
        {
            return false;
        }

        if (_vlaSocket.IsAlive)
        {
            return true;
        }

        return _vlaSocket.ReadyState == WebSocketState.Open ||
               _vlaSocket.ReadyState == WebSocketState.Connecting;
    }

    [ContextMenu("Send Unity State Once")]
    // 현재 로봇 상태를 한 번 만들어 백엔드 state websocket으로 전송합니다.
    // Inspector의 ContextMenu에서도 수동 호출할 수 있습니다.
    public void SendStateOnce()
    {
        if (_stateSocket == null || !_stateSocket.IsAlive)
        {
            sendStateContinuously = true;
            ConnectStateSocket();
            AppendRecentEvent("State socket not connected; connecting now");
            return;
        }

        var state = BuildRobotStateMessage("", ResolveActiveTargetName(), SceneManager.GetActiveScene().name);
        if (state == null)
        {
            return;
        }

        var json = JsonUtility.ToJson(state);
        _stateSocket.SendAsync(json, completed =>
        {
            if (!completed)
            {
                AppendRecentEvent("State send not completed");
            }
        });
    }

    [ContextMenu("Send Unity Image Once")]
    // Send one image frame to the backend image websocket.
    public void SendImageOnce()
    {
        if (_imageSocket == null || _imageSocket.State != NetWebSocketState.Open || _isImageSending)
        {
            sendImageContinuously = true;
            EnsureImageCamera();
            ConnectImageSocket();
            AppendRecentEvent("Image socket not connected; connecting now");
            return;
        }

        var frame = BuildImageFrameMessage();
        if (frame == null)
        {
            if (Time.unscaledTime >= _nextImageNotReadyLogAt)
            {
                _nextImageNotReadyLogAt = Time.unscaledTime + 2.0f;
                AppendRecentEvent("Image frame not ready: assign imageSourceRawImage or simCamera/MainCamera");
            }

            return;
        }

        var json = JsonUtility.ToJson(frame);
        var payload = Encoding.UTF8.GetBytes(json);
        var socket = _imageSocket;
        var token = _imageSocketCts != null ? _imageSocketCts.Token : CancellationToken.None;
        _isImageSending = true;

        Task.Run(async () =>
        {
            var sent = false;
            try
            {
                await socket.SendAsync(
                    new ArraySegment<byte>(payload),
                    NetWebSocketMessageType.Text,
                    true,
                    token
                );
                sent = true;
            }
            catch (OperationCanceledException)
            {
            }
            catch (Exception ex)
            {
                EnqueueOnMainThread(() =>
                {
                    if (ReferenceEquals(_imageSocket, socket))
                    {
                        AppendRecentEvent($"Image WS send failed: {ex.Message}");
                    }
                });
            }
            finally
            {
                EnqueueOnMainThread(() =>
                {
                    if (ReferenceEquals(_imageSocket, socket))
                    {
                        if (sent)
                        {
                            var payloadLength = frame.image != null ? frame.image.Length : 0;
                            lastImageSummary =
                                $"client={frame.client_id}, size={frame.width}x{frame.height}, payload={payloadLength}";
                        }

                        _isImageSending = false;
                    }
                });
            }
        });
    }

    [ContextMenu("Send Unity LiDAR Once")]
    // Send one raycast LiDAR scan to the backend LiDAR websocket.
    public void SendLidarOnce()
    {
        SendLidarOnce(ResolveActiveTargetName(), SceneManager.GetActiveScene().name);
    }

    private void SendLidarOnce(string targetName, string sceneName)
    {
        var frame = BuildLidarFrameMessage(targetName, sceneName);
        if (frame == null)
        {
            return;
        }

        UpdateLidarSummaries(frame);

        if (_lidarSocket == null || !_lidarSocket.IsAlive)
        {
            sendLidarContinuously = true;
            EnsureVirtualLidarOrigin(false);
            ConnectLidarSocket();
            AppendRecentEvent("LiDAR socket not connected; connecting now");
            return;
        }

        var json = JsonUtility.ToJson(frame);
        _lidarSocket.SendAsync(json, completed =>
        {
            EnqueueOnMainThread(() =>
            {
                if (!completed)
                {
                    AppendRecentEvent("LiDAR send not completed");
                    return;
                }
            });
        });
    }

    [ContextMenu("Send Direct VLA Infer Request")]
    // Unity 관측값을 모아 직접 VLA 서버에 infer_request를 보냅니다.
    // 위치, 목표, stuck 여부, 선택적 카메라 이미지를 하나의 JSON으로 묶습니다.
    public void SendVlaInferRequest()
    {
        if (!IsVlaSocketActive())
        {
            AppendRecentEvent("VLA request skipped: socket not connected");
            return;
        }

        if (_isVlaRequesting)
        {
            return;
        }

        var targetTransform = ResolveFallbackTransform();
        if (targetTransform == null)
        {
            AppendRecentEvent("VLA request skipped: no controlled transform");
            return;
        }

        if (goal == null)
        {
            AppendRecentEvent("VLA request skipped: goal is null");
            return;
        }

        var targetAgent = ResolveAgent(targetTransform.gameObject);
        _isVlaRequesting = true;
        _vlaRequestSeq += 1;
        _lastVlaRequestId = "vla-" + _vlaRequestSeq.ToString("D6");

        var request = new HumanoidBridgeInferRequest
        {
            request_id = _lastVlaRequestId,
            instruction = vlaInstruction,
            image_b64 = CaptureCameraImageBase64(),
            agent_state = new HumanoidBridgeAgentState
            {
                position = ToArray(targetTransform.position),
                forward = ToArray(targetTransform.forward),
                velocity = targetAgent != null ? ToArray(targetAgent.velocity) : ToArray(Vector3.zero),
            },
            goal = new HumanoidBridgeGoalState
            {
                position = ToArray(goal.position),
            },
            simulation = new HumanoidBridgeSimulationState
            {
                distance_to_goal = Vector3.Distance(targetTransform.position, goal.position),
                has_line_of_sight = HasLineOfSightToGoal(targetTransform),
                stuck = IsStuck(targetAgent),
            },
        };

        var json = JsonUtility.ToJson(request);
        _vlaSocket.SendAsync(json, completed =>
        {
            EnqueueOnMainThread(() =>
            {
                if (completed)
                {
                    lastVlaRequestSummary =
                        $"id={request.request_id}, dist={request.simulation.distance_to_goal:0.00}, " +
                        $"los={request.simulation.has_line_of_sight}, stuck={request.simulation.stuck}";
                    AppendRecentEvent("VLA OUT " + lastVlaRequestSummary);
                    return;
                }

                _isVlaRequesting = false;
                lastVlaRequestSummary = "VLA request send failed";
                AppendRecentEvent(lastVlaRequestSummary);
            });
        });
    }

    // 직접 VLA 서버에서 받은 infer_response를 파싱하고, action을 Unity 제어에 반영한 뒤 ACK를 보냅니다.
    private void HandleIncomingVlaMessage(string json)
    {
        try
        {
            var response = JsonUtility.FromJson<HumanoidBridgeInferResponse>(json);

            if (response == null)
            {
                _isVlaRequesting = false;
                lastVlaResponseSummary = "VLA response is null";
                AppendRecentEvent(lastVlaResponseSummary);
                return;
            }

            if (!string.Equals(response.type, "infer_response", StringComparison.OrdinalIgnoreCase))
            {
                _isVlaRequesting = false;
                lastVlaResponseSummary = "Ignored VLA message type: " + response.type;
                AppendRecentEvent(lastVlaResponseSummary);
                return;
            }

            bool applied = false;
            string ackMessage = "";
            string ackError = "";

            if (response.action == null)
            {
                ackMessage = "Response action is null";
                ackError = ackMessage;
                lastVlaResponseSummary = $"id={response.request_id}, action=NULL";
            }
            else
            {
                RegisterDirectVlaActivity(response.action);
                applied = ApplyVlaAction(response.action, out ackMessage, out ackError);
                var responseTarget = FormatVector(response.action.target_position);
                lastVlaResponseSummary =
                    $"id={response.request_id}, cmd={response.action.command}, stop={response.action.stop}, " +
                    $"move=({response.action.move_x:0.00}, {response.action.move_z:0.00}), " +
                    $"target=({responseTarget}), speed={response.action.speed:0.00}, applied={applied}";
            }

            AppendRecentEvent("VLA IN  " + lastVlaResponseSummary);

            var ack = new HumanoidBridgeVlaAckResponse
            {
                ok = applied,
                request_id = string.IsNullOrWhiteSpace(response.request_id) ? _lastVlaRequestId : response.request_id,
                applied = applied,
                message = string.IsNullOrWhiteSpace(ackMessage)
                    ? (applied ? "Action applied" : "Action rejected")
                    : ackMessage,
                error = ackError ?? "",
                command = "apply_action",
            };

            if (applied)
            {
                var state = BuildRobotStateMessage(ack.request_id, ResolveActiveTargetName(), SceneManager.GetActiveScene().name);
                RecordStateMessage(state);

                if (sendStateContinuously)
                {
                    SendStateOnce();
                }
            }

            SendVlaAck(ack);
        }
        catch (Exception ex)
        {
            _isVlaRequesting = false;
            lastVlaResponseSummary = "VLA parse failed: " + ex.Message;
            AppendRecentEvent(lastVlaResponseSummary);

            SendVlaAck(
                new HumanoidBridgeVlaAckResponse
                {
                    ok = false,
                    request_id = _lastVlaRequestId,
                    applied = false,
                    message = "Parse failed",
                    error = ex.Message,
                    command = "apply_action",
                }
            );
        }
    }

    // 직접 VLA 서버에 "액션 적용 성공/실패" 결과를 되돌려 보냅니다.
    private void SendVlaAck(HumanoidBridgeVlaAckResponse ack)
    {
        if (_vlaSocket == null || !_isVlaConnected)
        {
            _isVlaRequesting = false;
            lastVlaAckSummary = "VLA ACK skipped: socket not connected";
            AppendRecentEvent(lastVlaAckSummary);
            return;
        }

        var ackJson = JsonUtility.ToJson(ack);
        _vlaSocket.SendAsync(ackJson, completed =>
        {
            EnqueueOnMainThread(() =>
            {
                lastVlaAckSummary =
                    $"id={ack.request_id}, ok={ack.ok}, applied={ack.applied}, msg={ack.message}";
                AppendRecentEvent("VLA ACK " + lastVlaAckSummary);

                if (!completed)
                {
                    AppendRecentEvent("VLA ACK send failed");
                }

                _isVlaRequesting = false;
            });
        });
    }

    // 직접 VLA 클라이언트 경로에서 받은 휴머노이드 액션을 실제 Unity 이동으로 적용합니다.
    // Graph Runtime의 robot_command 경로가 아니라, Unity가 VLA 서버에 직접 요청한 응답을 처리하는 함수입니다.
    // 성공 여부와 사용자/로그용 메시지를 out 파라미터로 돌려 ACK 생성에 사용합니다.
    private bool ApplyVlaAction(HumanoidBridgeVlaAction action, out string message, out string error)
    {
        message = "";
        error = "";

        try
        {
            // 모델 응답이 비어 있으면 Unity에 적용할 수 없으므로 실패 ACK로 이어지게 합니다.
            if (action == null)
            {
                message = "Action is null";
                error = message;
                return false;
            }

            // controlledTransform이 명시되어 있으면 그것을, 없으면 NavMeshAgent 또는 이 컴포넌트의 Transform을 씁니다.
            var targetTransform = ResolveFallbackTransform();
            if (targetTransform == null)
            {
                message = "Controlled transform is null";
                error = message;
                return false;
            }

            // 이후 상태 메시지와 overlay가 같은 대상을 가리키도록 활성 대상/프로필을 갱신합니다.
            controlledTransform = targetTransform;
            _activeRobotType = ResolveConfiguredRobotType();
            _activeControllerMode = ResolveConfiguredControllerMode();
            var targetObject = targetTransform.gameObject;
            var targetAgent = ResolveAgent(targetObject);
            var normalizedCommand = NormalizeCommand(action.command);

            // stop 응답은 이동 목표만 지우고 성공으로 처리합니다.
            // 모델이 "더 이상 움직이지 말라"고 판단한 정상 명령일 수 있기 때문입니다.
            if (action.stop || action.terminate)
            {
                if (targetAgent != null)
                {
                    targetAgent.ResetPath();
                }

                message = "Stop action applied";
                return true;
            }

            if (normalizedCommand == "apply_base_waypoint" ||
                (action.target_position != null && action.target_position.Length > 0))
            {
                var targetPosition = ToVector3(action.target_position);
                Vector3 resolvedPosition;
                if (!TryMoveTargetPosition(
                    targetObject,
                    targetAgent,
                    targetPosition,
                    Mathf.Max(0.1f, action.speed),
                    out resolvedPosition,
                    out error))
                {
                    message = error;
                    return false;
                }

                if (applyRotationDelta && action.target_rotation != null && action.target_rotation.Length > 0)
                {
                    targetObject.transform.eulerAngles = ToVector3(action.target_rotation);
                }

                UpdateGripperState(action.gripper);
                message =
                    $"Waypoint applied to ({resolvedPosition.x:0.00}, {resolvedPosition.y:0.00}, {resolvedPosition.z:0.00})";
                return true;
            }

            if (normalizedCommand == "apply_action" ||
                (action.translation != null && action.translation.Length > 0))
            {
                var translation = ToVector3(action.translation) * translationScale;
                var actionWorldDelta = translationSpace == TranslationSpace.Self
                    ? targetObject.transform.TransformDirection(translation)
                    : translation;
                Vector3 resolvedPosition;
                if (!TryMoveTargetDelta(
                    targetObject,
                    targetAgent,
                    actionWorldDelta,
                    Mathf.Max(0.1f, action.speed),
                    out resolvedPosition,
                    out error))
                {
                    message = error;
                    return false;
                }

                if (applyRotationDelta && action.rotation != null && action.rotation.Length > 0)
                {
                    targetObject.transform.eulerAngles += ToVector3(action.rotation) * rotationScale;
                }

                UpdateGripperState(action.gripper);
                message =
                    $"Delta action applied to ({resolvedPosition.x:0.00}, {resolvedPosition.y:0.00}, {resolvedPosition.z:0.00})";
                return true;
            }

            // VLA 응답은 로봇 로컬 평면 기준의 move_x/move_z로 들어옵니다.
            // y축은 지면 이동에서 사용하지 않으므로 0으로 고정합니다.
            var localDelta = new Vector3(action.move_x, 0f, action.move_z);
            var magnitude = localDelta.magnitude;
            if (magnitude < Mathf.Max(0.0001f, vlaMinMoveMagnitude))
            {
                message = "Move magnitude too small";
                return false;
            }

            // 모델이 준 방향만 사용하고, 실제 한 스텝 길이는 vlaStepScale로 제어합니다.
            // TransformDirection은 로봇 로컬 방향을 월드 방향으로 바꿉니다.
            var localStep = localDelta.normalized * Mathf.Max(0.01f, vlaStepScale);
            var worldDelta = targetTransform.TransformDirection(localStep);
            var nextPoint = targetTransform.position + worldDelta;

            // NavMeshAgent를 선호하고 사용 가능한 경우, 목표점을 NavMesh 위로 보정한 뒤 SetDestination을 호출합니다.
            // 이 경로가 캐릭터/휴머노이드 이동에서 가장 자연스럽습니다.
            if (preferNavMeshAgent && targetAgent != null)
            {
                NavMeshHit hit;
                if (!NavMesh.SamplePosition(nextPoint, out hit, navSampleRadius, NavMesh.AllAreas))
                {
                    message = "NavMesh.SamplePosition failed";
                    error = message;
                    return false;
                }

                targetAgent.speed = Mathf.Max(0.1f, action.speed);
                if (!targetAgent.SetDestination(hit.position))
                {
                    message = "SetDestination failed";
                    error = message;
                    return false;
                }

                message =
                    $"Destination set to ({hit.position.x:0.00}, {hit.position.y:0.00}, {hit.position.z:0.00})";
                return true;
            }

            // NavMeshAgent가 없거나 사용하지 않는 설정이면 Transform 위치를 직접 이동합니다.
            // 물리/애니메이션 시스템과 충돌할 수 있으므로 테스트용 또는 단순 오브젝트에 적합합니다.
            targetObject.transform.position = nextPoint;
            UpdateGripperState(action.gripper);
            message =
                $"Position set to ({nextPoint.x:0.00}, {nextPoint.y:0.00}, {nextPoint.z:0.00})";
            return true;
        }
        catch (Exception ex)
        {
            message = "ApplyVlaAction exception";
            error = ex.Message;
            return false;
        }
    }

    // WebSocket으로 받은 robot_command 하나를 처리하고 ACK/state 묶음을 만듭니다.
    // 실제 적용은 ApplyRequest가 담당하고, sendStateAfterCommand가 켜져 있으면 최신 상태도 함께 보냅니다.
    private HumanoidBridgeProcessResult ProcessIncomingRequest(HumanoidBridgeRobotCommandRequest request)
    {
        var targetName = ResolveTargetName(request != null ? request.@object : "");
        var sceneName = SceneManager.GetActiveScene().name;
        RegisterCommandActivity(request, "robot_command");
        var ack = ApplyRequest(request, targetName, sceneName);

        HumanoidBridgeRobotState state = null;
        if (sendStateAfterCommand && ack != null && ack.ok)
        {
            state = BuildRobotStateMessage(
                request != null ? request.request_id : "",
                ack != null ? ack.target : targetName,
                ack != null ? ack.scene : sceneName
            );
        }

        if (sendLidarAfterCommand && ack != null && ack.ok)
        {
            if (!IsLidarSocketActive())
            {
                ConnectLidarSocket();
            }
            else
            {
                SendLidarOnce(ack.target, ack.scene);
            }
        }

        return new HumanoidBridgeProcessResult
        {
            ack = ack,
            state = state,
        };
    }

    // 백엔드에서 온 명령을 검증한 뒤 command 이름에 맞는 적용 함수로 분기합니다.
    // 이 함수가 graph runtime robot_execute 노드와 Unity 제어 로직 사이의 핵심 라우터입니다.
    private HumanoidBridgeRobotAckResponse ApplyRequest(
        HumanoidBridgeRobotCommandRequest request,
        string targetName,
        string activeScene
    )
    {
        if (request == null)
        {
            return Fail("", activeScene, targetName, "Request is null", "");
        }

        if (!string.Equals(request.type, "robot_command", StringComparison.OrdinalIgnoreCase))
        {
            return Fail(
                request.request_id,
                activeScene,
                targetName,
                $"Unsupported type: {request.type}",
                request.command
            );
        }

        if (request.action == null)
        {
            return Fail(request.request_id, activeScene, targetName, "Action is null", request.command);
        }

        if (requireSceneMatch &&
            !string.IsNullOrWhiteSpace(request.scene) &&
            !string.Equals(request.scene, activeScene, StringComparison.Ordinal))
        {
            return Fail(
                request.request_id,
                activeScene,
                targetName,
                $"Scene mismatch: req={request.scene}, active={activeScene}",
                request.command
            );
        }

        var targetObject = ResolveCommandTargetObject(targetName);
        if (targetObject == null)
        {
            return Fail(
                request.request_id,
                activeScene,
                targetName,
                $"Target object not found: {targetName}",
                request.command
            );
        }

        controlledTransform = targetObject.transform;
        _activeRobotType = ResolveRequestRobotType(request);
        _activeControllerMode = ResolveRequestControllerMode(request);

        var targetAgent = ResolveAgent(targetObject);
        var command = NormalizeCommand(request.command);

        try
        {
            UpdateGripperState(request.action.gripper);

            if ((request.action.terminate || request.action.stop) && stopOnTerminate)
            {
                return StopTargetMotion(request, activeScene, targetObject, targetAgent, "Stop action applied");
            }

            switch (command)
            {
                case "apply_action":
                    return ApplyLegacyActionCommand(request, activeScene, targetObject, targetAgent);
                case "apply_joint_targets":
                    return ApplyJointTargetsCommand(request, activeScene, targetObject, false, false);
                case "apply_joint_deltas":
                    return ApplyJointTargetsCommand(request, activeScene, targetObject, true, false);
                case "apply_joint_velocities":
                    return ApplyJointTargetsCommand(request, activeScene, targetObject, false, true);
                case "apply_base_velocity":
                    return ApplyBaseVelocityCommand(request, activeScene, targetObject, targetAgent);
                case "apply_base_waypoint":
                    return ApplyBaseWaypointCommand(request, activeScene, targetObject, targetAgent);
                case "apply_humanoid_step":
                    return ApplyHumanoidStepCommand(request, activeScene, targetObject, targetAgent);
                case "apply_patrol_control":
                case "set_patrol_control":
                case "patrol_control":
                    return ApplyPatrolControlCommand(request, activeScene, targetObject);
                case "stop":
                    return StopTargetMotion(request, activeScene, targetObject, targetAgent, "Stop command applied");
                default:
                    return Fail(
                        request.request_id,
                        activeScene,
                        targetObject.name,
                        $"Unsupported command: {request.command}",
                        request.command
                    );
            }
        }
        catch (Exception ex)
        {
            return Fail(request.request_id, activeScene, targetObject.name, ex.Message, request.command);
        }
    }

    // Inspector에 설정된 기본 robot type을 정리해서 반환합니다.
    private string ResolveConfiguredRobotType()
    {
        return string.IsNullOrWhiteSpace(unityRobotType) ? "generic" : unityRobotType.Trim();
    }

    // Inspector에 설정된 기본 controller mode를 정리해서 반환합니다.
    private string ResolveConfiguredControllerMode()
    {
        return string.IsNullOrWhiteSpace(unityControllerMode) ? "task" : unityControllerMode.Trim();
    }

    // 요청 payload에 robot_type이 있으면 그것을 우선하고, 없으면 Inspector 기본값을 사용합니다.
    private string ResolveRequestRobotType(HumanoidBridgeRobotCommandRequest request)
    {
        if (request != null && !string.IsNullOrWhiteSpace(request.robot_type))
        {
            return request.robot_type.Trim();
        }

        return ResolveConfiguredRobotType();
    }

    // 요청 payload에 controller_mode가 있으면 그것을 우선하고, 없으면 Inspector 기본값을 사용합니다.
    private string ResolveRequestControllerMode(HumanoidBridgeRobotCommandRequest request)
    {
        if (request != null && !string.IsNullOrWhiteSpace(request.controller_mode))
        {
            return request.controller_mode.Trim();
        }

        return ResolveConfiguredControllerMode();
    }

    // command 문자열을 비교하기 쉬운 소문자 형태로 정규화합니다.
    // 비어 있으면 오래된 기본 명령인 apply_action으로 처리합니다.
    private static string NormalizeCommand(string command)
    {
        return string.IsNullOrWhiteSpace(command) ? "apply_action" : command.Trim().ToLowerInvariant();
    }

    // 이동 중인 NavMeshAgent 목표를 지우고 정지 ACK를 만듭니다.
    private HumanoidBridgeRobotAckResponse StopTargetMotion(
        HumanoidBridgeRobotCommandRequest request,
        string activeScene,
        GameObject targetObject,
        NavMeshAgent targetAgent,
        string message
    )
    {
        if (targetAgent != null)
        {
            targetAgent.ResetPath();
        }

        return new HumanoidBridgeRobotAckResponse
        {
            ok = true,
            request_id = request.request_id,
            applied = true,
            message = message,
            error = "",
            scene = activeScene,
            target = targetObject.name,
            command = request.command,
        };
    }

    // apply_action 명령 처리입니다.
    // translation/rotation을 사용하던 초기 포맷을 유지하기 위한 호환 경로입니다.
    private HumanoidBridgeRobotAckResponse ApplyLegacyActionCommand(
        HumanoidBridgeRobotCommandRequest request,
        string activeScene,
        GameObject targetObject,
        NavMeshAgent targetAgent
    )
    {
        var translation = ToVector3(request.action.translation) * translationScale;
        var rotation = ToVector3(request.action.rotation) * rotationScale;
        var appliedTranslation = false;
        var appliedRotation = false;
        var messageParts = new List<string>();

        if (translation.magnitude >= minTranslationMagnitude)
        {
            var worldDelta = translationSpace == TranslationSpace.Self
                ? targetObject.transform.TransformDirection(translation)
                : translation;

            Vector3 resolvedPosition;
            string error;
            if (!TryMoveTargetDelta(
                targetObject,
                targetAgent,
                worldDelta,
                translation.magnitude,
                out resolvedPosition,
                out error))
            {
                return Fail(request.request_id, activeScene, targetObject.name, error, request.command);
            }

            appliedTranslation = true;
            messageParts.Add(
                $"position=({resolvedPosition.x:0.00}, {resolvedPosition.y:0.00}, {resolvedPosition.z:0.00})"
            );
        }

        if (applyRotationDelta && rotation.magnitude > 0.0001f)
        {
            targetObject.transform.eulerAngles += rotation;
            appliedRotation = true;

            var euler = targetObject.transform.eulerAngles;
            messageParts.Add($"rotation=({euler.x:0.00}, {euler.y:0.00}, {euler.z:0.00})");
        }

        if (!appliedTranslation && !appliedRotation)
        {
            return Fail(
                request.request_id,
                activeScene,
                targetObject.name,
                "Translation and rotation magnitudes are too small",
                request.command
            );
        }

        return new HumanoidBridgeRobotAckResponse
        {
            ok = true,
            request_id = request.request_id,
            applied = true,
            message = string.Join(", ", messageParts.ToArray()),
            error = "",
            scene = activeScene,
            target = targetObject.name,
            command = request.command,
        };
    }

    // apply_humanoid_step 명령 처리입니다.
    // 로컬 평면 이동(move_x/move_z)과 yaw 회전(turn_yaw)을 휴머노이드 이동에 적용합니다.
    private HumanoidBridgeRobotAckResponse ApplyHumanoidStepCommand(
        HumanoidBridgeRobotCommandRequest request,
        string activeScene,
        GameObject targetObject,
        NavMeshAgent targetAgent
    )
    {
        var localStep = new Vector3(request.action.move_x, 0f, request.action.move_z) * translationScale;
        var yawDelta = request.action.turn_yaw * rotationScale;
        var appliedTranslation = false;
        var appliedRotation = false;
        var messageParts = new List<string>();

        if (localStep.magnitude >= minTranslationMagnitude)
        {
            var worldDelta = targetObject.transform.TransformDirection(localStep);
            Vector3 resolvedPosition;
            string error;
            if (!TryMoveTargetDelta(
                targetObject,
                targetAgent,
                worldDelta,
                Mathf.Max(0.1f, request.action.speed),
                out resolvedPosition,
                out error))
            {
                return Fail(request.request_id, activeScene, targetObject.name, error, request.command);
            }

            appliedTranslation = true;
            messageParts.Add(
                $"step=({resolvedPosition.x:0.00}, {resolvedPosition.y:0.00}, {resolvedPosition.z:0.00})"
            );
        }

        if (applyRotationDelta && Mathf.Abs(yawDelta) > 0.0001f)
        {
            targetObject.transform.eulerAngles += new Vector3(0f, yawDelta, 0f);
            appliedRotation = true;
            messageParts.Add($"yaw={targetObject.transform.eulerAngles.y:0.00}");
        }

        if (!appliedTranslation && !appliedRotation)
        {
            return Fail(request.request_id, activeScene, targetObject.name, "Humanoid step is too small", request.command);
        }

        return new HumanoidBridgeRobotAckResponse
        {
            ok = true,
            request_id = request.request_id,
            applied = true,
            message = string.Join(", ", messageParts.ToArray()),
            error = "",
            scene = activeScene,
            target = targetObject.name,
            command = request.command,
        };
    }

    // ThirdPersonController의 자율 순찰 모드를 외부 AI 서버 명령으로 제어합니다.
    private HumanoidBridgeRobotAckResponse ApplyPatrolControlCommand(
        HumanoidBridgeRobotCommandRequest request,
        string activeScene,
        GameObject targetObject
    )
    {
        var controller = ResolveThirdPersonController(targetObject);
        if (controller == null)
        {
            return Fail(request.request_id, activeScene, targetObject.name, "ThirdPersonController not found", request.command);
        }

        var mode = string.IsNullOrWhiteSpace(request.action.patrol_mode)
            ? InferPatrolMode(request.action)
            : request.action.patrol_mode.Trim().ToLowerInvariant();
        var speed = request.action.patrol_speed > 0.0f ? request.action.patrol_speed : request.action.speed;
        var message = "";

        switch (mode)
        {
            case "enable":
            case "on":
                controller.SetAutonomousPatrolEnabled(true);
                if (speed > 0.0f)
                {
                    controller.AutonomousPatrolSpeed = speed;
                }
                message = $"patrol enabled, speed={controller.AutonomousPatrolSpeed:0.00}";
                break;

            case "disable":
            case "off":
                controller.SetAutonomousPatrolEnabled(false);
                message = "patrol disabled";
                break;

            case "internal":
            case "auto":
                controller.ClearExternalPatrolControl();
                controller.SetAutonomousPatrolEnabled(true);
                if (speed > 0.0f)
                {
                    controller.AutonomousPatrolSpeed = speed;
                }
                message = $"internal patrol enabled, speed={controller.AutonomousPatrolSpeed:0.00}";
                break;

            case "target":
            case "waypoint":
            {
                var targetPosition = request.action.patrol_target_position != null &&
                                     request.action.patrol_target_position.Length > 0
                    ? ToVector3(request.action.patrol_target_position)
                    : ToVector3(request.action.target_position);
                controller.SetExternalPatrolTarget(targetPosition, speed);
                message =
                    $"external patrol target=({targetPosition.x:0.00}, {targetPosition.y:0.00}, {targetPosition.z:0.00}), " +
                    $"speed={controller.AutonomousPatrolSpeed:0.00}";
                break;
            }

            case "direction":
            case "velocity":
            {
                var direction = ResolvePatrolDirection(request.action);
                if (direction.sqrMagnitude <= 0.0001f)
                {
                    return Fail(request.request_id, activeScene, targetObject.name, "Patrol direction is too small", request.command);
                }

                controller.SetExternalPatrolDirection(direction, speed);
                message =
                    $"external patrol direction=({direction.x:0.00}, {direction.y:0.00}, {direction.z:0.00}), " +
                    $"speed={controller.AutonomousPatrolSpeed:0.00}";
                break;
            }

            default:
                return Fail(
                    request.request_id,
                    activeScene,
                    targetObject.name,
                    $"Unsupported patrol_mode: {request.action.patrol_mode}",
                    request.command
                );
        }

        return new HumanoidBridgeRobotAckResponse
        {
            ok = true,
            request_id = request.request_id,
            applied = true,
            message = message,
            error = "",
            scene = activeScene,
            target = targetObject.name,
            command = request.command,
        };
    }

    // 외부 명령이 한 번이라도 들어오면 idle 타이머를 리셋하고, idle patrol이 켜져 있으면 즉시 양보시킵니다.
    private void RegisterCommandActivity(HumanoidBridgeRobotCommandRequest request, string source)
    {
        _lastCommandActivityAt = Time.realtimeSinceStartup;
        idleSecondsSinceLastCommand = 0.0f;

        if (!enableIdlePatrol)
        {
            return;
        }

        var command = NormalizeCommand(request != null ? request.command : "");
        if (idlePatrolActive && stopIdlePatrolOnNewCommand)
        {
            var targetName = ResolveTargetName(request != null ? request.@object : "");
            StopIdlePatrol(ResolveCommandTargetObject(targetName), $"{source} received: {command}", true);
            return;
        }

        idlePatrolSummary = $"{source} received. Waiting {Mathf.Max(0.1f, idlePatrolDelaySec):0.0}s before idle patrol.";
    }

    // 직접 VLA 클라이언트 응답도 외부 AI 입력으로 간주해서 idle patrol과 충돌하지 않게 합니다.
    private void RegisterDirectVlaActivity(HumanoidBridgeVlaAction action)
    {
        _lastCommandActivityAt = Time.realtimeSinceStartup;
        idleSecondsSinceLastCommand = 0.0f;

        if (!enableIdlePatrol)
        {
            return;
        }

        if (idlePatrolActive && stopIdlePatrolOnNewCommand)
        {
            var targetTransform = ResolveFallbackTransform();
            var targetObject = targetTransform != null ? targetTransform.gameObject : null;
            var command = NormalizeCommand(action != null ? action.command : "");
            StopIdlePatrol(targetObject, $"direct VLA response received: {command}", true);
            return;
        }

        idlePatrolSummary = $"Direct VLA response received. Waiting {Mathf.Max(0.1f, idlePatrolDelaySec):0.0}s before idle patrol.";
    }

    // 사용자 이동 입력이 있으면 AI/idle patrol보다 먼저 처리되도록 patrol을 잠시 멈추고 idle 타이머를 리셋합니다.
    private void UpdatePlayerInputPriorityLoop()
    {
        if (!enableIdlePatrol || !stopIdlePatrolOnPlayerInput)
        {
            _playerInputWasActive = false;
            return;
        }

        GameObject targetObject;
        string inputSummary;
        var inputActive = TryGetPlayerInputActivity(out targetObject, out inputSummary);
        if (!inputActive)
        {
            _playerInputWasActive = false;
            return;
        }

        _lastCommandActivityAt = Time.realtimeSinceStartup;
        idleSecondsSinceLastCommand = 0.0f;
        lastPlayerInputSummary = inputSummary;

        var controller = ResolveThirdPersonController(targetObject);
        var shouldStopPatrol = idlePatrolActive || (controller != null && controller.EnableAutonomousPatrol);
        if (shouldStopPatrol)
        {
            StopIdlePatrol(targetObject, $"player input priority: {inputSummary}", true);
            if (!idlePatrolActive && controller != null && controller.EnableAutonomousPatrol)
            {
                RestoreIdlePatrolInputMode(controller);
                controller.SetAutonomousPatrolEnabled(false);
                controller.ForcePlayerInputEnabled();
            }
        }
        else
        {
            idlePatrolSummary =
                $"Player input active. Waiting {Mathf.Max(0.1f, idlePatrolDelaySec):0.0}s after input before idle patrol.";
        }

        if (!_playerInputWasActive)
        {
            AppendRecentEvent("INPUT " + inputSummary);
        }

        _playerInputWasActive = true;
    }

    private bool TryGetPlayerInputActivity(out GameObject targetObject, out string inputSummary)
    {
        targetObject = ResolveIdlePatrolTargetObject();
        inputSummary = "";

        if (targetObject == null)
        {
            return false;
        }

        var inputs = targetObject.GetComponent<StarterAssetsInputs>();
        if (inputs == null)
        {
            inputs = targetObject.GetComponentInChildren<StarterAssetsInputs>();
        }

        if (inputs != null)
        {
            var moveThreshold = Mathf.Max(0.0f, playerMoveInputThreshold);
            if (inputs.move.sqrMagnitude > moveThreshold * moveThreshold)
            {
                inputSummary = $"move=({inputs.move.x:0.00}, {inputs.move.y:0.00})";
                return true;
            }

            if (inputs.jump)
            {
                inputSummary = "jump";
                return true;
            }

            if (inputs.sprint)
            {
                inputSummary = "sprint";
                return true;
            }

            if (playerLookInputCountsAsActivity)
            {
                var lookThreshold = Mathf.Max(0.0f, playerLookInputThreshold);
                if (inputs.look.sqrMagnitude > lookThreshold * lookThreshold)
                {
                    inputSummary = $"look=({inputs.look.x:0.00}, {inputs.look.y:0.00})";
                    return true;
                }
            }
        }

#if ENABLE_INPUT_SYSTEM
        if (TryGetInputSystemActivity(out inputSummary))
        {
            return true;
        }
#endif

        return false;
    }

#if ENABLE_INPUT_SYSTEM
    private bool TryGetInputSystemActivity(out string inputSummary)
    {
        inputSummary = "";
        var move = Vector2.zero;

        var keyboard = Keyboard.current;
        if (keyboard != null)
        {
            if (keyboard.aKey.isPressed || keyboard.leftArrowKey.isPressed)
            {
                move.x -= 1.0f;
            }
            if (keyboard.dKey.isPressed || keyboard.rightArrowKey.isPressed)
            {
                move.x += 1.0f;
            }
            if (keyboard.sKey.isPressed || keyboard.downArrowKey.isPressed)
            {
                move.y -= 1.0f;
            }
            if (keyboard.wKey.isPressed || keyboard.upArrowKey.isPressed)
            {
                move.y += 1.0f;
            }

            var moveThreshold = Mathf.Max(0.0f, playerMoveInputThreshold);
            if (move.sqrMagnitude > moveThreshold * moveThreshold)
            {
                inputSummary = $"keyboard move=({move.x:0.00}, {move.y:0.00})";
                return true;
            }

            if (keyboard.spaceKey.isPressed)
            {
                inputSummary = "keyboard jump";
                return true;
            }

            if (keyboard.leftShiftKey.isPressed || keyboard.rightShiftKey.isPressed)
            {
                inputSummary = "keyboard sprint";
                return true;
            }
        }

        var gamepad = Gamepad.current;
        if (gamepad != null)
        {
            var stick = gamepad.leftStick.ReadValue();
            var moveThreshold = Mathf.Max(0.0f, playerMoveInputThreshold);
            if (stick.sqrMagnitude > moveThreshold * moveThreshold)
            {
                inputSummary = $"gamepad move=({stick.x:0.00}, {stick.y:0.00})";
                return true;
            }

            if (gamepad.buttonSouth.isPressed)
            {
                inputSummary = "gamepad jump";
                return true;
            }

            if (gamepad.leftStickButton.isPressed || gamepad.leftShoulder.isPressed)
            {
                inputSummary = "gamepad sprint";
                return true;
            }
        }

        return false;
    }
#endif

    // 매 프레임 외부 명령 공백 시간을 확인하고, 설정한 지연 시간이 지나면 ThirdPersonController 순찰을 켭니다.
    private void UpdateIdlePatrolLoop()
    {
        if (_lastCommandActivityAt <= 0.0f)
        {
            _lastCommandActivityAt = Time.realtimeSinceStartup;
        }

        if (!enableIdlePatrol)
        {
            idleSecondsSinceLastCommand = 0.0f;
            if (idlePatrolActive)
            {
                StopIdlePatrol(ResolveIdlePatrolTargetObject(), "idle patrol disabled", true);
            }
            else
            {
                idlePatrolSummary = "Idle patrol disabled.";
            }
            return;
        }

        var now = Time.realtimeSinceStartup;
        var delay = Mathf.Max(0.1f, idlePatrolDelaySec);
        idleSecondsSinceLastCommand = Mathf.Max(0.0f, now - _lastCommandActivityAt);

        if (idlePatrolActive)
        {
            idlePatrolSummary =
                $"Idle patrol active. No external command for {idleSecondsSinceLastCommand:0.0}s.";
            return;
        }

        if (idleSecondsSinceLastCommand < delay)
        {
            _idlePatrolStoppedMotionWaitStartedAt = -1f;
            idlePatrolSummary =
                $"Waiting for idle patrol: {idleSecondsSinceLastCommand:0.0}/{delay:0.0}s without external command.";
            return;
        }

        if (now < _nextIdlePatrolAttemptAt)
        {
            return;
        }

        TryStartIdlePatrol();
    }

    private bool TryStartIdlePatrol()
    {
        var targetObject = ResolveIdlePatrolTargetObject();
        if (targetObject == null)
        {
            ScheduleIdlePatrolRetry("Idle patrol target not found.");
            return false;
        }

        var takingOverStaleMotion = false;
        if (idlePatrolRequiresStoppedMotion && IsTargetStillMoving(targetObject))
        {
            var now = Time.realtimeSinceStartup;
            if (_idlePatrolStoppedMotionWaitStartedAt < 0.0f)
            {
                _idlePatrolStoppedMotionWaitStartedAt = now;
            }

            var maxWait = Mathf.Max(0.0f, idlePatrolMaxStoppedMotionWaitSec);
            if (maxWait <= 0.0f || now - _idlePatrolStoppedMotionWaitStartedAt < maxWait)
            {
                _nextIdlePatrolAttemptAt = now + 0.5f;
                idlePatrolSummary =
                    $"Waiting for current motion to settle before idle patrol: {targetObject.name} " +
                    $"({Mathf.Max(0.0f, now - _idlePatrolStoppedMotionWaitStartedAt):0.0}/{maxWait:0.0}s).";
                return false;
            }

            AppendRecentEvent(
                $"IDLE starting despite stale motion state after {maxWait:0.0}s: {targetObject.name}"
            );
            takingOverStaleMotion = true;
        }
        else
        {
            _idlePatrolStoppedMotionWaitStartedAt = -1f;
        }

        var controller = ResolveThirdPersonController(targetObject);
        if (controller == null)
        {
            ScheduleIdlePatrolRetry($"ThirdPersonController not found on idle patrol target: {targetObject.name}.");
            return false;
        }

        controlledTransform = targetObject.transform;

        if (idlePatrolSpeed > 0.0f)
        {
            controller.AutonomousPatrolSpeed = idlePatrolSpeed;
        }

        if (idlePatrolUseInternalMode)
        {
            controller.ClearExternalPatrolControl();
        }

        ConfigureIdlePatrolInputMode(controller);
        controller.SetAutonomousPatrolEnabled(true);
        idlePatrolActive = true;
        _idlePatrolStoppedMotionWaitStartedAt = -1f;
        idlePatrolSummary =
            $"Idle patrol active: target={targetObject.name}, " +
            $"mode={(idlePatrolUseInternalMode ? "internal" : "enable")}, " +
            $"speed={controller.AutonomousPatrolSpeed:0.00}" +
            $"{(takingOverStaleMotion ? ", stale motion takeover" : "")}.";
        AppendRecentEvent("IDLE " + idlePatrolSummary);
        return true;
    }

    private void StopIdlePatrol(GameObject targetObject, string reason, bool disableController)
    {
        if (!idlePatrolActive)
        {
            return;
        }

        if (disableController)
        {
            var resolvedTarget = targetObject != null ? targetObject : ResolveIdlePatrolTargetObject();
            var controller = ResolveThirdPersonController(resolvedTarget);
            if (controller != null)
            {
                RestoreIdlePatrolInputMode(controller);
                controller.SetAutonomousPatrolEnabled(false);
                controller.ForcePlayerInputEnabled();
            }
        }
        else if (_idlePatrolController != null)
        {
            RestoreIdlePatrolInputMode(_idlePatrolController);
        }

        idlePatrolActive = false;
        idlePatrolSummary = string.IsNullOrWhiteSpace(reason) ? "Idle patrol stopped." : reason;
        AppendRecentEvent("IDLE " + idlePatrolSummary);
    }

    private void ConfigureIdlePatrolInputMode(ThirdPersonController controller)
    {
        if (controller == null || !keepPlayerInputEnabledDuringIdlePatrol)
        {
            return;
        }

        if (!_hasIdlePatrolInputModeSnapshot || _idlePatrolController != controller)
        {
            _idlePatrolController = controller;
            _idlePatrolDefaultDisablePlayerInputDuringPatrol = controller.DisablePlayerInputDuringPatrol;
            _hasIdlePatrolInputModeSnapshot = true;
        }

        controller.DisablePlayerInputDuringPatrol = false;
        controller.ForcePlayerInputEnabled();
    }

    private void RestoreIdlePatrolInputMode(ThirdPersonController controller)
    {
        if (controller == null || !_hasIdlePatrolInputModeSnapshot || _idlePatrolController != controller)
        {
            return;
        }

        controller.DisablePlayerInputDuringPatrol = _idlePatrolDefaultDisablePlayerInputDuringPatrol;
        _idlePatrolController = null;
        _hasIdlePatrolInputModeSnapshot = false;
    }

    private void ScheduleIdlePatrolRetry(string reason)
    {
        _nextIdlePatrolAttemptAt =
            Time.realtimeSinceStartup + Mathf.Max(0.25f, idlePatrolRetryIntervalSec);
        idlePatrolSummary = reason;
        AppendRecentEvent("IDLE " + reason);
    }

    private GameObject ResolveIdlePatrolTargetObject()
    {
        var targetName = !string.IsNullOrWhiteSpace(idlePatrolTargetObject)
            ? idlePatrolTargetObject.Trim()
            : ResolveTargetName(defaultTargetObject);
        var targetObject = ResolveCommandTargetObject(targetName);
        if (targetObject != null)
        {
            return targetObject;
        }

        var fallback = ResolveFallbackTransform();
        return fallback != null ? fallback.gameObject : null;
    }

    private ThirdPersonController ResolveThirdPersonController(GameObject targetObject)
    {
        if (targetObject == null)
        {
            return null;
        }

        var controller = targetObject.GetComponent<ThirdPersonController>();
        return controller != null ? controller : targetObject.GetComponentInChildren<ThirdPersonController>();
    }

    private bool IsTargetStillMoving(GameObject targetObject)
    {
        if (targetObject == null)
        {
            return false;
        }

        var threshold = Mathf.Max(0.0f, idlePatrolStoppedVelocityThreshold);
        var targetAgent = ResolveAgent(targetObject);
        if (targetAgent != null && targetAgent.enabled && targetAgent.isOnNavMesh)
        {
            if (targetAgent.pathPending)
            {
                return true;
            }

            if (targetAgent.velocity.magnitude > threshold)
            {
                return true;
            }

            if (!targetAgent.isStopped && targetAgent.hasPath)
            {
                var distanceTolerance = Mathf.Max(targetAgent.stoppingDistance + 0.2f, 0.3f);
                var remainingDistance = targetAgent.remainingDistance;
                var hasUsableDistance = !float.IsInfinity(remainingDistance) && !float.IsNaN(remainingDistance);
                if (hasUsableDistance &&
                    remainingDistance > distanceTolerance &&
                    targetAgent.desiredVelocity.magnitude > threshold)
                {
                    return true;
                }
            }
        }

        var characterController = targetObject.GetComponent<CharacterController>();
        if (characterController == null)
        {
            characterController = targetObject.GetComponentInChildren<CharacterController>();
        }

        return characterController != null && characterController.velocity.magnitude > threshold;
    }

    private static string InferPatrolMode(HumanoidBridgeRobotAction action)
    {
        if (action == null)
        {
            return "";
        }

        if (action.stop || action.terminate)
        {
            return "disable";
        }

        if (action.patrol_target_position != null && action.patrol_target_position.Length > 0 ||
            action.target_position != null && action.target_position.Length > 0)
        {
            return "target";
        }

        if (action.patrol_direction != null && action.patrol_direction.Length > 0 ||
            action.linear != null && action.linear.Length > 0 ||
            action.translation != null && action.translation.Length > 0 ||
            Mathf.Abs(action.linear_x) > 0.0001f ||
            Mathf.Abs(action.linear_z) > 0.0001f)
        {
            return "direction";
        }

        return "enable";
    }

    private static Vector3 ResolvePatrolDirection(HumanoidBridgeRobotAction action)
    {
        if (action == null)
        {
            return Vector3.zero;
        }

        if (action.patrol_direction != null && action.patrol_direction.Length > 0)
        {
            return ToVector3(action.patrol_direction);
        }

        if (action.linear != null && action.linear.Length > 0)
        {
            return ToVector3(action.linear);
        }

        if (action.translation != null && action.translation.Length > 0)
        {
            return ToVector3(action.translation);
        }

        return new Vector3(action.linear_x, 0.0f, action.linear_z);
    }

    // apply_base_velocity 명령 처리입니다.
    // linear/angular 배열 또는 scalar fallback 값을 읽어 베이스 속도형 이동으로 적용합니다.
    private HumanoidBridgeRobotAckResponse ApplyBaseVelocityCommand(
        HumanoidBridgeRobotCommandRequest request,
        string activeScene,
        GameObject targetObject,
        NavMeshAgent targetAgent
    )
    {
        var linear = request.action.linear != null && request.action.linear.Length > 0
            ? ToVector3(request.action.linear)
            : new Vector3(request.action.linear_x, 0f, request.action.linear_z);
        var angular = request.action.angular != null && request.action.angular.Length > 0
            ? ToVector3(request.action.angular)
            : new Vector3(0f, request.action.angular_yaw, 0f);

        var localStep = new Vector3(linear.x, 0f, linear.z) * translationScale;
        var yawDelta = angular.y * rotationScale;
        var appliedTranslation = false;
        var appliedRotation = false;
        var messageParts = new List<string>();

        if (applyRotationDelta && Mathf.Abs(yawDelta) > 0.0001f)
        {
            targetObject.transform.eulerAngles += new Vector3(0f, yawDelta, 0f);
            appliedRotation = true;
            messageParts.Add($"yaw={targetObject.transform.eulerAngles.y:0.00}");
        }

        if (localStep.magnitude >= minTranslationMagnitude)
        {
            var worldDelta = targetObject.transform.TransformDirection(localStep);
            Vector3 resolvedPosition;
            string error;
            if (!TryMoveTargetDelta(
                targetObject,
                targetAgent,
                worldDelta,
                Mathf.Max(0.1f, localStep.magnitude),
                out resolvedPosition,
                out error))
            {
                return Fail(request.request_id, activeScene, targetObject.name, error, request.command);
            }

            appliedTranslation = true;
            messageParts.Add(
                $"base=({resolvedPosition.x:0.00}, {resolvedPosition.y:0.00}, {resolvedPosition.z:0.00})"
            );
        }

        if (!appliedTranslation && !appliedRotation)
        {
            return Fail(request.request_id, activeScene, targetObject.name, "Base velocity is too small", request.command);
        }

        return new HumanoidBridgeRobotAckResponse
        {
            ok = true,
            request_id = request.request_id,
            applied = true,
            message = string.Join(", ", messageParts.ToArray()),
            error = "",
            scene = activeScene,
            target = targetObject.name,
            command = request.command,
        };
    }

    // apply_base_waypoint 명령 처리입니다.
    // target_position/target_rotation 또는 translation/rotation fallback을 목표점으로 해석합니다.
    private HumanoidBridgeRobotAckResponse ApplyBaseWaypointCommand(
        HumanoidBridgeRobotCommandRequest request,
        string activeScene,
        GameObject targetObject,
        NavMeshAgent targetAgent
    )
    {
        var hasAbsoluteTargetPosition =
            request.action.target_position != null && request.action.target_position.Length > 0;
        var hasAbsoluteTargetRotation =
            request.action.target_rotation != null && request.action.target_rotation.Length > 0;

        var waypointPosition = hasAbsoluteTargetPosition
            ? ToVector3(request.action.target_position)
            : ToVector3(request.action.translation);
        var waypointRotation = hasAbsoluteTargetRotation
            ? ToVector3(request.action.target_rotation)
            : ToVector3(request.action.rotation);

        if (!hasAbsoluteTargetPosition &&
            waypointPosition.magnitude < minTranslationMagnitude &&
            waypointRotation.magnitude < 0.0001f)
        {
            return Fail(request.request_id, activeScene, targetObject.name, "Waypoint is too small", request.command);
        }

        var resolvedPosition = targetObject.transform.position;
        if (hasAbsoluteTargetPosition)
        {
            string error;
            if (!TryMoveTargetPosition(
                targetObject,
                targetAgent,
                waypointPosition,
                Mathf.Max(0.1f, request.action.speed),
                out resolvedPosition,
                out error))
            {
                return Fail(request.request_id, activeScene, targetObject.name, error, request.command);
            }
        }
        else if (waypointPosition.magnitude >= minTranslationMagnitude)
        {
            var worldDelta = translationSpace == TranslationSpace.Self
                ? targetObject.transform.TransformDirection(waypointPosition * translationScale)
                : waypointPosition * translationScale;

            string error;
            if (!TryMoveTargetDelta(
                targetObject,
                targetAgent,
                worldDelta,
                Mathf.Max(0.1f, request.action.speed),
                out resolvedPosition,
                out error))
            {
                return Fail(request.request_id, activeScene, targetObject.name, error, request.command);
            }
        }

        if (applyRotationDelta && waypointRotation.magnitude > 0.0001f)
        {
            targetObject.transform.eulerAngles = waypointRotation * rotationScale;
        }

        return new HumanoidBridgeRobotAckResponse
        {
            ok = true,
            request_id = request.request_id,
            applied = true,
            message =
                $"waypoint=({resolvedPosition.x:0.00}, {resolvedPosition.y:0.00}, {resolvedPosition.z:0.00}), " +
                $"rotation=({targetObject.transform.eulerAngles.x:0.00}, {targetObject.transform.eulerAngles.y:0.00}, {targetObject.transform.eulerAngles.z:0.00})",
            error = "",
            scene = activeScene,
            target = targetObject.name,
            command = request.command,
        };
    }

    // apply_joint_targets/apply_joint_deltas/apply_joint_velocities 공통 처리입니다.
    // useDelta/useVelocity 플래그로 절대 목표, 상대 변화량, 속도 명령을 구분합니다.
    private HumanoidBridgeRobotAckResponse ApplyJointTargetsCommand(
        HumanoidBridgeRobotCommandRequest request,
        string activeScene,
        GameObject targetObject,
        bool useDelta,
        bool useVelocity
    )
    {
        var joints = ResolveArticulatedJoints(targetObject);
        if (joints.Count == 0)
        {
            return Fail(request.request_id, activeScene, targetObject.name, "No articulated joints configured", request.command);
        }

        var values = ResolveJointCommandValues(request.action, useDelta, useVelocity);
        if (values == null || values.Length == 0)
        {
            return Fail(request.request_id, activeScene, targetObject.name, "Joint command values are empty", request.command);
        }

        var appliedCount = 0;
        var count = Mathf.Min(joints.Count, values.Length);
        for (var i = 0; i < count; i++)
        {
            var joint = joints[i];
            if (joint == null)
            {
                continue;
            }

            var drive = joint.xDrive;
            var value = values[i] * jointCommandScale;
            if (useVelocity)
            {
                drive.targetVelocity = value;
            }
            else if (useDelta)
            {
                drive.target += value;
            }
            else
            {
                drive.target = value;
            }

            joint.xDrive = drive;
            appliedCount += 1;
        }

        if (appliedCount <= 0)
        {
            return Fail(request.request_id, activeScene, targetObject.name, "No joints were updated", request.command);
        }

        return new HumanoidBridgeRobotAckResponse
        {
            ok = true,
            request_id = request.request_id,
            applied = true,
            message = $"Updated {appliedCount} articulated joints",
            error = "",
            scene = activeScene,
            target = targetObject.name,
            command = request.command,
        };
    }

    // 월드 좌표 이동 delta를 실제 대상에 적용합니다.
    // NavMeshAgent가 있으면 NavMesh 위 목표점으로 이동시키고, 없으면 Transform을 직접 이동합니다.
    private bool TryMoveTargetDelta(
        GameObject targetObject,
        NavMeshAgent targetAgent,
        Vector3 worldDelta,
        float speed,
        out Vector3 resolvedPosition,
        out string error
    )
    {
        resolvedPosition = targetObject != null ? targetObject.transform.position : Vector3.zero;
        error = "";

        if (targetObject == null)
        {
            error = "Target object is null";
            return false;
        }

        if (worldDelta.magnitude < minTranslationMagnitude)
        {
            error = "Move magnitude too small";
            return false;
        }

        var nextPoint = targetObject.transform.position + worldDelta;

        if (preferNavMeshAgent && targetAgent != null)
        {
            NavMeshHit hit;
            if (!NavMesh.SamplePosition(nextPoint, out hit, navSampleRadius, NavMesh.AllAreas))
            {
                error = "NavMesh.SamplePosition failed";
                return false;
            }

            if (speed > 0.0f)
            {
                targetAgent.speed = Mathf.Max(0.1f, speed);
            }

            if (!targetAgent.SetDestination(hit.position))
            {
                error = "SetDestination failed";
                return false;
            }

            resolvedPosition = hit.position;
            return true;
        }

        targetObject.transform.position = nextPoint;
        resolvedPosition = nextPoint;
        return true;
    }

    // 절대 월드 목표 좌표를 실제 대상에 적용합니다.
    // NavMeshAgent가 있으면 목적지로 설정하고, 없으면 Transform 위치를 직접 맞춥니다.
    private bool TryMoveTargetPosition(
        GameObject targetObject,
        NavMeshAgent targetAgent,
        Vector3 targetPosition,
        float speed,
        out Vector3 resolvedPosition,
        out string error
    )
    {
        resolvedPosition = targetObject != null ? targetObject.transform.position : Vector3.zero;
        error = "";

        if (targetObject == null)
        {
            error = "Target object is null";
            return false;
        }

        if (Vector3.Distance(targetObject.transform.position, targetPosition) < minTranslationMagnitude)
        {
            resolvedPosition = targetPosition;
            return true;
        }

        if (preferNavMeshAgent && targetAgent != null)
        {
            NavMeshHit hit;
            if (!NavMesh.SamplePosition(targetPosition, out hit, navSampleRadius, NavMesh.AllAreas))
            {
                error = "NavMesh.SamplePosition failed";
                return false;
            }

            if (speed > 0.0f)
            {
                targetAgent.speed = Mathf.Max(0.1f, speed);
            }

            if (!targetAgent.SetDestination(hit.position))
            {
                error = "SetDestination failed";
                return false;
            }

            resolvedPosition = hit.position;
            return true;
        }

        targetObject.transform.position = targetPosition;
        resolvedPosition = targetPosition;
        return true;
    }

    // 조인트 명령을 적용할 ArticulationBody 목록을 찾습니다.
    // Inspector 배열이 있으면 그것을 우선하고, 없으면 targetObject 하위에서 자동 탐색합니다.
    private List<ArticulationBody> ResolveArticulatedJoints(GameObject targetObject)
    {
        var joints = new List<ArticulationBody>();
        if (articulatedJoints != null && articulatedJoints.Length > 0)
        {
            foreach (var body in articulatedJoints)
            {
                if (body == null || body.jointType == ArticulationJointType.FixedJoint)
                {
                    continue;
                }

                joints.Add(body);
            }
        }

        if (joints.Count > 0)
        {
            return joints;
        }

        if (targetObject == null)
        {
            return joints;
        }

        var discovered = targetObject.GetComponentsInChildren<ArticulationBody>(true);
        foreach (var body in discovered)
        {
            if (body == null || body.jointType == ArticulationJointType.FixedJoint)
            {
                continue;
            }

            joints.Add(body);
        }

        return joints;
    }

    // 명령 타입에 맞는 조인트 값 배열을 선택합니다.
    // velocity -> joint_velocities, delta -> joint_deltas, target -> joint_targets/joint_positions 순서입니다.
    private float[] ResolveJointCommandValues(
        HumanoidBridgeRobotAction action,
        bool useDelta,
        bool useVelocity
    )
    {
        if (action == null)
        {
            return new float[0];
        }

        if (useVelocity)
        {
            return action.joint_velocities ?? new float[0];
        }

        if (useDelta)
        {
            return action.joint_deltas ?? new float[0];
        }

        if (action.joint_targets != null && action.joint_targets.Length > 0)
        {
            return action.joint_targets;
        }

        if (action.joint_positions != null && action.joint_positions.Length > 0)
        {
            return action.joint_positions;
        }

        return new float[0];
    }

    // 현재 대상 오브젝트의 위치/회전/조인트/그리퍼 상태를 백엔드가 읽을 수 있는 state 메시지로 만듭니다.
    private HumanoidBridgeRobotState BuildRobotStateMessage(
        string requestId,
        string targetName,
        string sceneName
    )
    {
        var targetObject = ResolveTargetObject(targetName);
        var targetTransform = targetObject != null ? targetObject.transform : ResolveFallbackTransform();
        if (targetTransform == null)
        {
            return null;
        }

        var position = targetTransform.position;
        var rotation = targetTransform.eulerAngles;
        var targetAgent = ResolveAgent(targetObject);
        var velocity = targetAgent != null ? targetAgent.velocity : Vector3.zero;
        var jointValues = ResolveCurrentJointPositions(targetObject);
        var hasGoal = goal != null;
        var goalPosition = hasGoal ? goal.position : Vector3.zero;
        return new HumanoidBridgeRobotState
        {
            request_id = requestId ?? "",
            scene = string.IsNullOrWhiteSpace(sceneName) ? SceneManager.GetActiveScene().name : sceneName,
            object_name = targetObject != null ? targetObject.name : targetTransform.name,
            client_id = string.IsNullOrWhiteSpace(stateClientId) ? "default" : stateClientId.Trim(),
            robot_type = _activeRobotType,
            controller_mode = _activeControllerMode,
            position = new float[] { position.x, position.y, position.z },
            rotation = new float[] { rotation.x, rotation.y, rotation.z },
            velocity = new float[] { velocity.x, velocity.y, velocity.z },
            joint_positions = jointValues,
            gripper_open = gripperOpen,
            eef_pose = new float[] { position.x, position.y, position.z, rotation.x, rotation.y, rotation.z },
            goal_position = hasGoal ? new float[] { goalPosition.x, goalPosition.y, goalPosition.z } : new float[0],
            distance_to_goal = hasGoal ? Vector3.Distance(position, goalPosition) : -1.0f,
            has_line_of_sight = hasGoal && HasLineOfSightToGoal(targetTransform),
            stuck = IsStuck(targetAgent),
            timestamp = Time.realtimeSinceStartup,
        };
    }

    // command 요청에서 지정한 대상 오브젝트를 찾습니다.
    // 이름이 비어 있으면 현재 fallback 제어 대상을 사용합니다.
    private GameObject ResolveCommandTargetObject(string targetName)
    {
        if (string.IsNullOrWhiteSpace(targetName))
        {
            var fallback = ResolveFallbackTransform();
            return fallback != null ? fallback.gameObject : null;
        }

        return GameObject.Find(targetName);
    }

    // 상태 생성용 대상 오브젝트를 찾습니다.
    // 지정 이름을 먼저 찾고, 없으면 현재 제어 대상으로 fallback합니다.
    private GameObject ResolveTargetObject(string targetName)
    {
        if (!string.IsNullOrWhiteSpace(targetName))
        {
            var found = GameObject.Find(targetName);
            if (found != null)
            {
                return found;
            }
        }

        var fallback = ResolveFallbackTransform();
        return fallback != null ? fallback.gameObject : null;
    }

    // 명시 제어 대상이 없을 때 사용할 Transform을 결정합니다.
    // controlledTransform -> agent.transform -> 이 컴포넌트 transform 순서입니다.
    private Transform ResolveFallbackTransform()
    {
        if (controlledTransform != null)
        {
            return controlledTransform;
        }

        if (agent != null)
        {
            return agent.transform;
        }

        return transform;
    }

    // 현재 명령 대상에 사용할 NavMeshAgent를 결정합니다.
    // preferNavMeshAgent가 켜져 있으면 대상 오브젝트의 Agent를 우선 탐색합니다.
    private NavMeshAgent ResolveAgent(GameObject targetObject)
    {
        if (preferNavMeshAgent)
        {
            if (agent != null && targetObject != null && agent.gameObject == targetObject)
            {
                return agent;
            }

            if (targetObject != null)
            {
                var targetAgent = targetObject.GetComponent<NavMeshAgent>();
                if (targetAgent != null)
                {
                    return targetAgent;
                }
            }
        }

        return agent;
    }

    // 요청된 target 이름, Inspector 기본 target, fallback Transform 이름 순서로 대상 이름을 정합니다.
    private string ResolveTargetName(string requestedName)
    {
        if (!string.IsNullOrWhiteSpace(requestedName))
        {
            return requestedName.Trim();
        }

        if (!string.IsNullOrWhiteSpace(defaultTargetObject))
        {
            return defaultTargetObject.Trim();
        }

        var fallback = ResolveFallbackTransform();
        return fallback != null ? fallback.name : "RobotKyle";
    }

    // 현재 상태 전송에 사용할 활성 대상 이름을 반환합니다.
    private string ResolveActiveTargetName()
    {
        if (controlledTransform != null)
        {
            return controlledTransform.name;
        }

        return ResolveTargetName(defaultTargetObject);
    }

    // 현재 ArticulationBody 조인트 위치값을 배열로 읽습니다.
    private float[] ResolveCurrentJointPositions(GameObject targetObject)
    {
        var joints = ResolveArticulatedJoints(targetObject);
        if (joints.Count == 0)
        {
            return new float[0];
        }

        var values = new float[joints.Count];
        for (var i = 0; i < joints.Count; i++)
        {
            var joint = joints[i];
            values[i] = joint != null ? joint.jointPosition[0] : 0f;
        }

        return values;
    }

    // 문자열 그리퍼 명령을 내부 bool 상태로 반영합니다.
    private void UpdateGripperState(string gripper)
    {
        if (string.IsNullOrWhiteSpace(gripper))
        {
            return;
        }

        var normalized = gripper.Trim().ToLowerInvariant();
        if (normalized == "open" || normalized == "opened")
        {
            gripperOpen = true;
        }
        else if (normalized == "close" || normalized == "closed")
        {
            gripperOpen = false;
        }
    }

    // 직접 VLA 요청용 진단값입니다. 현재 대상에서 goal까지 장애물 없는 시야가 있는지 Raycast로 확인합니다.
    private bool HasLineOfSightToGoal(Transform targetTransform)
    {
        if (targetTransform == null || goal == null)
        {
            return false;
        }

        var origin = targetTransform.position + Vector3.up * 1.0f;
        var target = goal.position + Vector3.up * 1.0f;
        var direction = target - origin;
        var distance = direction.magnitude;

        if (distance <= 0.001f)
        {
            return true;
        }

        RaycastHit hit;
        if (Physics.Raycast(origin, direction.normalized, out hit, distance))
        {
            return hit.transform == goal || hit.transform.IsChildOf(goal);
        }

        return true;
    }

    // 직접 VLA 요청용 진단값입니다. 속도는 낮은데 남은 거리가 크면 stuck으로 간주합니다.
    private bool IsStuck(NavMeshAgent targetAgent)
    {
        if (targetAgent == null)
        {
            return false;
        }

        return targetAgent.velocity.magnitude < stuckVelocityThreshold &&
               targetAgent.remainingDistance > stuckDistanceThreshold;
    }

    // 선택적으로 simCamera 화면을 JPEG로 캡처해 base64 문자열로 반환합니다.
    // includeCameraImage가 꺼져 있으면 빈 문자열을 반환합니다.
    private string CaptureCameraImageBase64(bool ignoreIncludeFlag = false)
    {
        if ((!includeCameraImage && !ignoreIncludeFlag) || simCamera == null)
        {
            return "";
        }

        var width = Mathf.Max(16, cameraCaptureWidth);
        var height = Mathf.Max(16, cameraCaptureHeight);
        var quality = Mathf.Clamp(cameraJpegQuality, 1, 100);

        var previousTarget = simCamera.targetTexture;
        var previousActive = RenderTexture.active;
        var tempTexture = RenderTexture.GetTemporary(width, height, 24, RenderTextureFormat.ARGB32);
        Texture2D readback = null;

        try
        {
            simCamera.targetTexture = tempTexture;
            simCamera.Render();
            RenderTexture.active = tempTexture;

            readback = new Texture2D(width, height, TextureFormat.RGB24, false);
            readback.ReadPixels(new Rect(0f, 0f, width, height), 0, 0, false);
            readback.Apply(false, false);

            var bytes = readback.EncodeToJPG(quality);
            return bytes != null && bytes.Length > 0 ? Convert.ToBase64String(bytes) : "";
        }
        catch (Exception ex)
        {
            AppendRecentEvent("Camera capture failed: " + ex.Message);
            return "";
        }
        finally
        {
            simCamera.targetTexture = previousTarget;
            RenderTexture.active = previousActive;
            if (readback != null)
            {
                if (Application.isPlaying)
                {
                    Destroy(readback);
                }
                else
                {
                    DestroyImmediate(readback);
                }
            }
            RenderTexture.ReleaseTemporary(tempTexture);
        }
    }

    // Read any Unity Texture as a JPEG and return it as base64.
    private string CaptureTextureImageBase64(Texture sourceTexture)
    {
        if (sourceTexture == null)
        {
            return "";
        }

        var renderTexture = sourceTexture as RenderTexture;
        var temporary = false;
        if (renderTexture == null)
        {
            var width = Mathf.Max(16, sourceTexture.width);
            var height = Mathf.Max(16, sourceTexture.height);
            renderTexture = RenderTexture.GetTemporary(width, height, 0, RenderTextureFormat.ARGB32);
            Graphics.Blit(sourceTexture, renderTexture);
            temporary = true;
        }

        var previousActive = RenderTexture.active;
        Texture2D readback = null;

        try
        {
            RenderTexture.active = renderTexture;
            readback = new Texture2D(renderTexture.width, renderTexture.height, TextureFormat.RGB24, false);
            readback.ReadPixels(new Rect(0f, 0f, renderTexture.width, renderTexture.height), 0, 0, false);
            readback.Apply(false, false);

            var quality = Mathf.Clamp(cameraJpegQuality, 1, 100);
            var bytes = readback.EncodeToJPG(quality);
            return bytes != null && bytes.Length > 0 ? Convert.ToBase64String(bytes) : "";
        }
        catch (Exception ex)
        {
            AppendRecentEvent("RawImage capture failed: " + ex.Message);
            return "";
        }
        finally
        {
            RenderTexture.active = previousActive;
            if (readback != null)
            {
                if (Application.isPlaying)
                {
                    Destroy(readback);
                }
                else
                {
                    DestroyImmediate(readback);
                }
            }

            if (temporary && renderTexture != null)
            {
                RenderTexture.ReleaseTemporary(renderTexture);
            }
        }
    }

    // Prefer the configured RawImage texture and fall back to simCamera capture.
    private string CaptureConfiguredImageBase64()
    {
        if (imageSourceRawImage != null && imageSourceRawImage.texture != null)
        {
            var rawImageBase64 = CaptureTextureImageBase64(imageSourceRawImage.texture);
            if (!string.IsNullOrWhiteSpace(rawImageBase64))
            {
                return rawImageBase64;
            }
        }

        EnsureImageCamera();
        return CaptureCameraImageBase64(true);
    }

    private void EnsureImageCamera()
    {
        if (simCamera != null || !autoUseMainCameraForImage)
        {
            return;
        }

        simCamera = Camera.main;
        if (simCamera != null && Application.isPlaying)
        {
            AppendRecentEvent($"Image camera auto-selected: {simCamera.name}");
        }
    }

    // Build one websocket payload that the Remote Image Sensor node can display directly.
    private HumanoidBridgeImageFrame BuildImageFrameMessage()
    {
        var encoded = CaptureConfiguredImageBase64();
        if (string.IsNullOrWhiteSpace(encoded))
        {
            return null;
        }

        var sourceTexture = imageSourceRawImage != null ? imageSourceRawImage.texture : null;
        var width = sourceTexture != null ? sourceTexture.width : Mathf.Max(16, cameraCaptureWidth);
        var height = sourceTexture != null ? sourceTexture.height : Mathf.Max(16, cameraCaptureHeight);
        var clientId = string.IsNullOrWhiteSpace(imageClientId) ? "default" : imageClientId.Trim();
        var sceneName = SceneManager.GetActiveScene().name;
        var objectName = ResolveActiveTargetName();

        return new HumanoidBridgeImageFrame
        {
            client_id = clientId,
            scene = sceneName,
            object_name = objectName,
            width = width,
            height = height,
            timestamp = Time.time,
            image = "data:image/jpeg;base64," + encoded,
        };
    }

    [ContextMenu("Create Virtual LiDAR Sensor")]
    // Create a scene child object that acts as the LiDAR mount point.
    public void CreateVirtualLidarSensor()
    {
        EnsureVirtualLidarOrigin(true);
    }

    private Transform ResolveLidarOriginTransform(Transform fallbackTarget)
    {
        if (lidarOrigin != null)
        {
            return lidarOrigin;
        }

        var created = EnsureVirtualLidarOrigin(false);
        if (created != null)
        {
            return created;
        }

        return fallbackTarget;
    }

    private Transform EnsureVirtualLidarOrigin(bool forceCreate)
    {
        if (lidarOrigin != null)
        {
            return lidarOrigin;
        }

        if (!forceCreate && !autoCreateVirtualLidar)
        {
            return null;
        }

        var parent = ResolveFallbackTransform();
        if (parent == null)
        {
            return null;
        }

        var objectName = string.IsNullOrWhiteSpace(virtualLidarObjectName)
            ? "VirtualLiDAR"
            : virtualLidarObjectName.Trim();
        var existing = parent.Find(objectName);
        if (existing != null)
        {
            lidarOrigin = existing;
            return lidarOrigin;
        }

        var sensorObject = new GameObject(objectName);
        lidarOrigin = sensorObject.transform;
        lidarOrigin.SetParent(parent, false);
        lidarOrigin.localPosition = virtualLidarLocalPosition;
        lidarOrigin.localRotation = Quaternion.Euler(virtualLidarLocalEulerAngles);

        if (Application.isPlaying)
        {
            AppendRecentEvent($"Virtual LiDAR created: {parent.name}/{objectName}");
        }
        else
        {
            Debug.Log($"[UnityHumanoidBridge] Virtual LiDAR created: {parent.name}/{objectName}");
        }

        return lidarOrigin;
    }

    // Build a lightweight 2D laser scan from Unity Physics raycasts.
    private HumanoidBridgeLidarFrame BuildLidarFrameMessage(string targetName, string sceneName)
    {
        var targetObject = ResolveTargetObject(targetName);
        var targetTransform = targetObject != null ? targetObject.transform : ResolveFallbackTransform();
        var originTransform = ResolveLidarOriginTransform(targetTransform);
        if (originTransform == null)
        {
            return null;
        }

        var count = Mathf.Clamp(lidarRayCount, 1, 4096);
        var fovDeg = Mathf.Clamp(lidarHorizontalFovDeg, 0.0f, 360.0f);
        var maxRange = Mathf.Max(0.01f, lidarMaxRange);
        var minValidRange = Mathf.Clamp(lidarMinRange, 0.0f, maxRange);
        var originPosition = lidarOrigin != null
            ? originTransform.position
            : originTransform.position + Vector3.up * lidarHeightOffset;

        var ranges = new float[count];
        var pointsFlat = new float[count * 3];
        var hitNames = new string[count];
        var minObserved = maxRange;
        var maxObserved = 0.0f;

        var halfFov = fovDeg * 0.5f;
        var incrementDeg = count > 1 ? fovDeg / (count - 1) : 0.0f;
        var pitchedForward = Quaternion.AngleAxis(lidarPitchDeg, originTransform.right) * originTransform.forward;

        for (var i = 0; i < count; i++)
        {
            var yawDeg = count > 1 ? -halfFov + incrementDeg * i : 0.0f;
            var direction = Quaternion.AngleAxis(yawDeg, originTransform.up) * pitchedForward;
            direction.Normalize();

            RaycastHit hit;
            var hitSomething = TryCastLidarRay(originPosition, direction, targetTransform, out hit);
            var distance = hitSomething ? Mathf.Clamp(hit.distance, minValidRange, maxRange) : maxRange;
            var endpoint = hitSomething ? hit.point : originPosition + direction * maxRange;

            ranges[i] = distance;
            pointsFlat[i * 3] = endpoint.x;
            pointsFlat[i * 3 + 1] = endpoint.y;
            pointsFlat[i * 3 + 2] = endpoint.z;
            hitNames[i] = hitSomething && hit.collider != null ? hit.collider.name : "";

            minObserved = Mathf.Min(minObserved, distance);
            maxObserved = Mathf.Max(maxObserved, distance);

            if (lidarDrawDebugRays)
            {
                Debug.DrawRay(
                    originPosition,
                    direction * distance,
                    hitSomething ? Color.cyan : new Color(0.35f, 0.35f, 0.35f),
                    Mathf.Max(0.02f, lidarSendIntervalSec)
                );
            }
        }

        var rotation = originTransform.eulerAngles;
        var clientId = string.IsNullOrWhiteSpace(lidarClientId) ? "default" : lidarClientId.Trim();
        var frameId = string.IsNullOrWhiteSpace(lidarFrameId) ? "humanoid_lidar" : lidarFrameId.Trim();
        var resolvedScene = string.IsNullOrWhiteSpace(sceneName) ? SceneManager.GetActiveScene().name : sceneName;
        var resolvedObject = targetObject != null ? targetObject.name : originTransform.name;

        return new HumanoidBridgeLidarFrame
        {
            client_id = clientId,
            scene = resolvedScene,
            object_name = resolvedObject,
            frame_id = frameId,
            origin = ToArray(originPosition),
            rotation = new float[] { rotation.x, rotation.y, rotation.z },
            forward = ToArray(originTransform.forward),
            range_count = count,
            angle_min = -halfFov * Mathf.Deg2Rad,
            angle_max = halfFov * Mathf.Deg2Rad,
            angle_increment = incrementDeg * Mathf.Deg2Rad,
            range_min = minValidRange,
            range_max = maxRange,
            min_range = minObserved,
            max_observed_range = maxObserved <= 0.0f ? maxRange : maxObserved,
            timestamp = Time.time,
            ranges = ranges,
            points_flat = pointsFlat,
            hit_names = hitNames,
        };
    }

    private bool TryCastLidarRay(
        Vector3 originPosition,
        Vector3 direction,
        Transform targetTransform,
        out RaycastHit bestHit
    )
    {
        bestHit = new RaycastHit();
        var triggerMode = lidarIgnoreTriggers ? QueryTriggerInteraction.Ignore : QueryTriggerInteraction.Collide;
        var hits = Physics.RaycastAll(originPosition, direction, Mathf.Max(0.01f, lidarMaxRange), lidarLayerMask, triggerMode);
        var found = false;
        var bestDistance = Mathf.Max(0.01f, lidarMaxRange);

        for (var i = 0; i < hits.Length; i++)
        {
            var hit = hits[i];
            if (hit.distance < lidarMinRange || hit.distance > bestDistance)
            {
                continue;
            }

            if (targetTransform != null &&
                hit.transform != null &&
                (hit.transform == targetTransform || hit.transform.IsChildOf(targetTransform)))
            {
                continue;
            }

            found = true;
            bestDistance = hit.distance;
            bestHit = hit;
        }

        return found;
    }

    // Sample the same LiDAR raycast fan used for streaming and return a local avoidance direction.
    // The returned vector is a world-space horizontal direction that points toward the clearer side.
    public bool TryGetLidarAvoidance(
        Transform targetTransform,
        Vector3 desiredDirection,
        float avoidDistance,
        float hardAvoidDistance,
        out Vector3 avoidanceDirection,
        out float nearestDistance,
        out bool hardAvoid
    )
    {
        avoidanceDirection = Vector3.zero;
        nearestDistance = Mathf.Max(0.01f, avoidDistance);
        hardAvoid = false;

        var fallbackTarget = targetTransform != null ? targetTransform : ResolveFallbackTransform();
        var originTransform = ResolveLidarOriginTransform(fallbackTarget);
        if (originTransform == null)
        {
            return false;
        }

        var scanForward = desiredDirection;
        scanForward.y = 0.0f;
        if (scanForward.sqrMagnitude < 0.0001f)
        {
            scanForward = originTransform.forward;
            scanForward.y = 0.0f;
        }

        if (scanForward.sqrMagnitude < 0.0001f)
        {
            return false;
        }

        scanForward.Normalize();

        var originPosition = lidarOrigin != null
            ? originTransform.position
            : originTransform.position + Vector3.up * lidarHeightOffset;
        var count = Mathf.Clamp(lidarRayCount, 3, 4096);
        var fovDeg = Mathf.Clamp(lidarHorizontalFovDeg, 1.0f, 360.0f);
        var scanDistance = Mathf.Max(0.01f, Mathf.Min(Mathf.Max(0.01f, lidarMaxRange), Mathf.Max(0.01f, avoidDistance)));
        var reactDistance = Mathf.Max(0.01f, avoidDistance);
        var hardDistance = Mathf.Clamp(hardAvoidDistance, 0.0f, reactDistance);
        var halfFov = fovDeg * 0.5f;
        var incrementDeg = count > 1 ? fovDeg / (count - 1) : 0.0f;
        var scanRight = Vector3.Cross(Vector3.up, scanForward);
        if (scanRight.sqrMagnitude < 0.0001f)
        {
            scanRight = originTransform.right;
            scanRight.y = 0.0f;
        }

        scanRight.Normalize();

        var pitchedForward = Quaternion.AngleAxis(lidarPitchDeg, scanRight) * scanForward;
        var leftClearance = 0.0f;
        var rightClearance = 0.0f;
        var steering = 0.0f;
        var frontPressure = 0.0f;
        var foundObstacle = false;

        for (var i = 0; i < count; i++)
        {
            var yawDeg = count > 1 ? -halfFov + incrementDeg * i : 0.0f;
            var direction = Quaternion.AngleAxis(yawDeg, Vector3.up) * pitchedForward;
            direction.Normalize();

            RaycastHit hit;
            var hitSomething = TryCastLidarRay(originPosition, direction, fallbackTarget, out hit);
            var distance = hitSomething ? Mathf.Min(hit.distance, scanDistance) : scanDistance;

            if (yawDeg < -0.001f)
            {
                leftClearance += distance;
            }
            else if (yawDeg > 0.001f)
            {
                rightClearance += distance;
            }

            if (!hitSomething || hit.distance > reactDistance)
            {
                continue;
            }

            foundObstacle = true;
            nearestDistance = Mathf.Min(nearestDistance, hit.distance);

            var centeredWeight = 1.0f - Mathf.Clamp01(Mathf.Abs(yawDeg) / Mathf.Max(1.0f, halfFov));
            var closenessWeight = 1.0f - Mathf.Clamp01(hit.distance / reactDistance);
            var weight = Mathf.Max(0.0f, closenessWeight) * (0.35f + centeredWeight * 0.65f);

            if (Mathf.Abs(yawDeg) <= Mathf.Max(5.0f, halfFov * 0.12f))
            {
                frontPressure += weight;
            }
            else
            {
                steering += -Mathf.Sign(yawDeg) * weight;
            }
        }

        if (!foundObstacle)
        {
            nearestDistance = scanDistance;
            return false;
        }

        hardAvoid = hardDistance > 0.0f && nearestDistance <= hardDistance;
        if (Mathf.Abs(steering) < 0.05f && (frontPressure > 0.0f || hardAvoid))
        {
            steering = rightClearance >= leftClearance ? 1.0f : -1.0f;
        }

        var lateral = Vector3.Cross(Vector3.up, scanForward).normalized * Mathf.Clamp(steering, -1.0f, 1.0f);
        avoidanceDirection = lateral;
        if (frontPressure > 0.0f)
        {
            avoidanceDirection = (avoidanceDirection + lateral * frontPressure).normalized;
        }

        return avoidanceDirection.sqrMagnitude > 0.0001f;
    }

    private void UpdateLidarSummaries(HumanoidBridgeLidarFrame frame)
    {
        if (frame == null)
        {
            return;
        }

        lastLidarSummary =
            $"points={frame.range_count}, min={frame.min_range:0.00}, max={frame.max_observed_range:0.00}, " +
            $"fov={lidarHorizontalFovDeg:0}, range={frame.range_max:0.0}";
        lastLidarHitSummary = BuildLidarHitSummary(frame, maxLidarOverlayHitObjects);
    }

    private static string BuildLidarHitSummary(HumanoidBridgeLidarFrame frame, int maxItems)
    {
        if (frame == null || frame.hit_names == null || frame.ranges == null)
        {
            return "No LiDAR hits yet.";
        }

        var nearestByName = new Dictionary<string, float>();
        var countByName = new Dictionary<string, int>();

        for (var i = 0; i < frame.hit_names.Length && i < frame.ranges.Length; i++)
        {
            var rawName = frame.hit_names[i];
            if (string.IsNullOrWhiteSpace(rawName))
            {
                continue;
            }

            var name = rawName.Trim();
            var range = frame.ranges[i];
            if (!nearestByName.ContainsKey(name) || range < nearestByName[name])
            {
                nearestByName[name] = range;
            }

            countByName[name] = countByName.ContainsKey(name) ? countByName[name] + 1 : 1;
        }

        if (nearestByName.Count == 0)
        {
            return "No object hit by LiDAR.";
        }

        var names = new List<string>(nearestByName.Keys);
        names.Sort((left, right) => nearestByName[left].CompareTo(nearestByName[right]));

        var builder = new StringBuilder();
        var limit = Mathf.Clamp(maxItems, 1, 32);
        var displayed = Mathf.Min(limit, names.Count);

        builder.Append("Hit objects: ");
        builder.Append(names.Count);
        builder.AppendLine();

        for (var i = 0; i < displayed; i++)
        {
            var name = names[i];
            builder.Append(i + 1);
            builder.Append(". ");
            builder.Append(name);
            builder.Append("  ");
            builder.Append(nearestByName[name].ToString("0.00"));
            builder.Append("m");
            builder.Append("  rays=");
            builder.Append(countByName[name]);
            builder.AppendLine();
        }

        if (names.Count > displayed)
        {
            builder.Append("+");
            builder.Append(names.Count - displayed);
            builder.Append(" more");
        }

        return builder.ToString().TrimEnd();
    }

    private static float[] ToArray(Vector3 value)
    {
        return new float[] { value.x, value.y, value.z };
    }

    // backendBaseUrl과 stateClientId를 사용해 Unity state websocket URL을 만듭니다.
    // http/https 스킴은 ws/wss로 변환합니다.
    private string BuildStateWebSocketUrl()
    {
        var clientId = string.IsNullOrWhiteSpace(stateClientId) ? "default" : stateClientId.Trim();

        try
        {
            var builder = new UriBuilder(backendBaseUrl.TrimEnd('/'));
            builder.Scheme = string.Equals(builder.Scheme, Uri.UriSchemeHttps, StringComparison.OrdinalIgnoreCase)
                ? "wss"
                : "ws";
            builder.Path = "/ws/unity/state";
            builder.Query = $"client_id={Uri.EscapeDataString(clientId)}";
            return builder.Uri.ToString();
        }
        catch (Exception ex)
        {
            Debug.LogWarning($"[UnityHumanoidBridge] Failed to build state WS URL: {ex.Message}");
            return $"ws://localhost:9000/ws/unity/state?client_id={Uri.EscapeDataString(clientId)}";
        }
    }


    // Build the backend websocket URL for Unity image streaming.
    private string BuildImageWebSocketUrl()
    {
        var clientId = string.IsNullOrWhiteSpace(imageClientId) ? "default" : imageClientId.Trim();

        try
        {
            var builder = new UriBuilder(backendBaseUrl.TrimEnd('/'));
            builder.Scheme = string.Equals(builder.Scheme, Uri.UriSchemeHttps, StringComparison.OrdinalIgnoreCase)
                ? "wss"
                : "ws";
            builder.Path = "/ws/unity/image";
            builder.Query = $"client_id={Uri.EscapeDataString(clientId)}";
            return builder.Uri.ToString();
        }
        catch (Exception ex)
        {
            Debug.LogWarning($"[UnityHumanoidBridge] Failed to build image WS URL: {ex.Message}");
            return $"ws://localhost:9000/ws/unity/image?client_id={Uri.EscapeDataString(clientId)}";
        }
    }

    // Build the backend websocket URL for Unity LiDAR streaming.
    private string BuildLidarWebSocketUrl()
    {
        var clientId = string.IsNullOrWhiteSpace(lidarClientId) ? "default" : lidarClientId.Trim();

        try
        {
            var builder = new UriBuilder(backendBaseUrl.TrimEnd('/'));
            builder.Scheme = string.Equals(builder.Scheme, Uri.UriSchemeHttps, StringComparison.OrdinalIgnoreCase)
                ? "wss"
                : "ws";
            builder.Path = "/ws/unity/lidar";
            builder.Query = $"client_id={Uri.EscapeDataString(clientId)}";
            return builder.Uri.ToString();
        }
        catch (Exception ex)
        {
            Debug.LogWarning($"[UnityHumanoidBridge] Failed to build LiDAR WS URL: {ex.Message}");
            return $"ws://localhost:9000/ws/unity/lidar?client_id={Uri.EscapeDataString(clientId)}";
        }
    }

    // 수신한 원본 command JSON과 사람이 읽을 요약을 Inspector/overlay에 기록합니다.
    private void RecordIncomingCommand(string rawJson, HumanoidBridgeRobotCommandRequest request)
    {
        receivedCommandCount += 1;
        lastReceivedRawJson = rawJson ?? "";
        lastCommandSummary = BuildCommandSummary(request);
        AppendRecentEvent($"IN  {lastCommandSummary}");
    }

    // 명령 처리 결과 ACK를 overlay 로그에 기록합니다.
    private void RecordCommandOutcome(
        HumanoidBridgeRobotCommandRequest request,
        HumanoidBridgeRobotAckResponse ack
    )
    {
        lastAckSummary = BuildAckSummary(ack);
        AppendRecentEvent($"OUT {lastAckSummary}");
    }

    // Unity에서 만든 최신 로봇 상태 요약을 overlay 로그에 기록합니다.
    private void RecordStateMessage(HumanoidBridgeRobotState state)
    {
        if (state == null)
        {
            return;
        }

        lastStateSummary =
            $"scene={state.scene}, object={state.object_name}, robot={state.robot_type}/{state.controller_mode}, " +
            $"pos=({FormatVector(state.position)}), rot=({FormatVector(state.rotation)}), " +
            $"vel=({FormatVector(state.velocity)}), dist={state.distance_to_goal:0.00}";
        AppendRecentEvent($"STATE {lastStateSummary}");
    }

    // 명령 처리 중 발생한 일반 알림/경고 메시지를 overlay 로그에 기록합니다.
    private void RecordNotice(string message)
    {
        if (string.IsNullOrWhiteSpace(message))
        {
            return;
        }

        lastAckSummary = message;
        AppendRecentEvent($"INFO {message}");
    }

    // 최근 이벤트 큐에 한 줄을 추가하고, Inspector 표시용 문자열과 Unity Console 로그를 갱신합니다.
    private void AppendRecentEvent(string line)
    {
        var timestamped = $"[{DateTime.Now:HH:mm:ss}] {line}";
        _recentEvents.Enqueue(timestamped);

        while (_recentEvents.Count > Mathf.Max(1, maxCommandHistory))
        {
            _recentEvents.Dequeue();
        }

        recentCommandLog = string.Join("\n", _recentEvents.ToArray());
        Debug.Log($"[UnityHumanoidBridge] {line}");
    }

    // robot_command 요청을 짧은 한 줄 요약으로 만듭니다.
    private static string BuildCommandSummary(HumanoidBridgeRobotCommandRequest request)
    {
        if (request == null)
        {
            return "Request is null";
        }

        var translation = FormatVector(request.action != null ? request.action.translation : null);
        var rotation = FormatVector(request.action != null ? request.action.rotation : null);
        var targetPosition = FormatVector(request.action != null ? request.action.target_position : null);
        var targetRotation = FormatVector(request.action != null ? request.action.target_rotation : null);
        var gripper = request.action != null ? request.action.gripper : "noop";
        var terminate = request.action != null && request.action.terminate ? "true" : "false";
        var stop = request.action != null && request.action.stop ? "true" : "false";
        var speed = request.action != null ? request.action.speed : 0f;
        var robotType = string.IsNullOrWhiteSpace(request.robot_type) ? "generic" : request.robot_type;
        var controllerMode = string.IsNullOrWhiteSpace(request.controller_mode) ? "task" : request.controller_mode;

        return
            $"id={request.request_id}, scene={request.scene}, object={request.@object}, robot={robotType}/{controllerMode}, cmd={request.command}, " +
            $"move=({translation}), rot=({rotation}), target=({targetPosition}), targetRot=({targetRotation}), speed={speed:0.00}, gripper={gripper}, stop={stop}, terminate={terminate}";
    }

    // ACK 응답을 짧은 한 줄 요약으로 만듭니다.
    private static string BuildAckSummary(HumanoidBridgeRobotAckResponse ack)
    {
        if (ack == null)
        {
            return "Ack is null";
        }

        var message = string.IsNullOrWhiteSpace(ack.error) ? ack.message : ack.error;
        return
            $"ok={ack.ok}, applied={ack.applied}, scene={ack.scene}, target={ack.target}, " +
            $"cmd={ack.command}, msg={message}";
    }

    // float 배열을 overlay에 표시하기 쉬운 x, y, z 문자열로 포맷합니다.
    private static string FormatVector(float[] values)
    {
        if (values == null || values.Length == 0)
        {
            return "0.00, 0.00, 0.00";
        }

        var x = values.Length > 0 ? values[0] : 0f;
        var y = values.Length > 1 ? values[1] : 0f;
        var z = values.Length > 2 ? values[2] : 0f;
        return $"{x:0.00}, {y:0.00}, {z:0.00}";
    }

    // null/짧은 배열도 안전하게 Vector3로 변환합니다.
    private static Vector3 ToVector3(float[] values)
    {
        if (values == null)
        {
            return Vector3.zero;
        }

        var x = values.Length > 0 ? values[0] : 0f;
        var y = values.Length > 1 ? values[1] : 0f;
        var z = values.Length > 2 ? values[2] : 0f;
        return new Vector3(x, y, z);
    }

    // 실패 ACK를 일관된 형식으로 생성합니다.
    private static HumanoidBridgeRobotAckResponse Fail(
        string requestId,
        string scene,
        string target,
        string error,
        string command
    )
    {
        return new HumanoidBridgeRobotAckResponse
        {
            ok = false,
            request_id = requestId ?? "",
            applied = false,
            message = "Apply failed",
            error = error ?? "Unknown error",
            scene = scene ?? "",
            target = target ?? "",
            command = command ?? "",
        };
    }

    // WebSocket routePath가 항상 /로 시작하도록 정규화합니다.
    private static string NormalizeRoutePath(string rawRoute)
    {
        var trimmed = string.IsNullOrWhiteSpace(rawRoute) ? "/robot" : rawRoute.Trim();
        return trimmed.StartsWith("/") ? trimmed : "/" + trimmed;
    }

    // 긴 JSON/로그 문자열을 overlay에 넣기 좋게 한 줄로 줄입니다.
    private static string TrimForLog(string raw)
    {
        var compact = string.IsNullOrWhiteSpace(raw)
            ? ""
            : string.Join(" ", raw.Split((char[])null, StringSplitOptions.RemoveEmptyEntries));
        return compact.Length > 140 ? compact.Substring(0, 137) + "..." : compact;
    }

    // 런타임 상태를 화면 왼쪽 위 간단한 디버그 overlay로 표시합니다.
    private void OnGUI()
    {
        if (!showCommandOverlay)
        {
            return;
        }

        EnsureOverlayStyles();

        GUILayout.BeginArea(new Rect(12f, 12f, 680f, 620f), _overlayBoxStyle);
        GUILayout.Label("Unity Humanoid Robot Bridge", _overlayTitleStyle);
        GUILayout.Label($"Robot WS Server: {(_server != null ? "running" : "stopped")}", _overlayTextStyle);
        GUILayout.Label($"Active Profile: {_activeRobotType}/{_activeControllerMode}", _overlayTextStyle);
        GUILayout.Label($"Received: {receivedCommandCount}", _overlayTextStyle);
        GUILayout.Label($"Last Command: {lastCommandSummary}", _overlayTextStyle);
        if (enableIdlePatrol || idlePatrolActive)
        {
            GUILayout.Label(
                $"Idle Patrol: {(idlePatrolActive ? "active" : "waiting")} " +
                $"({idleSecondsSinceLastCommand:0.0}/{Mathf.Max(0.1f, idlePatrolDelaySec):0.0}s)",
                _overlayTextStyle
            );
            GUILayout.Label($"Idle Patrol Status: {idlePatrolSummary}", _overlayTextStyle);
            GUILayout.Label($"Player Input: {lastPlayerInputSummary}", _overlayTextStyle);
        }

        if (!string.IsNullOrWhiteSpace(lastAckSummary))
        {
            GUILayout.Label($"Last Ack: {lastAckSummary}", _overlayTextStyle);
        }

        if (!string.IsNullOrWhiteSpace(lastStateSummary))
        {
            GUILayout.Label($"Last State: {lastStateSummary}", _overlayTextStyle);
        }

        GUILayout.Space(6f);
        GUILayout.Label($"State WS: {(IsStateSocketActive() ? "connected" : "disconnected")}", _overlayTextStyle);
        if (sendImageContinuously)
        {
            GUILayout.Label($"Image WS: {(IsImageSocketActive() ? "connected" : "disconnected")}", _overlayTextStyle);
            GUILayout.Label($"Last Image: {lastImageSummary}", _overlayTextStyle);
        }

        if (sendLidarContinuously || sendLidarAfterCommand)
        {
            GUILayout.Label($"LiDAR WS: {(IsLidarSocketActive() ? "connected" : "disconnected")}", _overlayTextStyle);
            GUILayout.Label($"Last LiDAR: {lastLidarSummary}", _overlayTextStyle);
            if (showLidarHitOverlay)
            {
                GUILayout.Label($"LiDAR Hits:\n{lastLidarHitSummary}", _overlayTextStyle);
            }
        }

        if (enableDirectVlaClient)
        {
            GUILayout.Space(6f);
            GUILayout.Label("Direct VLA Client", _overlayTextStyle);
            GUILayout.Label($"VLA WS: {(_isVlaConnected ? "connected" : "disconnected")}", _overlayTextStyle);
            GUILayout.Label($"VLA Requesting: {_isVlaRequesting}", _overlayTextStyle);
            GUILayout.Label($"Last VLA Request: {lastVlaRequestSummary}", _overlayTextStyle);
            GUILayout.Label($"Last VLA Response: {lastVlaResponseSummary}", _overlayTextStyle);
            GUILayout.Label($"Last VLA ACK: {lastVlaAckSummary}", _overlayTextStyle);
        }

        if (!string.IsNullOrWhiteSpace(recentCommandLog))
        {
            GUILayout.Space(6f);
            GUILayout.Label("Recent", _overlayTextStyle);
            _logScrollPos = GUILayout.BeginScrollView(_logScrollPos, GUILayout.Height(130f));
            GUILayout.Label(recentCommandLog, _overlayTextStyle);
            GUILayout.EndScrollView();
        }

        GUILayout.EndArea();
    }

    // OnGUI overlay에서 사용할 GUIStyle을 지연 생성합니다.
    private void EnsureOverlayStyles()
    {
        if (_overlayBoxStyle == null)
        {
            _overlayBoxStyle = new GUIStyle(GUI.skin.box)
            {
                alignment = TextAnchor.UpperLeft,
                padding = new RectOffset(12, 12, 10, 10),
                fontSize = 12,
            };
        }

        if (_overlayTitleStyle == null)
        {
            _overlayTitleStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 14,
                fontStyle = FontStyle.Bold,
                normal = { textColor = Color.white },
            };
        }

        if (_overlayTextStyle == null)
        {
            _overlayTextStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 12,
                wordWrap = true,
                richText = false,
                normal = { textColor = new Color(0.92f, 0.96f, 1.0f) },
            };
        }
    }

    // Scene view helper: visualize the virtual LiDAR mount and scan fan when selected.
    private void OnDrawGizmosSelected()
    {
        var referenceTransform = lidarOrigin != null
            ? lidarOrigin
            : controlledTransform != null
                ? controlledTransform
                : transform;
        if (referenceTransform == null)
        {
            return;
        }

        var originPosition = lidarOrigin != null
            ? referenceTransform.position
            : referenceTransform.TransformPoint(virtualLidarLocalPosition);
        var originRotation = lidarOrigin != null
            ? referenceTransform.rotation
            : referenceTransform.rotation * Quaternion.Euler(virtualLidarLocalEulerAngles);

        var fovDeg = Mathf.Clamp(lidarHorizontalFovDeg, 0.0f, 360.0f);
        var maxRange = Mathf.Max(0.01f, lidarMaxRange);
        var halfFov = fovDeg * 0.5f;
        var sampleCount = Mathf.Clamp(Mathf.Min(lidarRayCount, 17), 1, 17);
        var incrementDeg = sampleCount > 1 ? fovDeg / (sampleCount - 1) : 0.0f;
        var sensorRight = originRotation * Vector3.right;
        var sensorUp = originRotation * Vector3.up;
        var sensorForward = Quaternion.AngleAxis(lidarPitchDeg, sensorRight) * (originRotation * Vector3.forward);

        Gizmos.color = Color.cyan;
        Gizmos.DrawWireSphere(originPosition, 0.06f);

        for (var i = 0; i < sampleCount; i++)
        {
            var yawDeg = sampleCount > 1 ? -halfFov + incrementDeg * i : 0.0f;
            var direction = Quaternion.AngleAxis(yawDeg, sensorUp) * sensorForward;
            direction.Normalize();
            Gizmos.DrawLine(originPosition, originPosition + direction * maxRange);
        }
    }
}

// WebSocketSharp 서버의 실제 세션 처리 클래스입니다.
// 네트워크 스레드에서 메시지를 받되, Unity API 호출은 MainThreadQueue를 통해 메인 스레드에서 실행합니다.
public class HumanoidRobotWsBehavior : WebSocketBehavior
{
    public static Action<Action> Enqueue;
    public static Func<HumanoidBridgeRobotCommandRequest, HumanoidBridgeProcessResult> ProcessRequest;
    public static Action<string, HumanoidBridgeRobotCommandRequest> RecordIncoming;
    public static Action<HumanoidBridgeRobotCommandRequest, HumanoidBridgeRobotAckResponse> RecordOutcome;
    public static Action<HumanoidBridgeRobotState> RecordState;
    public static Action<string> RecordNotice;

    // 백엔드에서 robot_command JSON을 받았을 때 호출됩니다.
    // JSON 파싱 -> 메인 스레드 실행 예약 -> ACK/state 전송 순서로 처리합니다.
    protected override void OnMessage(MessageEventArgs e)
    {
        HumanoidBridgeRobotCommandRequest request = null;

        try
        {
            request = JsonUtility.FromJson<HumanoidBridgeRobotCommandRequest>(e.Data);
        }
        catch (Exception ex)
        {
            Enqueue?.Invoke(() => RecordNotice?.Invoke("Invalid JSON: " + ex.Message));
            SafeSendJson(JsonUtility.ToJson(Fail("", "", "", "Invalid JSON: " + ex.Message, "")));
            return;
        }

        if (request == null)
        {
            Enqueue?.Invoke(() => RecordNotice?.Invoke("Request is null"));
            SafeSendJson(JsonUtility.ToJson(Fail("", "", "", "Request is null", "")));
            return;
        }

        HumanoidBridgeProcessResult result = null;

        // Unity 오브젝트/NavMeshAgent/ArticulationBody 접근은 메인 스레드에서 해야 안전합니다.
        Action processRequest = () =>
        {
            try
            {
                RecordIncoming?.Invoke(e.Data, request);
                result = ProcessRequest != null ? ProcessRequest.Invoke(request) : null;
            }
            catch (Exception ex)
            {
                result = new HumanoidBridgeProcessResult
                {
                    ack = Fail(request.request_id, request.scene, request.@object, ex.Message, request.command),
                    state = null,
                };
            }
        };

        if (UnityHumanoidRobotBridge.IsOnMainThread())
        {
            processRequest();
            SendResult(request, result);
            return;
        }

        var done = new ManualResetEvent(false);
        if (Enqueue != null)
        {
            Enqueue.Invoke(() =>
            {
                try
                {
                    processRequest();
                }
                finally
                {
                    done.Set();
                }
            });
        }
        else
        {
            processRequest();
            done.Set();
        }

        if (!done.WaitOne(15000))
        {
            Enqueue?.Invoke(() => RecordNotice?.Invoke("Main thread execution timed out: " + request.request_id));
            SafeSendJson(
                JsonUtility.ToJson(
                    Fail(request.request_id, request.scene, request.@object, "Main thread execution timed out", request.command)
                )
            );
            return;
        }

        SendResult(request, result);
    }

    // 처리 결과를 WebSocket 클라이언트로 보냅니다.
    // ACK는 항상 먼저 보내고, state가 있으면 이어서 한 번 더 보냅니다.
    private void SendResult(HumanoidBridgeRobotCommandRequest request, HumanoidBridgeProcessResult result)
    {
        if (result == null)
        {
            var errorAck = Fail(request.request_id, request.scene, request.@object, "Result is null", request.command);
            RecordOutcome?.Invoke(request, errorAck);
            SafeSendJson(JsonUtility.ToJson(errorAck));
            return;
        }

        var ack = result.ack;
        var state = result.state;

        if (ack == null)
        {
            ack = Fail(request.request_id, request.scene, request.@object, "Ack is null", request.command);
        }

        RecordOutcome?.Invoke(request, ack);
        SafeSendJson(JsonUtility.ToJson(ack));

        if (state != null)
        {
            RecordState?.Invoke(state);
            SafeSendJson(JsonUtility.ToJson(state));
        }
    }

    // WebSocket이 열려 있을 때만 JSON 문자열을 전송합니다.
    private void SafeSendJson(string json)
    {
        if (State != WebSocketState.Open || string.IsNullOrWhiteSpace(json))
        {
            return;
        }

        Send(json);
    }

    // WebSocketBehavior 내부에서 즉시 실패 응답이 필요할 때 쓰는 ACK 생성 헬퍼입니다.
    private static HumanoidBridgeRobotAckResponse Fail(
        string requestId,
        string scene,
        string target,
        string error,
        string command
    )
    {
        return new HumanoidBridgeRobotAckResponse
        {
            ok = false,
            request_id = requestId ?? "",
            applied = false,
            message = "Apply failed",
            error = error ?? "Unknown error",
            scene = scene ?? "",
            target = target ?? "",
            command = command ?? "",
        };
    }
}
