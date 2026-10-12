import React, { useCallback, useEffect, useRef, useState } from "react";
import { Handle, NodeProps, Position } from "reactflow";
import {
  getSensorSourceMode,
  NODE_DEF_BY_TYPE,
  nodeColor,
  pinColor,
} from "../../../nodeDefs";

function stopEvent(event: React.SyntheticEvent) {
  event.stopPropagation();
}

function getStatusBorder(status: string, selected: boolean) {
  if (status === "running") return "1px solid #f59e0b";
  if (status === "ok" || status === "success") return "1px solid #22c55e";
  if (status === "error") return "1px solid #ef4444";
  if (selected) return "1px solid #60a5fa";
  return "1px solid #1e293b";
}

function ActionButton({
  children,
  onClick,
  active = false,
}: {
  children: React.ReactNode;
  onClick: (event: React.MouseEvent<HTMLButtonElement>) => void;
  active?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      onMouseDown={stopEvent}
      style={{
        width: "100%",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 32,
        marginTop: 8,
        padding: "8px 10px",
        borderRadius: 10,
        border: active
          ? "1px solid rgba(125,211,252,0.5)"
          : "1px solid rgba(255,255,255,0.14)",
        background: active ? "rgba(14,116,144,0.42)" : "rgba(255,255,255,0.08)",
        color: "#f8fafc",
        fontSize: 12,
        fontWeight: 700,
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );
}

function InfoRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 4 }}>
      <span style={{ opacity: 0.7 }}>{label}: </span>
      <span style={{ opacity: 0.95, fontWeight: 600 }}>{value}</span>
    </div>
  );
}

function truncate(value: unknown, max = 36) {
  const text = String(value ?? "");
  if (text.length <= max) return text || "-";
  return `${text.slice(0, max - 3)}...`;
}

function StableImagePreview({
  src,
  alt,
  children,
}: {
  src: string;
  alt: string;
  children: React.ReactNode;
}) {
  const [displaySrc, setDisplaySrc] = useState(src || "");

  useEffect(() => {
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
    image.onerror = () => {
      // Keep the previous decoded frame visible during transient sensor misses.
    };
    image.src = src;

    return () => {
      cancelled = true;
    };
  }, [displaySrc, src]);

  if (!displaySrc) {
    return <>{children}</>;
  }

  return (
    <img
      src={displaySrc}
      alt={alt}
      decoding="async"
      style={{ width: "100%", display: "block", aspectRatio: "4 / 3", objectFit: "cover" }}
    />
  );
}

function formatJson(value: unknown) {
  if (value == null) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function JsonPreview({
  label,
  value,
}: {
  label: string;
  value: unknown;
}) {
  const text = formatJson(value);
  if (!text) return null;

  return (
    <div
      onClick={stopEvent}
      onMouseDown={stopEvent}
      style={{
        marginTop: 8,
        borderRadius: 12,
        border: "1px solid rgba(255,255,255,0.12)",
        background: "rgba(2,6,23,0.6)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "7px 10px",
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: 0.2,
          color: "#cbd5e1",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          background: "rgba(255,255,255,0.04)",
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>
      <pre
        style={{
          margin: 0,
          padding: 10,
          maxHeight: 150,
          overflow: "auto",
          fontSize: 10,
          lineHeight: 1.45,
          color: "#dbeafe",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {text}
      </pre>
    </div>
  );
}

function finiteNumber(value: unknown) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function normalizePreviewPoints(value: unknown): number[][] {
  if (!value || typeof value !== "object") return [];
  const points = (value as { points?: unknown }).points;
  if (!Array.isArray(points)) return [];

  const normalized: number[][] = [];
  for (const point of points) {
    if (!Array.isArray(point) || point.length < 2) continue;
    const x = finiteNumber(point[0]);
    const y = finiteNumber(point[1]);
    const z = finiteNumber(point[2]) ?? 0;
    if (x == null || y == null) continue;
    normalized.push([x, y, z]);
  }
  return normalized;
}

function LidarPointCloudPreview({ value }: { value: unknown }) {
  const points = normalizePreviewPoints(value);
  const payload = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const pointCount = Number(payload.pointCount ?? points.length) || points.length;
  const sampledCount = Number(payload.sampledCount ?? points.length) || points.length;
  const nearestRange = finiteNumber(payload.nearestRange);
  const obstacleCount = Number(payload.obstacleCount ?? 0) || 0;
  const configuredRange = finiteNumber(payload.rangeMax);
  const pointRadius = points.reduce((max, point) => {
    const radius = Math.hypot(point[0], point[1]);
    return Number.isFinite(radius) ? Math.max(max, radius) : max;
  }, 0);
  const range = Math.max(configuredRange ?? 0, pointRadius, 1);
  const size = 180;
  const center = size / 2;
  const padding = 14;
  const scale = (center - padding) / range;
  const gridRadius = Math.max(8, range * scale);

  if (!value) {
    return null;
  }

  return (
    <div
      onClick={stopEvent}
      onMouseDown={stopEvent}
      style={{
        marginTop: 8,
        borderRadius: 12,
        border: "1px solid rgba(255,255,255,0.12)",
        background: "rgba(2,6,23,0.6)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "7px 10px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          background: "rgba(255,255,255,0.04)",
        }}
      >
        <span style={{ fontSize: 10, fontWeight: 800, color: "#cbd5e1", textTransform: "uppercase" }}>
          Point Cloud
        </span>
        <span style={{ fontSize: 10, color: "#93c5fd", fontWeight: 700 }}>
          {sampledCount}/{pointCount}
        </span>
      </div>

      <svg
        viewBox={`0 0 ${size} ${size}`}
        width="100%"
        height="180"
        role="img"
        aria-label="LiDAR point cloud preview"
        style={{ display: "block", background: "rgba(8,13,25,0.78)" }}
      >
        <circle
          cx={center}
          cy={center}
          r={gridRadius}
          fill="none"
          stroke="rgba(148,163,184,0.22)"
          strokeWidth="1"
        />
        <line x1={center} y1={padding} x2={center} y2={size - padding} stroke="rgba(148,163,184,0.16)" />
        <line x1={padding} y1={center} x2={size - padding} y2={center} stroke="rgba(148,163,184,0.16)" />
        <path
          d={`M ${center} ${center} L ${center - gridRadius} ${center} A ${gridRadius} ${gridRadius} 0 0 1 ${center + gridRadius} ${center} Z`}
          fill="rgba(59,130,246,0.06)"
          stroke="rgba(59,130,246,0.16)"
          strokeWidth="1"
        />
        <circle cx={center} cy={center} r="3" fill="#f8fafc" />
        {points.map((point, index) => {
          const px = center + point[1] * scale;
          const py = center - point[0] * scale;
          const distance = Math.hypot(point[0], point[1]);
          const near = nearestRange != null && Math.abs(distance - nearestRange) < 0.05;
          return (
            <circle
              key={`${index}-${point[0]}-${point[1]}`}
              cx={px}
              cy={py}
              r={near ? 2.4 : 1.6}
              fill={near ? "#f97316" : "#38bdf8"}
              opacity={near ? 0.95 : 0.72}
            />
          );
        })}
      </svg>

      <div style={{ padding: "8px 10px", fontSize: 11, color: "#cbd5e1", display: "grid", gap: 3 }}>
        <InfoRow label="nearest" value={nearestRange == null ? "-" : `${nearestRange.toFixed(2)} m`} />
        <InfoRow label="obstacle rays" value={obstacleCount} />
      </div>
    </div>
  );
}

export default function SensorInputNode(props: NodeProps) {
  const { id, type, data, selected } = props;
  const nodeType = type ?? "sensor_input";
  const def = NODE_DEF_BY_TYPE[nodeType] ?? NODE_DEF_BY_TYPE.sensor_input;
  const status = String(data?.status ?? "idle");
  const autoStartKeyRef = useRef("");

  const sourceMode = getSensorSourceMode(nodeType, data?.sourceMode);
  const cameraDeviceId = String(data?.cameraDeviceId ?? "");
  const cameraFacingMode = String(data?.cameraFacingMode ?? "environment");
  const captureWidth = Number(data?.captureWidth ?? 1280);
  const captureHeight = Number(data?.captureHeight ?? 720);
  const capturedFrame = String(data?.capturedFrame ?? "");
  const remoteImageUrl = String(data?.remoteImageUrl ?? "");
  const remoteLidarUrl = String(data?.remoteLidarUrl ?? "");
  const remoteImageTransport = String(data?.remoteImageTransport ?? "snapshot");
  const rtspTransport = String(data?.rtspTransport ?? "tcp");
  const lidarFormat = String(data?.lidarFormat ?? "auto");
  const lidarObstacleDistance = Number(data?.lidarObstacleDistance ?? 1.0);
  const lastCapturedAt = String(data?.lastCapturedAt ?? "");
  const lastImageFrame = String(data?.lastImageFrame ?? "");
  const lastRawLidarJson = data?.lastRawLidarJson;
  const lastLidarOutputJson = data?.lastLidarOutputJson;
  const lastLidarPointPreview = data?.lastLidarPointPreview;

  const onNodeDataChange =
    data?.onNodeDataChange as
      | ((nodeId: string, key: string, value: unknown) => void)
      | undefined;

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [cameraStatus, setCameraStatus] = useState("Camera idle");

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.srcObject = null;
    }

    setIsStreaming(false);
    setCameraStatus("Camera stopped");
  }, []);

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (sourceMode !== "camera" && isStreaming) {
      stopCamera();
    }
  }, [isStreaming, sourceMode, stopCamera]);

  const startCamera = useCallback(async () => {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setCameraStatus("Camera API unavailable");
      return;
    }

    try {
      setCameraStatus("Connecting camera...");
      const constraints: MediaTrackConstraints = {
        width: captureWidth > 0 ? { ideal: captureWidth } : undefined,
        height: captureHeight > 0 ? { ideal: captureHeight } : undefined,
      };

      if (cameraDeviceId.trim()) {
        constraints.deviceId = { exact: cameraDeviceId.trim() };
      } else {
        constraints.facingMode = cameraFacingMode || "environment";
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: constraints,
        audio: false,
      });

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        try {
          await videoRef.current.play();
        } catch {
          // noop
        }
      }

      setIsStreaming(true);
      setCameraStatus("Live camera connected");
    } catch (error) {
      setCameraStatus(
        error instanceof Error ? `Camera error: ${error.message}` : "Camera start failed"
      );
    }
  }, [cameraDeviceId, cameraFacingMode, captureHeight, captureWidth]);

  useEffect(() => {
    if (sourceMode !== "camera") {
      autoStartKeyRef.current = "";
      return;
    }

    if (isStreaming) {
      return;
    }

    const autoStartKey = [
      id,
      cameraDeviceId.trim(),
      cameraFacingMode,
      captureWidth,
      captureHeight,
    ].join("|");

    if (autoStartKeyRef.current === autoStartKey) {
      return;
    }

    autoStartKeyRef.current = autoStartKey;
    void startCamera();
  }, [
    cameraDeviceId,
    cameraFacingMode,
    captureHeight,
    captureWidth,
    id,
    isStreaming,
    sourceMode,
    startCamera,
  ]);

  useEffect(() => {
    if (sourceMode !== "camera" || !isStreaming || !streamRef.current || !videoRef.current) {
      return;
    }

    const video = videoRef.current;
    const stream = streamRef.current;

    if (video.srcObject !== stream) {
      video.srcObject = stream;
    }

    let disposed = false;

    const syncPreview = async () => {
      try {
        await video.play();
        if (!disposed) {
          setCameraStatus("Live camera connected");
        }
      } catch (error) {
        if (!disposed) {
          setCameraStatus(
            error instanceof Error ? `Camera preview error: ${error.message}` : "Camera preview error"
          );
        }
      }
    };

    void syncPreview();

    return () => {
      disposed = true;
    };
  }, [isStreaming, sourceMode]);

  const captureFrame = useCallback(() => {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
      setCameraStatus("Camera preview not ready");
      return;
    }

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context) {
      setCameraStatus("Canvas capture unavailable");
      return;
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const nextFrame = canvas.toDataURL("image/jpeg", 0.92);
    const capturedAt = new Date().toISOString();

    onNodeDataChange?.(id, "capturedFrame", nextFrame);
    onNodeDataChange?.(id, "lastCapturedAt", capturedAt);
    setCameraStatus("Frame captured");
  }, [id, onNodeDataChange]);

  const width = Number(data?.__ui?.w ?? def.width ?? 320);

  return (
    <div
      style={{
        width,
        minHeight: 150,
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
      {def.inputs.map((pin, idx) => (
        <Handle
          key={`in-${pin.id}`}
          type="target"
          id={pin.id}
          position={Position.Left}
          style={{
            top: 48 + idx * 18,
            left: -5,
            width: 8,
            height: 8,
            borderRadius: 999,
            border: "1px solid rgba(255,255,255,0.9)",
            background: pinColor(pin.pinType),
          }}
        />
      ))}

      {def.outputs.map((pin, idx) => (
        <Handle
          key={`out-${pin.id}`}
          type="source"
          id={pin.id}
          position={Position.Right}
          style={{
            top: 48 + idx * 18,
            right: -5,
            width: 8,
            height: 8,
            borderRadius: 999,
            border: "1px solid rgba(255,255,255,0.9)",
            background: pinColor(pin.pinType),
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
          onClick={(event) => {
            stopEvent(event);
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

      <div style={{ fontSize: 12, lineHeight: 1.45, color: "#d6e2f3" }}>
        <InfoRow label="mode" value={sourceMode} />

        {sourceMode === "camera" && (
          <>
            <InfoRow
              label="camera"
              value={cameraDeviceId ? truncate(cameraDeviceId) : cameraFacingMode}
            />
            <InfoRow label="size" value={`${captureWidth} x ${captureHeight}`} />

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
              {isStreaming ? (
                <video
                  ref={videoRef}
                  autoPlay
                  muted
                  playsInline
                  style={{ width: "100%", display: "block", aspectRatio: "4 / 3", objectFit: "cover" }}
                />
              ) : capturedFrame ? (
                <img
                  src={capturedFrame}
                  alt="Captured sensor frame"
                  style={{ width: "100%", display: "block", aspectRatio: "4 / 3", objectFit: "cover" }}
                />
              ) : (
                <div
                  style={{
                    aspectRatio: "4 / 3",
                    display: "grid",
                    placeItems: "center",
                    color: "#94a3b8",
                    fontSize: 11,
                    textAlign: "center",
                    padding: 12,
                  }}
                >
                  Camera preview will appear here
                </div>
              )}
            </div>

            {!isStreaming ? (
              <ActionButton
                onClick={(event) => {
                  stopEvent(event);
                  void startCamera();
                }}
              >
                Start Camera
              </ActionButton>
            ) : (
              <>
                <ActionButton
                  active
                  onClick={(event) => {
                    stopEvent(event);
                    captureFrame();
                  }}
                >
                  Capture Frame
                </ActionButton>
                <ActionButton
                  onClick={(event) => {
                    stopEvent(event);
                    stopCamera();
                  }}
                >
                  Stop Camera
                </ActionButton>
              </>
            )}

            <div
              onClick={stopEvent}
              onMouseDown={stopEvent}
              style={{
                marginTop: 8,
                padding: "8px 10px",
                borderRadius: 999,
                border: "1px solid rgba(255,255,255,0.12)",
                background: "rgba(255,255,255,0.06)",
                color: "#cbd5e1",
                fontSize: 11,
                fontWeight: 700,
                textAlign: "center",
              }}
            >
              {cameraStatus}
            </div>

            {lastCapturedAt && (
              <div style={{ marginTop: 6, fontSize: 11, opacity: 0.72 }}>
                captured: {truncate(lastCapturedAt, 28)}
              </div>
            )}
          </>
        )}

        {sourceMode === "remote_image" && (
          <>
            <div
              onClick={stopEvent}
              onMouseDown={stopEvent}
              style={{
                marginTop: 8,
                marginBottom: 8,
                borderRadius: 12,
                overflow: "hidden",
                border: "1px solid rgba(255,255,255,0.12)",
                background: "rgba(2,6,23,0.6)",
              }}
            >
              <StableImagePreview src={lastImageFrame} alt="Remote sensor frame">
                <div
                  style={{
                    aspectRatio: "4 / 3",
                    display: "grid",
                    placeItems: "center",
                    color: "#94a3b8",
                    fontSize: 11,
                    textAlign: "center",
                    padding: 12,
                  }}
                >
                  Remote image preview will appear here
                </div>
              </StableImagePreview>
            </div>
            <InfoRow label="image url" value={truncate(remoteImageUrl, 40)} />
            <InfoRow label="transport" value={remoteImageTransport} />
            {remoteImageTransport === "rtsp" && (
              <InfoRow label="rtsp" value={rtspTransport} />
            )}
            <div style={{ marginTop: 6, fontSize: 11, opacity: 0.72 }}>
              Runtime fetches the latest remote frame and emits it through the `image` pin.
            </div>
          </>
        )}

        {sourceMode === "remote_lidar" && (
          <>
            <InfoRow label="lidar url" value={truncate(remoteLidarUrl, 40)} />
            <InfoRow label="format" value={lidarFormat} />
            <InfoRow label="near obstacle" value={`${lidarObstacleDistance.toFixed(2)} m`} />
            <div style={{ marginTop: 6, fontSize: 11, opacity: 0.72 }}>
              LiDAR payload is normalized as point cloud or laser scan at run time.
            </div>
            {!lastRawLidarJson && !lastLidarOutputJson && (
              <div style={{ marginTop: 6, fontSize: 11, opacity: 0.72 }}>
                Run Graph 후 원본 JSON과 정규화 JSON preview가 여기에 표시됩니다.
              </div>
            )}
            <LidarPointCloudPreview value={lastLidarPointPreview} />
            <JsonPreview label="Raw JSON" value={lastRawLidarJson} />
            <JsonPreview label="Normalized JSON" value={lastLidarOutputJson} />
          </>
        )}

        {sourceMode === "fused" && (
          <>
            <div
              onClick={stopEvent}
              onMouseDown={stopEvent}
              style={{
                marginTop: 8,
                marginBottom: 8,
                borderRadius: 12,
                overflow: "hidden",
                border: "1px solid rgba(255,255,255,0.12)",
                background: "rgba(2,6,23,0.6)",
              }}
            >
              <StableImagePreview src={capturedFrame || lastImageFrame} alt="Fused sensor frame">
                <div
                  style={{
                    aspectRatio: "4 / 3",
                    display: "grid",
                    placeItems: "center",
                    color: "#94a3b8",
                    fontSize: 11,
                    textAlign: "center",
                    padding: 12,
                  }}
                >
                  Fused image preview will appear here
                </div>
              </StableImagePreview>
            </div>
            <InfoRow
              label="image source"
              value={capturedFrame ? "captured camera frame" : truncate(remoteImageUrl, 34)}
            />
            <InfoRow label="transport" value={remoteImageTransport} />
            {remoteImageTransport === "rtsp" && (
              <InfoRow label="rtsp" value={rtspTransport} />
            )}
            <InfoRow label="lidar url" value={truncate(remoteLidarUrl, 34)} />
            <InfoRow label="lidar format" value={lidarFormat} />
            <InfoRow label="near obstacle" value={`${lidarObstacleDistance.toFixed(2)} m`} />
            <div style={{ marginTop: 6, fontSize: 11, opacity: 0.72 }}>
              Uses the captured frame first, then falls back to the remote image endpoint.
            </div>
            {(lastRawLidarJson || lastLidarOutputJson) && (
              <>
                <LidarPointCloudPreview value={lastLidarPointPreview} />
                <JsonPreview label="Raw LiDAR JSON" value={lastRawLidarJson} />
                <JsonPreview label="Normalized LiDAR JSON" value={lastLidarOutputJson} />
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
