// src/api/graph.ts
import { apiGet, apiPost } from "./client";

export async function runGraph(payload: any) {
  return apiPost("/api/graph/run", payload);
}

export async function startGraphRuntime(payload: any) {
  return apiPost("/api/graph/runtime/start", payload);
}

export async function getGraphRuntime(sessionId: string) {
  return apiGet(`/api/graph/runtime/${encodeURIComponent(sessionId)}`);
}

export async function cancelGraphRuntime(sessionId: string) {
  return apiPost(`/api/graph/runtime/${encodeURIComponent(sessionId)}/cancel`, {});
}

export async function initIsaacGr00tScene(payload: any) {
  return apiPost("/api/omniverse/isaac-gr00t/init", payload);
}

export async function getRealSenseBridgeStatus(port = 9180) {
  return apiGet(`/api/realsense/bridge/status?port=${encodeURIComponent(String(port))}`);
}

export async function startRealSenseBridge(payload: any) {
  return apiPost("/api/realsense/bridge/start", payload);
}

export async function stopRealSenseBridge() {
  return apiPost("/api/realsense/bridge/stop", {});
}
