using System;
using System.Collections.Generic;
using System.Threading;
using UnityEngine;
using UnityEngine.SceneManagement;
using WebSocketSharp;
using WebSocketSharp.Server;

[Serializable]
public class RobotAction
{
    public float[] translation;
    public float[] rotation;
    public string gripper;
    public bool terminate;
    public string type;
}

[Serializable]
public class RobotCommandRequest
{
    public string type;
    public string request_id;
    public string scene;
    public string @object;
    public string command;
    public RobotAction action;
}

[Serializable]
public class RobotAckResponse
{
    public bool ok;
    public string type;
    public string request_id;
    public bool applied;
    public string message;
    public string error;
    public string scene;
    public string target;
    public string command;
}

public class UnityRobotWebSocketServer : MonoBehaviour
{
    [Header("Server")]
    public int port = 9081;
    public string defaultTargetObject = "RobotArm";
    public bool requireSceneMatch = false;

    [Header("Command Monitor")]
    public bool showCommandOverlay = true;
    public int maxCommandHistory = 6;
    public int receivedCommandCount = 0;

    [TextArea(2, 4)]
    public string lastCommandSummary = "Waiting for command...";

    [TextArea(3, 8)]
    public string lastReceivedRawJson = "";

    [TextArea(2, 4)]
    public string lastAckSummary = "";

    [TextArea(6, 16)]
    public string recentCommandLog = "";

    private WebSocketServer _server;
    private static readonly Queue<Action> MainThreadQueue = new Queue<Action>();
    private readonly Queue<string> _recentEvents = new Queue<string>();
    private static UnityRobotWebSocketServer _instance;
    private GUIStyle _overlayBoxStyle;
    private GUIStyle _overlayTitleStyle;
    private GUIStyle _overlayTextStyle;
    private Vector2 _logScrollPos = Vector2.zero;
    private static int MainThreadManagedThreadId = -1;

    public static string DefaultTargetObject = "RobotArm";
    public static bool RequireSceneMatch = false;

    private void Awake()
    {
        _instance = this;
        MainThreadManagedThreadId = Thread.CurrentThread.ManagedThreadId;
    }

    private void Start()
    {
        DefaultTargetObject = defaultTargetObject;
        RequireSceneMatch = requireSceneMatch;

        _server = new WebSocketServer(port);
        _server.AddWebSocketService<RobotWsBehavior>("/robot");
        RobotWsBehavior.Enqueue = EnqueueOnMainThread;
        RobotWsBehavior.RecordIncoming = RecordIncomingCommand;
        RobotWsBehavior.RecordOutcome = RecordCommandOutcome;
        RobotWsBehavior.RecordNotice = RecordNotice;
        _server.Start();

        Debug.Log($"[UnityRobotWS] started ws://0.0.0.0:{port}/robot");
        AppendRecentEvent($"Server started on ws://0.0.0.0:{port}/robot");
    }

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
    }

    private void OnApplicationQuit()
    {
        if (_server != null)
        {
            _server.Stop();
            _server = null;
        }

        if (_instance == this)
        {
            _instance = null;
        }

        RobotWsBehavior.RecordIncoming = null;
        RobotWsBehavior.RecordOutcome = null;
        RobotWsBehavior.RecordNotice = null;
    }

    private void OnGUI()
    {
        if (!showCommandOverlay)
        {
            return;
        }

        EnsureOverlayStyles();

        GUILayout.BeginArea(new Rect(12f, 12f, 560f, 300f), _overlayBoxStyle);
        GUILayout.Label("Unity Robot WS Monitor", _overlayTitleStyle);
        GUILayout.Label($"Received: {receivedCommandCount}", _overlayTextStyle);
        GUILayout.Label($"Last Command: {lastCommandSummary}", _overlayTextStyle);

        if (!string.IsNullOrWhiteSpace(lastAckSummary))
        {
            GUILayout.Label($"Last Ack: {lastAckSummary}", _overlayTextStyle);
        }

        if (!string.IsNullOrWhiteSpace(recentCommandLog))
        {
            GUILayout.Space(6f);
            GUILayout.Label("Recent", _overlayTextStyle);
            _logScrollPos = GUILayout.BeginScrollView(_logScrollPos, GUILayout.Height(120f));
            GUILayout.Label(recentCommandLog, _overlayTextStyle);
            GUILayout.EndScrollView();
        }

        GUILayout.EndArea();
    }

    public static void EnqueueOnMainThread(Action action)
    {
        lock (MainThreadQueue)
        {
            MainThreadQueue.Enqueue(action);
        }
    }

    public static bool IsOnMainThread()
    {
        return Thread.CurrentThread.ManagedThreadId == MainThreadManagedThreadId;
    }

    private void RecordIncomingCommand(string rawJson, RobotCommandRequest request)
    {
        receivedCommandCount += 1;
        lastReceivedRawJson = rawJson ?? "";
        lastCommandSummary = BuildCommandSummary(request);
        AppendRecentEvent($"IN  {lastCommandSummary}");
    }

    private void RecordCommandOutcome(RobotCommandRequest request, RobotAckResponse ack)
    {
        lastAckSummary = BuildAckSummary(ack);
        AppendRecentEvent($"OUT {lastAckSummary}");
    }

    private void RecordNotice(string message)
    {
        if (string.IsNullOrWhiteSpace(message))
        {
            return;
        }

        lastAckSummary = message;
        AppendRecentEvent($"INFO {message}");
    }

    private void AppendRecentEvent(string line)
    {
        var timestamped = $"[{DateTime.Now:HH:mm:ss}] {line}";
        _recentEvents.Enqueue(timestamped);

        var maxCount = Mathf.Max(1, maxCommandHistory);
        while (_recentEvents.Count > maxCount)
        {
            _recentEvents.Dequeue();
        }

        recentCommandLog = string.Join("\n", _recentEvents.ToArray());
        Debug.Log($"[UnityRobotWS] {line}");
    }

    private static string BuildCommandSummary(RobotCommandRequest request)
    {
        if (request == null)
        {
            return "Request is null";
        }

        var translation = FormatVector(request.action != null ? request.action.translation : null);
        var rotation = FormatVector(request.action != null ? request.action.rotation : null);
        var gripper = request.action != null ? request.action.gripper : "noop";
        var terminate = request.action != null && request.action.terminate ? "true" : "false";
        var target = string.IsNullOrWhiteSpace(request.@object) ? DefaultTargetObject : request.@object;

        return
            $"id={request.request_id}, scene={request.scene}, object={target}, cmd={request.command}, " +
            $"move=({translation}), rot=({rotation}), gripper={gripper}, terminate={terminate}";
    }

    private static string BuildAckSummary(RobotAckResponse ack)
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
}

public class RobotWsBehavior : WebSocketBehavior
{
    public static Action<Action> Enqueue;
    public static Action<string, RobotCommandRequest> RecordIncoming;
    public static Action<RobotCommandRequest, RobotAckResponse> RecordOutcome;
    public static Action<string> RecordNotice;


    protected override void OnMessage(MessageEventArgs e)
    {
        RobotCommandRequest req = null;

        try
        {
            req = JsonUtility.FromJson<RobotCommandRequest>(e.Data);
        }
        catch (Exception ex)
        {
            Enqueue?.Invoke(() => RecordNotice?.Invoke("Invalid JSON: " + ex.Message));
            SafeSend(Fail("", "", "", "Invalid JSON: " + ex.Message));
            return;
        }

        if (req == null)
        {
            Enqueue?.Invoke(() => RecordNotice?.Invoke("Request is null"));
            SafeSend(Fail("", "", "", "Request is null"));
            return;
        }

        RobotAckResponse ack = null;
        Action processRequest = () =>
        {
            try
            {
                RecordIncoming?.Invoke(e.Data, req);
                ack = ApplyRequest(req);
                RecordOutcome?.Invoke(req, ack);
            }
            catch (Exception ex)
            {
                ack = Fail(
                    req.request_id,
                    SceneManager.GetActiveScene().name,
                    req.@object,
                    ex.Message,
                    req.command
                );
                RecordOutcome?.Invoke(req, ack);
            }
        };

        Action processAndReply = () =>
        {
            processRequest();
            SafeSend(ack ?? Fail(req.request_id, req.scene, req.@object, "Ack is null", req.command));
        };

        if (UnityRobotWebSocketServer.IsOnMainThread())
        {
            processAndReply();
        }
        else
        {
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
                Enqueue?.Invoke(() => RecordNotice?.Invoke($"Main thread execution timed out: {req.request_id}"));
                SafeSend(Fail(req.request_id, req.scene, req.@object, "Main thread execution timed out", req.command));
                return;
            }

            SafeSend(ack ?? Fail(req.request_id, req.scene, req.@object, "Ack is null", req.command));
        }
    }

    private void SafeSend(RobotAckResponse ack)
    {
        if (State != WebSocketState.Open) return;
        Send(JsonUtility.ToJson(ack));
    }

    private RobotAckResponse ApplyRequest(RobotCommandRequest req)
    {
        try
        {
            if (!string.Equals(req.type, "robot_command", StringComparison.OrdinalIgnoreCase))
            {
                return Fail(req.request_id, req.scene, req.@object, $"Unsupported type: {req.type}", req.command);
            }

            if (!string.Equals(req.command, "apply_action", StringComparison.Ordinal))
            {
                return Fail(req.request_id, req.scene, req.@object, $"Unsupported command: {req.command}", req.command);
            }

            if (req.action == null)
            {
                return Fail(req.request_id, req.scene, req.@object, "Action is null", req.command);
            }

            var activeScene = SceneManager.GetActiveScene().name;
            if (UnityRobotWebSocketServer.RequireSceneMatch &&
                !string.IsNullOrWhiteSpace(req.scene) &&
                !string.Equals(req.scene, activeScene, StringComparison.Ordinal))
            {
                return Fail(
                    req.request_id,
                    activeScene,
                    req.@object,
                    $"Scene mismatch: req={req.scene}, active={activeScene}",
                    req.command
                );
            }

            var targetName = string.IsNullOrWhiteSpace(req.@object)
                ? UnityRobotWebSocketServer.DefaultTargetObject
                : req.@object;

            var target = GameObject.Find(targetName);
            if (target == null)
            {
                return Fail(req.request_id, activeScene, targetName, $"Target object not found: {targetName}", req.command);
            }

            var t = req.action.translation ?? new float[] { 0f, 0f, 0f };
            var r = req.action.rotation ?? new float[] { 0f, 0f, 0f };

            float tx = t.Length > 0 ? t[0] : 0f;
            float ty = t.Length > 1 ? t[1] : 0f;
            float tz = t.Length > 2 ? t[2] : 0f;

            float rx = r.Length > 0 ? r[0] : 0f;
            float ry = r.Length > 1 ? r[1] : 0f;
            float rz = r.Length > 2 ? r[2] : 0f;

            target.transform.position += new Vector3(tx, ty, tz);
            target.transform.eulerAngles += new Vector3(rx, ry, rz);

            Debug.Log(
                $"[UnityRobotWS] applied request_id={req.request_id}, scene={activeScene}, object={targetName}, " +
                $"gripper={req.action.gripper}, terminate={req.action.terminate}"
            );

            return new RobotAckResponse
            {
                ok = true,
                type = "robot_ack",
                request_id = req.request_id,
                applied = true,
                message = "Action applied",
                error = "",
                scene = activeScene,
                target = targetName,
                command = req.command
            };
        }
        catch (Exception ex)
        {
            return Fail(req.request_id, SceneManager.GetActiveScene().name, req.@object, ex.Message, req.command);
        }
    }

    private static RobotAckResponse Fail(
        string requestId,
        string scene,
        string target,
        string error,
        string command = ""
    )
    {
        return new RobotAckResponse
        {
            ok = false,
            type = "robot_ack",
            request_id = requestId ?? "",
            applied = false,
            message = "Apply failed",
            error = error ?? "Unknown error",
            scene = scene ?? "",
            target = target ?? "",
            command = command ?? ""
        };
    }
}
