// src/components/nodes/GenericNode.tsx
import React, { useEffect, useRef } from "react";
import { Handle, Position, NodeProps } from "reactflow";
import { NODE_DEF_BY_TYPE, nodeColor, pinColor } from "../../nodeDefs";

const INLINE_UNITY_ROBOT_TYPE_OPTIONS = [
  "generic",
  "articulated_arm",
  "mobile_base",
  "humanoid",
];

const INLINE_UNITY_COMMAND_OPTIONS: Record<string, string[]> = {
  generic: ["apply_action", "stop"],
  articulated_arm: [
    "apply_joint_targets",
    "apply_joint_deltas",
    "apply_joint_velocities",
    "stop",
  ],
  mobile_base: ["apply_base_velocity", "apply_base_waypoint", "stop"],
  humanoid: [
    "apply_humanoid_step",
    "apply_base_waypoint",
    "apply_patrol_control",
    "apply_action",
    "stop",
  ],
};

function inlineUnityCommandsForRobotType(robotType: unknown) {
  const normalized = String(robotType ?? "generic");
  return INLINE_UNITY_COMMAND_OPTIONS[normalized] ?? INLINE_UNITY_COMMAND_OPTIONS.generic;
}

function stopEvent(event: React.SyntheticEvent) {
  event.stopPropagation();
}

function handleFileInputChange(
  event: React.ChangeEvent<HTMLInputElement>,
  callback?: (file: File) => void
) {
  event.stopPropagation();
  const file = event.target.files?.[0];
  if (file && callback) {
    callback(file);
  }
  event.target.value = "";
}

function getStatusBorder(status: string, selected: boolean) {
  if (status === "running") return "1px solid #f59e0b";
  if (status === "ok" || status === "success") return "1px solid #22c55e";
  if (status === "error") return "1px solid #ef4444";
  if (selected) return "1px solid #60a5fa";
  return "1px solid #1e293b";
}

function InfoRow({
  label,
  value,
  strong = false,
}: {
  label: string;
  value: React.ReactNode;
  strong?: boolean;
}) {
  return (
    <div style={{ marginBottom: 4 }}>
      <span style={{ opacity: 0.7 }}>{label}: </span>
      <span style={{ opacity: 0.95, fontWeight: strong ? 700 : 500 }}>{value}</span>
    </div>
  );
}

function ModeBadge({ mode }: { mode: string }) {
  const m = String(mode || "simulate").toLowerCase();

  const bg =
    m === "unity"
      ? "rgba(59,130,246,0.18)"
      : m === "omniverse"
      ? "rgba(168,85,247,0.18)"
      : m === "ros"
      ? "rgba(34,197,94,0.18)"
      : "rgba(148,163,184,0.18)";

  const border =
    m === "unity"
      ? "1px solid rgba(96,165,250,0.45)"
      : m === "omniverse"
      ? "1px solid rgba(192,132,252,0.45)"
      : m === "ros"
      ? "1px solid rgba(74,222,128,0.45)"
      : "1px solid rgba(148,163,184,0.35)";

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: 22,
        padding: "0 8px",
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: 0.2,
        background: bg,
        border,
        color: "#e5eefc",
        textTransform: "uppercase",
      }}
    >
      {m}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const normalized = String(status || "idle").toLowerCase();
  const label =
    normalized === "running"
      ? "RUNNING"
      : normalized === "success" || normalized === "ok"
      ? "OK"
      : normalized === "warning"
      ? "CHECK"
      : normalized === "error"
      ? "ERROR"
      : "IDLE";

  const background =
    normalized === "running"
      ? "rgba(245,158,11,0.18)"
      : normalized === "success" || normalized === "ok"
      ? "rgba(34,197,94,0.18)"
      : normalized === "warning"
      ? "rgba(251,191,36,0.18)"
      : normalized === "error"
      ? "rgba(239,68,68,0.18)"
      : "rgba(148,163,184,0.18)";

  const border =
    normalized === "running"
      ? "1px solid rgba(251,191,36,0.35)"
      : normalized === "success" || normalized === "ok"
      ? "1px solid rgba(74,222,128,0.35)"
      : normalized === "warning"
      ? "1px solid rgba(253,224,71,0.35)"
      : normalized === "error"
      ? "1px solid rgba(248,113,113,0.35)"
      : "1px solid rgba(148,163,184,0.22)";

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: 22,
        padding: "0 8px",
        borderRadius: 999,
        fontSize: 10,
        fontWeight: 800,
        letterSpacing: 0.3,
        background,
        border,
        color: "#f8fafc",
      }}
    >
      {label}
    </span>
  );
}

function Panel({
  children,
  tint = "rgba(255,255,255,0.04)",
  border = "1px solid rgba(255,255,255,0.06)",
}: {
  children: React.ReactNode;
  tint?: string;
  border?: string;
}) {
  return (
    <div
      style={{
        marginTop: 6,
        padding: 8,
        borderRadius: 10,
        background: tint,
        border,
      }}
    >
      {children}
    </div>
  );
}

function speechTaskLabel(task: unknown) {
  return String(task ?? "transcribe") === "translate" ? "영문 번역" : "원문 추출";
}

function speechLanguageLabel(language: unknown) {
  const normalized = String(language ?? "auto");
  if (normalized === "ko") return "한국어";
  if (normalized === "en") return "영어";
  if (normalized === "ja") return "일본어";
  return "자동 감지";
}

function speechProviderLabel(provider: unknown) {
  const normalized = String(provider ?? "whisper");
  if (normalized === "stub") return "Stub Demo";
  if (normalized === "faster-whisper") return "Faster Whisper";
  return "Whisper";
}

function speechOutputLabel(task: unknown) {
  return String(task ?? "transcribe") === "translate" ? "영문 텍스트" : "원문 텍스트";
}

function compactAssetLabel(path: unknown, fallback = "not set", max = 28) {
  const raw = String(path ?? "").trim();
  if (!raw) return fallback;

  const basename = raw.replace(/\\/g, "/").split("/").pop() || raw;
  if (basename.length <= max) return basename;
  return `${basename.slice(0, max - 3)}...`;
}

function isBrowserPreviewUrl(value: unknown) {
  const text = String(value ?? "").trim();
  return text.startsWith("http://") || text.startsWith("https://") || text.startsWith("/uploads/");
}

function isVisionPoseNode(type: unknown) {
  return (
    type === "realsense_d435i_sensor" ||
    type === "mediapipe_pose" ||
    type === "rgbd_pose_fusion"
  );
}

function StableImagePreview({
  src,
  alt,
  aspectRatio = "4 / 3",
}: {
  src: string;
  alt: string;
  aspectRatio?: string;
}) {
  const [displaySrc, setDisplaySrc] = React.useState(src || "");

  React.useEffect(() => {
    if (!src || src === displaySrc) {
      return;
    }

    let cancelled = false;
    const image = new Image();
    image.onload = () => {
      if (!cancelled) {
        setDisplaySrc(src);
      }
    };
    image.src = src;

    return () => {
      cancelled = true;
    };
  }, [displaySrc, src]);

  if (!displaySrc) {
    return (
      <div
        style={{
          aspectRatio,
          display: "grid",
          placeItems: "center",
          color: "#94a3b8",
          background: "rgba(2,6,23,0.72)",
          fontSize: 11,
        }}
      >
        Image appears after run
      </div>
    );
  }

  return (
    <img
      src={displaySrc}
      alt={alt}
      decoding="async"
      style={{
        width: "100%",
        display: "block",
        aspectRatio,
        objectFit: "cover",
        background: "#020617",
      }}
    />
  );
}

function VisionImagePanel({
  label,
  src,
}: {
  label: string;
  src: unknown;
}) {
  return (
    <div
      onClick={stopEvent}
      onMouseDown={stopEvent}
      style={{
        marginTop: 8,
        borderRadius: 12,
        overflow: "hidden",
        border: "1px solid rgba(255,255,255,0.12)",
        background: "rgba(2,6,23,0.6)",
      }}
    >
      <div
        style={{
          padding: "7px 10px",
          fontSize: 10,
          fontWeight: 800,
          color: "#cbd5e1",
          textTransform: "uppercase",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          background: "rgba(255,255,255,0.04)",
        }}
      >
        {label}
      </div>
      <StableImagePreview src={String(src ?? "")} alt={label} />
    </div>
  );
}

function VisionJsonPreview({ value }: { value: unknown }) {
  if (value == null) {
    return null;
  }

  let text = "";
  try {
    text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  } catch {
    text = String(value);
  }

  if (!text) {
    return null;
  }

  return (
    <Panel tint="rgba(14,165,233,0.07)" border="1px solid rgba(125,211,252,0.14)">
      <div style={{ fontSize: 10, fontWeight: 800, color: "#bfdbfe", marginBottom: 6 }}>
        runtime
      </div>
      <pre
        onClick={stopEvent}
        onMouseDown={stopEvent}
        style={{
          margin: 0,
          maxHeight: 120,
          overflow: "auto",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          color: "#dbeafe",
          fontSize: 10,
          lineHeight: 1.45,
        }}
      >
        {text}
      </pre>
    </Panel>
  );
}

type PosePreviewLandmark = {
  x?: number;
  y?: number;
  visibility?: number;
};

type PosePreviewFrame = {
  timestamp_sec?: number;
  frame_index?: number;
  landmarks?: Record<string, PosePreviewLandmark>;
};

const POSE_PREVIEW_CONNECTIONS: Array<[string, string]> = [
  ["LEFT_SHOULDER", "RIGHT_SHOULDER"],
  ["LEFT_SHOULDER", "LEFT_ELBOW"],
  ["LEFT_ELBOW", "LEFT_WRIST"],
  ["RIGHT_SHOULDER", "RIGHT_ELBOW"],
  ["RIGHT_ELBOW", "RIGHT_WRIST"],
  ["LEFT_SHOULDER", "LEFT_HIP"],
  ["RIGHT_SHOULDER", "RIGHT_HIP"],
  ["LEFT_HIP", "RIGHT_HIP"],
  ["LEFT_HIP", "LEFT_KNEE"],
  ["LEFT_KNEE", "LEFT_ANKLE"],
  ["RIGHT_HIP", "RIGHT_KNEE"],
  ["RIGHT_KNEE", "RIGHT_ANKLE"],
];

function posePreviewFrames(value: unknown): PosePreviewFrame[] {
  if (!value || typeof value !== "object") {
    return [];
  }
  const frames = (value as { frames?: unknown }).frames;
  return Array.isArray(frames) ? (frames as PosePreviewFrame[]) : [];
}

function nearestPosePreviewFrame(frames: PosePreviewFrame[], currentTime: number) {
  if (frames.length === 0) {
    return undefined;
  }

  let best = frames[0];
  let bestDistance = Number.POSITIVE_INFINITY;
  for (const frame of frames) {
    const timestamp = Number(frame?.timestamp_sec ?? 0);
    const distance = Math.abs(timestamp - currentTime);
    if (distance < bestDistance) {
      best = frame;
      bestDistance = distance;
    }
  }
  return best;
}

function resizeCanvasToDisplaySize(canvas: HTMLCanvasElement) {
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width));
  const height = Math.max(1, Math.round(rect.height));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  return { width, height };
}

function drawPosePreviewOverlay(
  canvas: HTMLCanvasElement,
  video: HTMLVideoElement,
  preview: unknown
) {
  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }

  const { width, height } = resizeCanvasToDisplaySize(canvas);
  context.clearRect(0, 0, width, height);

  const frames = posePreviewFrames(preview);
  const frame = nearestPosePreviewFrame(frames, video.currentTime);
  const landmarks = frame?.landmarks;
  if (!landmarks) {
    return;
  }

  const videoWidth = video.videoWidth || width;
  const videoHeight = video.videoHeight || height;
  const videoRatio = videoWidth / Math.max(1, videoHeight);
  const canvasRatio = width / Math.max(1, height);
  let drawWidth = width;
  let drawHeight = height;
  let offsetX = 0;
  let offsetY = 0;

  if (videoRatio > canvasRatio) {
    drawWidth = width;
    drawHeight = width / videoRatio;
    offsetY = (height - drawHeight) * 0.5;
  } else {
    drawHeight = height;
    drawWidth = height * videoRatio;
    offsetX = (width - drawWidth) * 0.5;
  }

  const pointFor = (name: string) => {
    const landmark = landmarks[name];
    if (!landmark) {
      return undefined;
    }
    const x = Number(landmark.x);
    const y = Number(landmark.y);
    const visibility = Number(landmark.visibility ?? 1);
    if (!Number.isFinite(x) || !Number.isFinite(y) || visibility < 0.2) {
      return undefined;
    }
    return {
      x: offsetX + x * drawWidth,
      y: offsetY + y * drawHeight,
      visibility,
    };
  };

  context.save();
  context.lineCap = "round";
  context.lineJoin = "round";
  context.shadowColor = "rgba(2, 6, 23, 0.9)";
  context.shadowBlur = 4;

  context.strokeStyle = "rgba(45, 212, 191, 0.95)";
  context.lineWidth = 3;
  for (const [fromName, toName] of POSE_PREVIEW_CONNECTIONS) {
    const from = pointFor(fromName);
    const to = pointFor(toName);
    if (!from || !to) {
      continue;
    }
    context.beginPath();
    context.moveTo(from.x, from.y);
    context.lineTo(to.x, to.y);
    context.stroke();
  }

  for (const name of Object.keys(landmarks)) {
    const point = pointFor(name);
    if (!point) {
      continue;
    }
    const isCore = name.includes("HIP") || name.includes("SHOULDER");
    context.beginPath();
    context.fillStyle = isCore ? "#f97316" : "#f8fafc";
    context.strokeStyle = "rgba(15, 23, 42, 0.86)";
    context.lineWidth = 2;
    context.arc(point.x, point.y, isCore ? 4.5 : 3.5, 0, Math.PI * 2);
    context.fill();
    context.stroke();
  }

  context.restore();
}

function compactStateText(value: unknown, max = 160) {
  const raw = String(value ?? "").replace(/\s+/g, " ").trim();
  if (!raw) return "";
  if (raw.length <= max) return raw;
  return `${raw.slice(0, max - 3)}...`;
}

function renderRobotStateRuntime(data: any) {
  const message = compactStateText(data?.lastStateMessage, 120);
  const scene = compactStateText(data?.lastStateScene, 28);
  const objectName = compactStateText(data?.lastStateObject, 28);
  const source = compactStateText(data?.lastStateSource, 36);
  const gripper = compactStateText(data?.lastStateGripper, 20);
  const pose = compactStateText(data?.lastStatePose, 96);
  const preview = compactStateText(data?.lastStatePreview, 180);

  if (!message && !scene && !objectName && !source && !gripper && !pose && !preview) {
    return null;
  }

  return (
    <Panel
      tint="rgba(56,189,248,0.08)"
      border="1px solid rgba(125,211,252,0.16)"
    >
      {message && <InfoRow label="latest" value={message} />}
      {source && <InfoRow label="source" value={source} />}
      {(scene || objectName) && (
        <InfoRow
          label="target"
          value={`${scene || "-"}/${objectName || "-"}`}
        />
      )}
      {gripper && <InfoRow label="gripper" value={gripper} />}
      {pose && <InfoRow label="pose" value={pose} />}
      {preview && (
        <div
          style={{
            marginTop: 6,
            fontSize: 11,
            lineHeight: 1.45,
            color: "#bfdbfe",
            wordBreak: "break-word",
            opacity: 0.92,
          }}
        >
          payload: {preview}
        </div>
      )}
    </Panel>
  );
}

function renderRobotExecute(
  data: any,
  nodeId?: string,
  onNodeDataChange?: (nodeId: string, key: string, value: unknown) => void
) {
  const mode = String(data?.mode ?? "simulate");
  const executor = String(data?.executor ?? "robot-executor");
  const robotType = String(data?.robotType ?? data?.unityRobotType ?? "generic");
  const commandOptions = inlineUnityCommandsForRobotType(robotType);
  const currentCommand = String(data?.unityCommand ?? "apply_action");
  const commandSelectValue = commandOptions.includes(currentCommand) ? currentCommand : "__custom__";

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          marginBottom: 8,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <InfoRow label="target" value={<b>{executor}</b>} strong />
        </div>
        <ModeBadge mode={mode} />
      </div>

      {mode === "simulate" && (
        <Panel>
          <InfoRow label="sim" value={String(data?.simulateName ?? "default-sim")} />
          <InfoRow label="speed" value={String(data?.simulateSpeed ?? 1.0)} />
          <InfoRow label="dryRun" value={Boolean(data?.dryRun ?? true) ? "true" : "false"} />
        </Panel>
      )}

      {mode === "unity" && (
        <Panel
          tint="rgba(59,130,246,0.08)"
          border="1px solid rgba(96,165,250,0.15)"
        >
          <InfoRow label="endpoint" value={String(data?.unityEndpoint ?? "ws://host.docker.internal:9081/robot")} />
          <InfoRow label="scene" value={String(data?.unityScene ?? "VALConnect")} />
          <InfoRow label="object" value={String(data?.unityObject ?? "GR00T_Humanoid")} />
          <InfoRow label="command" value={String(data?.unityCommand ?? "apply_action")} />
          <InfoRow label="robotType" value={String(data?.unityRobotType ?? "generic")} />
          <InfoRow label="control" value={String(data?.unityControllerMode ?? "task")} />
          <InfoRow label="timeout" value={String(data?.unityTimeoutSec ?? data?.timeoutSec ?? 5)} />
          {nodeId && onNodeDataChange && (
            <div style={{ marginTop: 10, display: "grid", gap: 6 }}>
              <div style={{ fontSize: 11, opacity: 0.72, fontWeight: 700 }}>quick edit</div>
              <select
                value={robotType}
                onChange={(event) => onNodeDataChange(nodeId, "unityRobotType", event.target.value)}
                style={{
                  width: "100%",
                  borderRadius: 8,
                  border: "1px solid rgba(96,165,250,0.25)",
                  background: "rgba(15,23,42,0.72)",
                  color: "#e5eefc",
                  padding: "8px 10px",
                  fontSize: 12,
                }}
              >
                {INLINE_UNITY_ROBOT_TYPE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
              <select
                value={commandSelectValue}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  if (nextValue === "__custom__") {
                    onNodeDataChange(nodeId, "unityCommand", "");
                    return;
                  }
                  onNodeDataChange(nodeId, "unityCommand", nextValue);
                }}
                style={{
                  width: "100%",
                  borderRadius: 8,
                  border: "1px solid rgba(96,165,250,0.25)",
                  background: "rgba(15,23,42,0.72)",
                  color: "#e5eefc",
                  padding: "8px 10px",
                  fontSize: 12,
                }}
              >
                {commandOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
                <option value="__custom__">custom</option>
              </select>
              {commandSelectValue === "__custom__" && (
                <input
                  value={currentCommand}
                  placeholder="custom unity command"
                  onChange={(event) => onNodeDataChange(nodeId, "unityCommand", event.target.value)}
                  style={{
                    width: "100%",
                    borderRadius: 8,
                    border: "1px solid rgba(96,165,250,0.25)",
                    background: "rgba(15,23,42,0.72)",
                    color: "#e5eefc",
                    padding: "8px 10px",
                    fontSize: 12,
                  }}
                />
              )}
            </div>
          )}
        </Panel>
      )}

      {mode === "omniverse" && (
        <Panel
          tint="rgba(168,85,247,0.08)"
          border="1px solid rgba(192,132,252,0.15)"
        >
          <InfoRow label="endpoint" value={String(data?.omniverseEndpoint ?? "ws://host.docker.internal:9900/omniverse")} />
          <InfoRow label="url" value={String(data?.omniverseUrl ?? "omniverse://localhost/Projects/Robot")} />
          <InfoRow label="stage" value={String(data?.omniverseStage ?? "/World")} />
          <InfoRow label="prim" value={String(data?.omniversePrimPath ?? "/World/GR00T_Humanoid")} />
          <InfoRow label="command" value={String(data?.omniverseCommand ?? "execute_policy")} />
          <InfoRow label="robotType" value={String(data?.robotType ?? data?.omniverseRobotType ?? data?.unityRobotType ?? "generic")} />
          <InfoRow label="control" value={String(data?.controllerMode ?? data?.omniverseControllerMode ?? data?.unityControllerMode ?? "task")} />
          <InfoRow label="timeout" value={String(data?.omniverseTimeoutSec ?? data?.timeoutSec ?? 15)} />
          <InfoRow label="wait response" value={String(Boolean(data?.omniverseWaitForResponse ?? true))} />
        </Panel>
      )}

      {mode === "ros" && (
        <Panel
          tint="rgba(34,197,94,0.08)"
          border="1px solid rgba(74,222,128,0.15)"
        >
          <InfoRow label="bridge" value={String(data?.rosBridgeUrl ?? "ws://localhost:9090")} />
          <InfoRow label="topic" value={String(data?.rosTopic ?? "/robot/action_cmd")} />
          <InfoRow label="robot" value={String(data?.rosRobotName ?? "robot1")} />
          <InfoRow label="frame" value={String(data?.rosFrameId ?? "base_link")} />
          <InfoRow label="msg" value={String(data?.rosMsgType ?? "geometry_msgs/Twist")} />
        </Panel>
      )}
    </div>
  );
}

export default function GenericNode(props: NodeProps) {
  const { id, type, data, selected } = props;
  const videoPreviewRef = useRef<HTMLVideoElement | null>(null);
  const poseCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const previousStatusRef = useRef("");

  const def = NODE_DEF_BY_TYPE[type ?? ""] ?? {
    type: type ?? "unknown",
    label: type ?? "unknown",
    category: "Node",
    width: 260,
    inputs: [],
    outputs: [],
  };

  const status = String(data?.status ?? "idle");
  const lastSummary = String(data?.lastSummary ?? "").trim();
  const lastDetail = String(data?.lastDetail ?? "").trim();
  const promptText = String(data?.text ?? "");
  const poseFrameCount = posePreviewFrames(data?.lastPosePreview).length;
  const onNodeDataChange =
    data?.onNodeDataChange as
      | ((nodeId: string, key: string, value: unknown) => void)
      | undefined;
  const onIsaacGr00tInit =
    data?.onIsaacGr00tInit as (() => void) | undefined;
  const onToggleRealSenseBridge =
    data?.onToggleRealSenseBridge as (() => void) | undefined;
  const width = Number(data?.__ui?.w ?? def.width ?? 260);
  const height = Number(data?.__ui?.h ?? def.height ?? 0);

  useEffect(() => {
    if (type !== "video_motion_input") {
      previousStatusRef.current = status;
      return;
    }

    const previousStatus = previousStatusRef.current;
    previousStatusRef.current = status;

    if (previousStatus === "running" || status !== "running") {
      return;
    }

    const video = videoPreviewRef.current;
    if (!video || !isBrowserPreviewUrl(data?.videoPath)) {
      return;
    }

    try {
      video.currentTime = 0;
    } catch {
      // Some browsers disallow seeking before metadata is loaded.
    }

    void video.play().catch(() => {
      // Browser autoplay can still be blocked if user settings disallow it.
    });
  }, [data?.videoPath, status, type]);

  useEffect(() => {
    if (type !== "video_motion_input") {
      return;
    }

    const video = videoPreviewRef.current;
    const canvas = poseCanvasRef.current;
    if (!video || !canvas) {
      return;
    }

    let frameRequest = 0;

    const draw = () => {
      drawPosePreviewOverlay(canvas, video, data?.lastPosePreview);
    };

    const drawLoop = () => {
      draw();
      if (!video.paused && !video.ended) {
        frameRequest = window.requestAnimationFrame(drawLoop);
      }
    };

    const startLoop = () => {
      if (frameRequest) {
        window.cancelAnimationFrame(frameRequest);
      }
      drawLoop();
    };

    const stopLoop = () => {
      if (frameRequest) {
        window.cancelAnimationFrame(frameRequest);
        frameRequest = 0;
      }
      draw();
    };

    draw();
    video.addEventListener("loadedmetadata", draw);
    video.addEventListener("timeupdate", draw);
    video.addEventListener("seeked", draw);
    video.addEventListener("play", startLoop);
    video.addEventListener("pause", stopLoop);
    video.addEventListener("ended", stopLoop);
    window.addEventListener("resize", draw);

    return () => {
      if (frameRequest) {
        window.cancelAnimationFrame(frameRequest);
      }
      video.removeEventListener("loadedmetadata", draw);
      video.removeEventListener("timeupdate", draw);
      video.removeEventListener("seeked", draw);
      video.removeEventListener("play", startLoop);
      video.removeEventListener("pause", stopLoop);
      video.removeEventListener("ended", stopLoop);
      window.removeEventListener("resize", draw);
    };
  }, [data?.lastPosePreview, data?.videoPath, type]);

  const nodeActionStyle: React.CSSProperties = {
    width: "100%",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: 32,
    marginTop: 8,
    padding: "8px 10px",
    borderRadius: 10,
    border: "1px solid rgba(255,255,255,0.14)",
    background: "rgba(255,255,255,0.08)",
    color: "#f8fafc",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    textDecoration: "none",
  };

  const handleSize = 12;

  const baseHandleStyle: React.CSSProperties = {
    width: handleSize,
    height: handleSize,
    borderRadius: 999,
    border: "1px solid rgba(255,255,255,0.95)",
    boxShadow: "0 0 0 2px rgba(8,16,29,0.92), 0 0 10px rgba(148,163,184,0.25)",
    zIndex: 20,
    cursor: "crosshair",
  };

  return (
    <div
      style={{
        width,
        ...(height > 0 ? { height } : {}),
        minHeight: 120,
        borderRadius: 18,
        background: `linear-gradient(180deg, ${nodeColor(type ?? "")} 0%, #08101d 100%)`,
        border: getStatusBorder(status, selected),
        color: "#e5eefc",
        padding: 12,
        position: "relative",
        overflow: "visible",
        boxShadow: "0 14px 32px rgba(0,0,0,0.35)",
      }}
    >
      {def.inputs.map((p, idx) => (
        <Handle
          key={`in-${p.id}`}
          type="target"
          id={p.id}
          position={Position.Left}
          style={{
            top: 48 + idx * 18,
            left: -7,
            background: pinColor(p.pinType),
            ...baseHandleStyle,
          }}
        />
      ))}

      {def.outputs.map((p, idx) => (
        <Handle
          key={`out-${p.id}`}
          type="source"
          id={p.id}
          position={Position.Right}
          style={{
            top: 48 + idx * 18,
            right: -7,
            background: pinColor(p.pinType),
            ...baseHandleStyle,
          }}
        />
      ))}

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 8,
          marginBottom: 4,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div style={{ marginBottom: 6 }}>
            <StatusBadge status={status} />
          </div>
          <div
            style={{
              fontSize: 15,
              fontWeight: 800,
              lineHeight: 1.2,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              color: "#ffffff",
            }}
          >
            {String(data?.label ?? def.label)}
          </div>

          <div
            style={{
              fontSize: 10,
              opacity: 0.75,
              marginTop: 2,
              color: "#9fb1c9",
            }}
          >
            {def.category}
          </div>
        </div>

        <button
          onClick={(e) => {
            e.stopPropagation();
            data?.onRemove?.(id);
          }}
          title="Remove node"
          style={{
            width: 20,
            height: 20,
            borderRadius: 6,
            border: "1px solid rgba(255,255,255,0.15)",
            background: "rgba(255,255,255,0.05)",
            color: "#dbeafe",
            cursor: "pointer",
            fontSize: 12,
            fontWeight: 700,
            lineHeight: "18px",
            padding: 0,
            flex: "0 0 auto",
          }}
        >
          ×
        </button>
      </div>

      <div
        style={{
          fontSize: 10,
          opacity: 0.55,
          marginBottom: 10,
          color: "#7c93b5",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {id}
      </div>

      <div
        style={{
          fontSize: 12,
          lineHeight: 1.45,
          color: "#d6e2f3",
        }}
      >
        {type === "prompt" && (
          <div>
            <div
              style={{
                marginBottom: 6,
                fontSize: 11,
                fontWeight: 700,
                color: "#bfdbfe",
              }}
            >
              prompt
            </div>
            <textarea
              className="nodrag nowheel"
              value={promptText}
              placeholder="예: walk forward toward the checkpoint and turn slightly left"
              rows={4}
              onClick={stopEvent}
              onMouseDown={stopEvent}
              onChange={(event) => onNodeDataChange?.(id, "text", event.target.value)}
              style={{
                width: "100%",
                minHeight: 88,
                resize: "vertical",
                borderRadius: 10,
                border: "1px solid rgba(125,211,252,0.16)",
                background: "rgba(56,189,248,0.08)",
                color: "#e5eefc",
                padding: "10px 12px",
                fontSize: 12,
                lineHeight: 1.45,
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>
        )}

        {type === "image_input" && (
          <div>
            image:{" "}
            <span style={{ opacity: 0.85 }}>
              {String(data?.imageUrl ?? "").slice(0, 42)}
            </span>
            <label
              onClick={stopEvent}
              onMouseDown={stopEvent}
              style={nodeActionStyle}
            >
              Upload Image
              <input
                type="file"
                hidden
                accept="image/*"
                onChange={(event) => handleFileInputChange(event, data?.onImageUpload)}
              />
            </label>
          </div>
        )}

        {isVisionPoseNode(type) && (
          <div>
            {type === "realsense_d435i_sensor" && (
              <>
                <button
                  type="button"
                  onClick={(event) => {
                    stopEvent(event);
                    onToggleRealSenseBridge?.();
                  }}
                  onMouseDown={stopEvent}
                  disabled={
                    data?.realsenseBridgeStatus === "starting" ||
                    data?.realsenseBridgeStatus === "stopping"
                  }
                  style={{
                    ...nodeActionStyle,
                    marginTop: 0,
                    background: data?.realsensePreviewEnabled
                      ? "rgba(34,197,94,0.18)"
                      : "rgba(59,130,246,0.16)",
                    border: data?.realsensePreviewEnabled
                      ? "1px solid rgba(74,222,128,0.45)"
                      : "1px solid rgba(96,165,250,0.38)",
                    opacity:
                      data?.realsenseBridgeStatus === "starting" ||
                      data?.realsenseBridgeStatus === "stopping"
                        ? 0.72
                        : 1,
                  }}
                >
                  {data?.realsenseBridgeStatus === "starting"
                    ? "Starting RealSense..."
                    : data?.realsenseBridgeStatus === "stopping"
                    ? "Stopping RealSense..."
                    : data?.realsensePreviewEnabled
                    ? "Turn RealSense Off"
                    : "Turn RealSense On"}
                </button>
                <InfoRow
                  label="bridge"
                  value={String(data?.realsenseBridgeStatus ?? "off")}
                  strong={Boolean(data?.realsensePreviewEnabled)}
                />
                {String(data?.realsenseBridgeMessage ?? "").trim() && (
                  <InfoRow
                    label="message"
                    value={String(data?.realsenseBridgeMessage ?? "").slice(0, 64)}
                  />
                )}
                <InfoRow
                  label="source"
                  value={String(data?.remoteRgbdUrl ?? "").trim() ? "host bridge" : "backend USB"}
                />
                <InfoRow
                  label="device"
                  value={
                    String(data?.remoteRgbdUrl ?? "").trim()
                      ? compactAssetLabel(data?.remoteRgbdUrl, "remote RGB-D")
                      : String(data?.realsenseSerial ?? "") || "first D435i"
                  }
                />
                <InfoRow
                  label="capture"
                  value={`${String(data?.captureWidth ?? 640)}x${String(data?.captureHeight ?? 480)} @ ${String(data?.fps ?? 30)}fps`}
                />
                <InfoRow
                  label="mock"
                  value={Boolean(data?.mockWhenUnavailable ?? false) ? "enabled" : "disabled"}
                />
                <VisionImagePanel label="rgb image" src={data?.lastImageFrame} />
                <VisionImagePanel label="depth image" src={data?.lastDepthImageFrame} />
              </>
            )}

            {type === "mediapipe_pose" && (
              <>
                <InfoRow label="model" value={`complexity ${String(data?.modelComplexity ?? 1)}`} />
                <InfoRow label="visibility" value={String(data?.minPoseVisibility ?? 0.35)} />
                <VisionImagePanel label="pose image" src={data?.lastImageFrame} />
              </>
            )}

            {type === "rgbd_pose_fusion" && (
              <>
                <InfoRow label="depth radius" value={String(data?.depthSampleRadius ?? 3)} />
                <InfoRow label="history" value={`${String(data?.maxMotionFrames ?? 40)} frames`} />
                <InfoRow label="label" value={String(data?.motionLabel ?? "rgbd_follow")} />
                <VisionImagePanel label="fused image" src={data?.lastImageFrame} />
              </>
            )}

            <VisionJsonPreview value={data?.lastVisionJson} />
          </div>
        )}

        {type === "video_motion_input" && (
          <div>
            <InfoRow label="video" value={compactAssetLabel(data?.videoPath)} />
            <InfoRow label="label" value={String(data?.motionLabel ?? "-")} />
            {isBrowserPreviewUrl(data?.videoPath) ? (
              <div
                onClick={stopEvent}
                onMouseDown={stopEvent}
                style={{
                  marginTop: 8,
                  borderRadius: 12,
                  overflow: "hidden",
                  border: "1px solid rgba(255,255,255,0.12)",
                  background: "rgba(2,6,23,0.6)",
                  position: "relative",
                }}
              >
                <video
                  ref={videoPreviewRef}
                  src={String(data?.videoPath ?? "")}
                  controls
                  muted
                  playsInline
                  preload="metadata"
                  style={{
                    width: "100%",
                    display: "block",
                    aspectRatio: "16 / 9",
                    objectFit: "contain",
                    background: "#020617",
                  }}
                />
                <canvas
                  ref={poseCanvasRef}
                  style={{
                    position: "absolute",
                    inset: 0,
                    width: "100%",
                    height: "100%",
                    pointerEvents: "none",
                  }}
                />
                {poseFrameCount > 0 && (
                  <div
                    style={{
                      position: "absolute",
                      left: 8,
                      bottom: 8,
                      padding: "3px 7px",
                      borderRadius: 999,
                      background: "rgba(15,23,42,0.72)",
                      border: "1px solid rgba(45,212,191,0.35)",
                      color: "#ccfbf1",
                      fontSize: 10,
                      fontWeight: 800,
                      pointerEvents: "none",
                    }}
                  >
                    MediaPipe {poseFrameCount}
                  </div>
                )}
              </div>
            ) : (
              <div
                style={{
                  marginTop: 8,
                  aspectRatio: "16 / 9",
                  display: "grid",
                  placeItems: "center",
                  borderRadius: 12,
                  border: "1px solid rgba(255,255,255,0.12)",
                  background: "rgba(2,6,23,0.6)",
                  color: "#94a3b8",
                  fontSize: 11,
                  textAlign: "center",
                  padding: 12,
                }}
              >
                Video preview will appear here
              </div>
            )}
            <label
              onClick={stopEvent}
              onMouseDown={stopEvent}
              style={nodeActionStyle}
            >
              Upload Video
              <input
                type="file"
                hidden
                accept="video/*"
                onChange={(event) => handleFileInputChange(event, data?.onVideoUpload)}
              />
            </label>
          </div>
        )}

        {type === "motion_extract" && (
          <div>
            <InfoRow label="대상" value="휴머노이드 전용" />
            <InfoRow label="sample" value={`every ${String(data?.everyNFrames ?? 2)} frames`} />
            <InfoRow label="visibility" value={String(data?.minVisibility ?? 0.35)} />
            <InfoRow label="frames" value={Boolean(data?.includeFrames) ? "full trace" : "compact"} />
            <div style={{ fontSize: 11, opacity: 0.7, marginTop: 6 }}>
              사람의 전신 자세를 휴머노이드 관절·루트 동작으로 해석합니다.
            </div>
            {Array.isArray(data?.lastHumanoidMeaning) && data.lastHumanoidMeaning.length > 0 && (
              <Panel tint="rgba(16,185,129,0.08)" border="1px solid rgba(52,211,153,0.2)">
                <div style={{ fontSize: 10, fontWeight: 800, color: "#a7f3d0" }}>휴머노이드 의미</div>
                {data.lastHumanoidMeaning.map((item: any, index: number) => (
                  <div key={`${String(item?.code ?? "meaning")}-${index}`} style={{ marginTop: 4, fontSize: 10 }}>
                    {String(item?.name_ko ?? item?.code ?? "")}: {String(item?.meaning_ko ?? "")}
                  </div>
                ))}
              </Panel>
            )}
            {data?.lastTrainingDatasetPath && (
              <Panel tint="rgba(59,130,246,0.08)" border="1px solid rgba(96,165,250,0.2)">
                <InfoRow label="학습 샘플" value={String(data?.lastTrainingSampleCount ?? 0)} />
                <div style={{ marginTop: 4, fontSize: 10, wordBreak: "break-all", color: "#bfdbfe" }}>
                  {String(data.lastTrainingDatasetPath)}
                </div>
              </Panel>
            )}
          </div>
        )}

        {type === "motion_retarget" && (
          <div>
            <InfoRow label="target" value="Omniverse humanoid" />
            <InfoRow label="speed" value={String(data?.speed ?? 1.0)} />
            <InfoRow label="step" value={String(data?.stepScale ?? 0.45)} />
            <InfoRow label="turn" value={String(data?.turnScale ?? 0.2)} />
            <InfoRow label="body" value={Boolean(data?.fullBodyRetarget ?? true) ? "pose sequence" : "skill only"} />
            <InfoRow label="frames" value={String(data?.maxPoseFrames ?? 40)} />
            <div style={{ fontSize: 11, opacity: 0.7, marginTop: 6 }}>
              converts extracted motion into apply_humanoid_motion action
            </div>
          </div>
        )}

        {type === "robot_state" && (
          <div>
            state:{" "}
            <span style={{ opacity: 0.85 }}>
              {JSON.stringify(data?.robotState ?? {}).slice(0, 56)}
            </span>
            {renderRobotStateRuntime(data)}
          </div>
        )}

        {type === "unity_state" && (
          <div>
            client: <b>{String(data?.clientId ?? "default")}</b>
            <div style={{ fontSize: 11, opacity: 0.7 }}>
              latest: run to fetch current Unity robot state
            </div>
            <InfoRow
              label="endpoint"
              value={String(data?.omniverseEndpoint ?? "ws://host.docker.internal:9900/omniverse")}
            />
            {onIsaacGr00tInit && (
              <button
                className="nodrag nowheel"
                disabled={String(data?.initStatus ?? "") === "running"}
                onClick={(event) => {
                  event.stopPropagation();
                  onIsaacGr00tInit();
                }}
                onMouseDown={stopEvent}
                style={{
                  ...nodeActionStyle,
                  opacity: String(data?.initStatus ?? "") === "running" ? 0.65 : 1,
                  cursor: String(data?.initStatus ?? "") === "running" ? "wait" : "pointer",
                }}
                title="Send command: init to the Isaac Sim Omniverse bridge"
              >
                {String(data?.initStatus ?? "") === "running" ? "Initializing..." : "Init GR00T Scene"}
              </button>
            )}
            {String(data?.initStatus ?? "idle") !== "idle" && (
              <div style={{ fontSize: 11, opacity: 0.78, marginTop: 6 }}>
                init: {String(data?.initMessage ?? data?.initStatus ?? "")}
                {data?.initPrimPath ? ` / ${String(data.initPrimPath)}` : ""}
              </div>
            )}
            {renderRobotStateRuntime(data)}
          </div>
        )}

        {type === "openvla_infer" && (
          <div>
            model: <b>{String(data?.modelName ?? "openvla-stub")}</b>
            <div style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>
              optional: connect LiDAR or fused sensor JSON for obstacle context
            </div>
          </div>
        )}

        {type === "gr00t_infer" && (
          <div>
            model: <b>{String(data?.modelName ?? "nvidia/GR00T-N1.7-3B")}</b>
            <div style={{ fontSize: 11, opacity: 0.78, marginTop: 4 }}>
              embodiment: {String(data?.embodimentTag ?? "REAL_G1")}
            </div>
            <div style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>
              horizon: {String(data?.actionHorizon ?? 40)} / {String(data?.inferenceMode ?? "pytorch")}
            </div>
          </div>
        )}

        {type === "action_decode" && (
          <div>
            mode: <b>{String(data?.decodeMode ?? "default")}</b>
          </div>
        )}

        {type === "safety_clamp" && (
          <div>
            clamp: <b>{Boolean(data?.enabled ?? true) ? "enabled" : "disabled"}</b>
            <div style={{ fontSize: 11, opacity: 0.7 }}>
              max Δ: {String(data?.maxDelta ?? 0.05)}
            </div>
          </div>
        )}

            {type === "robot_execute" && renderRobotExecute(data, id, onNodeDataChange)}

        {type === "dataset_upload" && (
          <div>
            path:{" "}
            <span style={{ opacity: 0.85 }}>
              {String(data?.datasetPath ?? "").slice(0, 42)}
            </span>
            <div style={{ fontSize: 11, opacity: 0.7, marginBottom: 6 }}>
              format: {String(data?.datasetFormat ?? "jsonl")}
            </div>
            <label
              onClick={stopEvent}
              onMouseDown={stopEvent}
              style={nodeActionStyle}
            >
              Upload Dataset
              <input
                type="file"
                hidden
                accept=".ls,.tp,.jsonl,.json,.csv,text/csv,application/json"
                onChange={(event) => handleFileInputChange(event, data?.onDatasetUpload)}
              />
            </label>
            {Boolean(data?.initialSettingsEnabled) && (
              <div style={{ marginTop: 10 }}>
                initial LS:{" "}
                <span style={{ opacity: 0.85 }}>
                  {String(data?.initialSettingsPath ?? "").slice(0, 42)}
                </span>
                <div style={{ fontSize: 11, opacity: 0.7, marginBottom: 6 }}>
                  format: {String(data?.initialSettingsFormat ?? data?.datasetFormat ?? "ls")}
                </div>
                <label
                  onClick={stopEvent}
                  onMouseDown={stopEvent}
                  style={nodeActionStyle}
                >
                  Upload Initial LS
                  <input
                    type="file"
                    hidden
                    accept=".ls,.tp,text/plain"
                    onChange={(event) =>
                      handleFileInputChange(event, data?.onInitialSettingsUpload)
                    }
                  />
                </label>
              </div>
            )}
          </div>
        )}

        {type === "model_sync" && (
          <div>
            target: <b>{String(data?.targetName ?? "Cosmos-Reason2-2B")}</b>
            <div style={{ fontSize: 11, opacity: 0.78, marginTop: 4 }}>
              source: {String(data?.sourcePath ?? "/host_downloads/Cosmos-Reason2-2B").slice(0, 42)}
            </div>
            <div style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>
              overwrite: {Boolean(data?.overwrite ?? false) ? "true" : "false"}
            </div>
          </div>
        )}

        {type === "dataset_preview" && (
          <div>
            rows: <b>{String(data?.maxRows ?? 3)}</b>
          </div>
        )}

        {type === "openvla_finetune" && (
          <div>
            base: <b>{String(data?.baseModel ?? "openvla/openvla-7b")}</b>
            <div style={{ fontSize: 11, opacity: 0.7 }}>
              epochs: {String(data?.epochs ?? 1)} / batch: {String(data?.batchSize ?? 2)}
            </div>
          </div>
        )}

        {type === "speech_to_text" && (
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 8,
                marginBottom: 8,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <InfoRow label="engine" value={<b>{speechProviderLabel(data?.provider)}</b>} strong />
              </div>
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  minHeight: 22,
                  padding: "0 9px",
                  borderRadius: 999,
                  border: "1px solid rgba(125,211,252,0.35)",
                  background: "rgba(14,165,233,0.16)",
                  color: "#e0f2fe",
                  fontSize: 11,
                  fontWeight: 800,
                }}
              >
                {speechTaskLabel(data?.task)}
              </span>
            </div>
            <Panel
              tint="rgba(14,165,233,0.08)"
              border="1px solid rgba(125,211,252,0.16)"
            >
              <InfoRow label="input" value={speechLanguageLabel(data?.language ?? "auto")} />
              <InfoRow label="output" value={speechOutputLabel(data?.task)} />
              <InfoRow label="audio" value={compactAssetLabel(data?.audioPath)} />
            </Panel>
            <label
              onClick={stopEvent}
              onMouseDown={stopEvent}
              style={nodeActionStyle}
            >
              Upload Audio
              <input
                type="file"
                hidden
                accept="audio/*"
                onChange={(event) => handleFileInputChange(event, data?.onAudioUpload)}
              />
            </label>
            <button
              onClick={(event) => {
                stopEvent(event);
                if (data?.isMicRecording) {
                  data?.onStopMic?.();
                } else {
                  data?.onStartMic?.();
                }
              }}
              onMouseDown={stopEvent}
              style={{
                ...nodeActionStyle,
                background: Boolean(data?.isMicRecording)
                  ? "rgba(153,27,27,0.85)"
                  : "rgba(255,255,255,0.08)",
                border: Boolean(data?.isMicRecording)
                  ? "1px solid rgba(252,165,165,0.45)"
                  : "1px solid rgba(255,255,255,0.14)",
              }}
            >
              {Boolean(data?.isMicRecording) ? "Stop Mic" : "Start Mic"}
            </button>
            <div
              onClick={stopEvent}
              onMouseDown={stopEvent}
              style={{
                marginTop: 8,
                padding: "8px 10px",
                borderRadius: 999,
                border: Boolean(data?.isMicRecording)
                  ? "1px solid rgba(252,165,165,0.45)"
                  : "1px solid rgba(255,255,255,0.12)",
                background: Boolean(data?.isMicRecording)
                  ? "rgba(127,29,29,0.35)"
                  : "rgba(255,255,255,0.06)",
                color: Boolean(data?.isMicRecording) ? "#fecaca" : "#cbd5e1",
                fontSize: 11,
                fontWeight: 700,
                textAlign: "center",
              }}
            >
              {String(data?.micStatus ?? "Microphone ready")}
            </div>
            <div style={{ marginTop: 8, fontSize: 11, opacity: 0.72, lineHeight: 1.45 }}>
              {String(data?.task ?? "transcribe") === "translate"
                ? "한국어 같은 비영어 음성을 영어 텍스트로 바꿔 다음 노드에 넘깁니다."
                : "음성을 원문 그대로 텍스트로 추출해 다음 노드에 넘깁니다."}
            </div>
          </div>
        )}

        {type === "print" && <div>prints input</div>}
      </div>

      {(lastSummary || lastDetail) && (
        <div
          style={{
            marginTop: 10,
            padding: "9px 10px",
            borderRadius: 12,
            border:
              status === "error"
                ? "1px solid rgba(248,113,113,0.28)"
                : status === "running"
                ? "1px solid rgba(251,191,36,0.28)"
                : "1px solid rgba(96,165,250,0.22)",
            background:
              status === "error"
                ? "rgba(127,29,29,0.24)"
                : status === "running"
                ? "rgba(120,53,15,0.24)"
                : "rgba(15,23,42,0.35)",
          }}
        >
          <div
            style={{
              fontSize: 10,
              fontWeight: 800,
              letterSpacing: 0.24,
              color: "#93c5fd",
              textTransform: "uppercase",
            }}
          >
            Latest Run
          </div>
          {lastSummary && (
            <div
              style={{
                marginTop: 4,
                fontSize: 12,
                fontWeight: 800,
                color: "#f8fafc",
              }}
            >
              {lastSummary}
            </div>
          )}
          {lastDetail && (
            <div
              style={{
                marginTop: 4,
                fontSize: 11,
                lineHeight: 1.45,
                color: "#cbd5e1",
              }}
            >
              {lastDetail}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
