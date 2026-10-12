using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Networking;

[System.Serializable]
public class UnityRunRobotState
{
    public bool gripper_open = true;
    public float[] eef_pose = new float[] { 0.1f, 0.2f, 0.3f, 0f, 0f, 0f };
    public float[] position = new float[] { 0f, 0f, 0f };
    public float[] rotation = new float[] { 0f, 0f, 0f };
    public float[] velocity = new float[] { 0f, 0f, 0f };
    public float[] goal_position = new float[0];
    public float distance_to_goal = -1.0f;
    public bool has_line_of_sight = false;
    public bool stuck = false;
    public string object_name = "";
    public string robot_type = "generic";
    public string controller_mode = "task";
}

[System.Serializable]
public class UnityRunApiRequest
{
    public string prompt = "Move RobotKyle to CheckpointA at Unity world coordinate [35.0, 0.0, -10.0] using apply_base_waypoint";
    public string image = "/sample.png";
    public UnityRunRobotState robot_state = new UnityRunRobotState();
    public bool use_unity_state = false;
    public string state_client_id = "default";
    public string model_name = "openvla-stub";
    public string decode_mode = "default";
    public bool safety_enabled = true;
    public float safety_max_delta = 0.05f;
    public string unity_endpoint = "ws://host.docker.internal:9081/robot";
    public string unity_scene = "VALConnect";
    public string unity_object = "RobotKyle";
    public string unity_command = "apply_base_waypoint";
    public string action_format = "";
    public float waypoint_speed = 1.5f;
    public string unity_robot_type = "generic";
    public string unity_controller_mode = "task";
    public float unity_timeout_sec = 5f;
}

public class UnityGraphApiClient : MonoBehaviour
{
    [Header("Backend")]
    public string backendBaseUrl = "http://localhost:9000";
    public bool runOnStart = false;
    public bool sendStateContinuously = true;
    public float stateSendIntervalSec = 0.1f;
    public float stateReconnectIntervalSec = 2.0f;
    public bool useUnityStateForRun = true;

    [Header("Graph Input")]
    [TextArea]
    public string prompt = "Move RobotKyle to CheckpointA at Unity world coordinate [35.0, 0.0, -10.0] using apply_base_waypoint";
    public string image = "/sample.png";
    public string modelName = "openvla-stub";
    public bool safetyEnabled = true;
    public float safetyMaxDelta = 0.05f;

    [Header("Robot State")]
    public bool gripperOpen = true;
    public float[] eefPose = new float[] { 0.1f, 0.2f, 0.3f, 0f, 0f, 0f };
    public Transform goal;
    public float stuckVelocityThreshold = 0.05f;
    public float stuckDistanceThreshold = 1.0f;

    [Header("State WebSocket")]
    public string stateClientId = "default";

    private WebSocketSharp.WebSocket _stateSocket;
    private float _nextSendAt = 0f;
    private float _nextReconnectAt = 0f;
    private bool _stateReady = false;
    private bool _pendingRunOnStart = false;

    [Header("Unity Target")]
    public string unityEndpoint = "ws://host.docker.internal:9081/robot";
    public string unityScene = "VALConnect";
    public string unityObject = "RobotKyle";
    public string unityCommand = "apply_base_waypoint";
    public string actionFormat = "";
    public float waypointSpeed = 1.5f;
    public string unityRobotType = "generic";
    public string unityControllerMode = "task";
    public float unityTimeoutSec = 5f;

    [System.Serializable]
    private class UnityStatePayload
    {
        public string type;
        public string client_id;
        public string request_id;
        public float[] position;
        public float[] rotation;
        public bool gripper_open;
        public float[] eef_pose;
        public float[] velocity;
        public float[] goal_position;
        public float distance_to_goal;
        public bool has_line_of_sight;
        public bool stuck;
        public string robot_type;
        public string controller_mode;
        public string scene;
        public string object_name;
        public float timestamp;
    }

    [System.Serializable]
    private class UnityStateAck
    {
        public bool ok;
        public string error;
    }

    private void Start()
    {
        if (sendStateContinuously)
        {
            ConnectStateSocket();
        }

        if (runOnStart)
        {
            if (useUnityStateForRun && sendStateContinuously)
            {
                _pendingRunOnStart = true;
                Debug.Log(
                    "[UnityGraphApiClient] runOnStart is waiting for the first Unity state to be stored."
                );
            }
            else
            {
                RunSampleGraph();
            }
        }
    }

    [ContextMenu("Call Backend Health")]
    public void CallBackendHealth()
    {
        StartCoroutine(GetJson($"{backendBaseUrl.TrimEnd('/')}/health"));
    }

    [ContextMenu("Run Sample Graph")]
    public void RunSampleGraph()
    {
        if (useUnityStateForRun && _stateSocket != null && _stateSocket.IsAlive)
        {
            SendStateOnce();
        }

        var snapshot = BuildRobotStateSnapshot();
        var payload = new UnityRunApiRequest
        {
            prompt = prompt,
            image = image,
            use_unity_state = useUnityStateForRun,
            state_client_id = stateClientId,
            model_name = modelName,
            safety_enabled = safetyEnabled,
            safety_max_delta = safetyMaxDelta,
            unity_endpoint = unityEndpoint,
            unity_scene = unityScene,
            unity_object = unityObject,
            unity_command = unityCommand,
            action_format = actionFormat,
            waypoint_speed = waypointSpeed,
            unity_robot_type = unityRobotType,
            unity_controller_mode = unityControllerMode,
            unity_timeout_sec = unityTimeoutSec,
            robot_state = snapshot,
        };

        if (useUnityStateForRun && (_stateSocket == null || !_stateSocket.IsAlive))
        {
            Debug.LogWarning(
                "[UnityGraphApiClient] useUnityStateForRun is enabled, but the state socket is not connected. " +
                "The backend will use the latest stored Unity state for this client_id, if any."
            );
        }

        var json = JsonUtility.ToJson(payload);
        StartCoroutine(PostJson($"{backendBaseUrl.TrimEnd('/')}/api/unity/run", json));
    }

    private void Update()
    {
        // 재연결 루프
        if (sendStateContinuously && !IsStateSocketActive())
        {
            if (Time.unscaledTime >= _nextReconnectAt)
            {
                _nextReconnectAt = Time.unscaledTime + Mathf.Max(0.5f, stateReconnectIntervalSec);
                Debug.Log("[UnityGraphApiClient] State socket reconnecting...");
                ConnectStateSocket();
            }
        }

        if (sendStateContinuously && _stateSocket != null && _stateSocket.IsAlive)
        {
            if (Time.unscaledTime >= _nextSendAt)
            {
                _nextSendAt = Time.unscaledTime + Mathf.Max(0.02f, stateSendIntervalSec);
                SendStateOnce();
            }
        }

        if (_pendingRunOnStart && (!useUnityStateForRun || _stateReady))
        {
            _pendingRunOnStart = false;
            RunSampleGraph();
        }
    }

    private IEnumerator GetJson(string url)
    {
        using (var request = UnityWebRequest.Get(url))
        {
            yield return request.SendWebRequest();
            LogResponse("GET", url, request);
        }
    }

    private IEnumerator PostJson(string url, string json)
    {
        var body = Encoding.UTF8.GetBytes(json);

        using (var request = new UnityWebRequest(url, UnityWebRequest.kHttpVerbPOST))
        {
            request.uploadHandler = new UploadHandlerRaw(body);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");

            yield return request.SendWebRequest();
            LogResponse("POST", url, request);
        }
    }

    private void OnDestroy()
    {
        if (_stateSocket != null)
        {
            _stateSocket.Close();
            _stateSocket = null;
        }
        _stateReady = false;
        _pendingRunOnStart = false;
    }

    private void ConnectStateSocket()
    {
        var url = BuildStateWebSocketUrl();
        try
        {
            if (_stateSocket != null)
            {
                var currentUrl = _stateSocket.Url != null ? _stateSocket.Url.ToString() : "";
                var readyState = _stateSocket.ReadyState;
                if (string.Equals(currentUrl, url, StringComparison.OrdinalIgnoreCase) &&
                    (readyState == WebSocketSharp.WebSocketState.Open ||
                     readyState == WebSocketSharp.WebSocketState.Connecting))
                {
                    return;
                }

                _stateSocket.Close();
            }

            _stateReady = false;
            _stateSocket = new WebSocketSharp.WebSocket(url);
            _stateSocket.OnOpen += (_, __) =>
            {
                _nextSendAt = 0f;
                Debug.Log($"[UnityGraphApiClient] State WS open -> {url}");
            };
            _stateSocket.OnMessage += (_, messageEvent) =>
            {
                try
                {
                    var ack = JsonUtility.FromJson<UnityStateAck>(messageEvent.Data);
                    if (ack != null && ack.ok)
                    {
                        _stateReady = true;
                        return;
                    }

                    if (ack != null && !string.IsNullOrWhiteSpace(ack.error))
                    {
                        Debug.LogWarning($"[UnityGraphApiClient] State WS ack error: {ack.error}");
                    }
                }
                catch (Exception ex)
                {
                    Debug.LogWarning($"[UnityGraphApiClient] State WS ack parse failed: {ex.Message}");
                }
            };
            _stateSocket.OnError += (_, e) =>
            {
                _stateReady = false;
                Debug.LogError($"[UnityGraphApiClient] State WS error: {e.Message}");
            };
            _stateSocket.OnClose += (_, __) =>
            {
                _stateReady = false;
                Debug.Log($"[UnityGraphApiClient] State WS closed");
            };
            _stateSocket.ConnectAsync();
        }
        catch (System.Exception ex)
        {
            Debug.LogError($"[UnityGraphApiClient] State WS connect failed: {ex.Message}");
        }
    }

    [ContextMenu("Enable Unity State Streaming")]
    public void EnableUnityStateStreaming()
    {
        sendStateContinuously = true;
        ConnectStateSocket();
        Debug.Log(
            $"[UnityGraphApiClient] Unity state streaming enabled for client_id={stateClientId}"
        );
    }

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

        var readyState = _stateSocket.ReadyState;
        return readyState == WebSocketSharp.WebSocketState.Open ||
               readyState == WebSocketSharp.WebSocketState.Connecting;
    }

    [ContextMenu("Send State Once")]
    public void SendStateOnce()
    {
        if (_stateSocket == null || !_stateSocket.IsAlive)
        {
            sendStateContinuously = true;
            ConnectStateSocket();
            Debug.LogWarning(
                "[UnityGraphApiClient] State socket not connected; connecting now. " +
                "Run Send State Once again after the socket opens, or keep streaming enabled."
            );
            return;
        }

        _stateReady = false;
        var statePayload = BuildStatePayload();
        var json = JsonUtility.ToJson(statePayload);
        _stateSocket.SendAsync(json, completed =>
        {
            if (!completed)
            {
                Debug.LogWarning("[UnityGraphApiClient] State send not completed (async)");
            }
        });
    }

    private UnityRunRobotState BuildRobotStateSnapshot()
    {
        var target = FindUnityTarget();
        if (target != null)
        {
            var position = target.transform.position;
            var rotation = target.transform.eulerAngles;
            var velocity = TryGetVelocity(target);
            var goalPosition = goal != null
                ? new float[] { goal.position.x, goal.position.y, goal.position.z }
                : new float[0];
            var distanceToGoal = goal != null ? Vector3.Distance(position, goal.position) : -1.0f;
            return new UnityRunRobotState
            {
                gripper_open = gripperOpen,
                position = new float[] { position.x, position.y, position.z },
                rotation = new float[] { rotation.x, rotation.y, rotation.z },
                velocity = velocity,
                eef_pose = new float[]
                {
                    position.x,
                    position.y,
                    position.z,
                    rotation.x,
                    rotation.y,
                    rotation.z,
                },
                goal_position = goalPosition,
                distance_to_goal = distanceToGoal,
                has_line_of_sight = HasLineOfSightToGoal(target),
                stuck = IsStuck(target, distanceToGoal),
                object_name = target.name,
                robot_type = unityRobotType,
                controller_mode = unityControllerMode,
            };
        }

        return new UnityRunRobotState
        {
            gripper_open = gripperOpen,
            position = new float[] { 0f, 0f, 0f },
            rotation = new float[] { 0f, 0f, 0f },
            velocity = new float[] { 0f, 0f, 0f },
            eef_pose = eefPose != null && eefPose.Length >= 6
                ? eefPose
                : new float[] { 0.1f, 0.2f, 0.3f, 0f, 0f, 0f },
            goal_position = goal != null
                ? new float[] { goal.position.x, goal.position.y, goal.position.z }
                : new float[0],
            distance_to_goal = -1.0f,
            has_line_of_sight = false,
            stuck = false,
            object_name = unityObject,
            robot_type = unityRobotType,
            controller_mode = unityControllerMode,
        };
    }

    private UnityStatePayload BuildStatePayload()
    {
        var position = TryGetPosition();
        var rotation = TryGetEuler();
        var snapshot = BuildRobotStateSnapshot();

        return new UnityStatePayload
        {
            type = "robot_state",
            client_id = string.IsNullOrWhiteSpace(stateClientId) ? "default" : stateClientId.Trim(),
            request_id = "",
            position = position,
            rotation = rotation,
            gripper_open = snapshot.gripper_open,
            eef_pose = snapshot.eef_pose,
            velocity = snapshot.velocity,
            goal_position = snapshot.goal_position,
            distance_to_goal = snapshot.distance_to_goal,
            has_line_of_sight = snapshot.has_line_of_sight,
            stuck = snapshot.stuck,
            robot_type = snapshot.robot_type,
            controller_mode = snapshot.controller_mode,
            scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name,
            object_name = snapshot.object_name,
            timestamp = Time.realtimeSinceStartup,
        };
    }

    private GameObject FindUnityTarget()
    {
        if (string.IsNullOrWhiteSpace(unityObject))
        {
            return null;
        }

        return GameObject.Find(unityObject);
    }

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
            Debug.LogWarning($"[UnityGraphApiClient] Failed to build WS URL from backendBaseUrl: {ex.Message}");
            return $"ws://localhost:9000/ws/unity/state?client_id={Uri.EscapeDataString(clientId)}";
        }
    }

    private float[] TryGetPosition()
    {
        var go = FindUnityTarget();
        if (go == null) return new float[] { 0, 0, 0 };
        var p = go.transform.position;
        return new float[] { p.x, p.y, p.z };
    }

    private float[] TryGetEuler()
    {
        var go = FindUnityTarget();
        if (go == null) return new float[] { 0, 0, 0 };
        var r = go.transform.eulerAngles;
        return new float[] { r.x, r.y, r.z };
    }

    private float[] TryGetVelocity(GameObject target)
    {
        if (target == null)
        {
            return new float[] { 0f, 0f, 0f };
        }

        var agent = target.GetComponent<NavMeshAgent>();
        if (agent != null)
        {
            var velocity = agent.velocity;
            return new float[] { velocity.x, velocity.y, velocity.z };
        }

        var rigidbody = target.GetComponent<Rigidbody>();
        if (rigidbody != null)
        {
            var velocity = rigidbody.velocity;
            return new float[] { velocity.x, velocity.y, velocity.z };
        }

        return new float[] { 0f, 0f, 0f };
    }

    private bool HasLineOfSightToGoal(GameObject target)
    {
        if (target == null || goal == null)
        {
            return false;
        }

        var origin = target.transform.position + Vector3.up * 1.0f;
        var destination = goal.position + Vector3.up * 1.0f;
        var direction = destination - origin;
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

    private bool IsStuck(GameObject target, float distanceToGoal)
    {
        if (target == null || distanceToGoal < 0.0f)
        {
            return false;
        }

        var velocity = TryGetVelocity(target);
        var speed = new Vector3(velocity[0], velocity[1], velocity[2]).magnitude;
        return speed < stuckVelocityThreshold && distanceToGoal > stuckDistanceThreshold;
    }

    private void LogResponse(string method, string url, UnityWebRequest request)
    {
        var status = $"{method} {url} -> {request.responseCode}";
        if (request.result == UnityWebRequest.Result.Success)
        {
            Debug.Log($"[UnityGraphApiClient] {status}\n{request.downloadHandler.text}");
            return;
        }

        Debug.LogError(
            $"[UnityGraphApiClient] {status}\n{request.error}\n{request.downloadHandler.text}"
        );
    }
}
