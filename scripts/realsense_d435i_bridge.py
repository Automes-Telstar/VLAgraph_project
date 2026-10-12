from __future__ import annotations

import argparse
import base64
import contextlib
import io
import json
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict
from urllib.parse import urlsplit

import numpy as np
from PIL import Image


def _data_uri(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _jpeg_data_uri(array: np.ndarray, quality: int = 86) -> str:
    image = Image.fromarray(np.asarray(array).astype("uint8"), mode="RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return _data_uri(buffer.getvalue(), "image/jpeg")


def _depth_png_data_uri(depth_units: np.ndarray) -> str:
    image = Image.fromarray(np.asarray(depth_units).astype(np.uint16), mode="I;16")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=1)
    return _data_uri(buffer.getvalue(), "image/png")


def _depth_preview_data_uri(depth_units: np.ndarray, depth_scale: float) -> str:
    depth_m = np.asarray(depth_units).astype("float32") * float(depth_scale)
    valid = depth_m > 0
    norm = np.clip((depth_m - 0.2) / 3.8, 0.0, 1.0)
    rgb = np.zeros((*depth_m.shape, 3), dtype=np.uint8)
    rgb[..., 0] = (255.0 * norm).astype(np.uint8)
    rgb[..., 1] = (255.0 * (1.0 - np.abs(norm * 2.0 - 1.0))).astype(np.uint8)
    rgb[..., 2] = (255.0 * (1.0 - norm)).astype(np.uint8)
    rgb[~valid] = np.array([10, 16, 28], dtype=np.uint8)
    return _jpeg_data_uri(rgb, quality=82)


def _intrinsics_dict(intrinsics: Any, width: int, height: int) -> Dict[str, Any]:
    return {
        "width": int(getattr(intrinsics, "width", width) or width),
        "height": int(getattr(intrinsics, "height", height) or height),
        "fx": float(getattr(intrinsics, "fx", width) or width),
        "fy": float(getattr(intrinsics, "fy", width) or width),
        "ppx": float(getattr(intrinsics, "ppx", width / 2.0) or width / 2.0),
        "ppy": float(getattr(intrinsics, "ppy", height / 2.0) or height / 2.0),
        "model": str(getattr(intrinsics, "model", "unknown")),
        "coeffs": [float(item) for item in list(getattr(intrinsics, "coeffs", []) or [])[:5]],
    }


def _frame_number(frame: Any) -> Any:
    try:
        return int(frame.get_frame_number())
    except Exception:
        return None


def _frame_timestamp_ms(frame: Any) -> Any:
    try:
        return float(frame.get_timestamp())
    except Exception:
        return None


def _make_frame_id(source: str, color_frame_number: Any, depth_frame_number: Any, timestamp: float) -> str:
    if color_frame_number is not None or depth_frame_number is not None:
        color_part = color_frame_number if color_frame_number is not None else "x"
        depth_part = depth_frame_number if depth_frame_number is not None else "x"
        return f"{source}-c{color_part}-d{depth_part}"
    return f"{source}-{timestamp:.6f}"


def _clone_frame_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    cloned = dict(payload)
    if isinstance(payload.get("depth"), dict):
        cloned["depth"] = dict(payload["depth"])
    if isinstance(payload.get("sensor"), dict):
        sensor = dict(payload["sensor"])
        for key in ("rgb", "depth", "intrinsics", "metadata"):
            if isinstance(sensor.get(key), dict):
                sensor[key] = dict(sensor[key])
        cloned["sensor"] = sensor
    return cloned


class RealSenseCapture:
    def __init__(self, width: int, height: int, fps: int, serial: str = "", warmup: int = 8) -> None:
        import pyrealsense2 as rs

        self.rs = rs
        context = rs.context()
        devices = context.query_devices()
        if len(devices) == 0:
            raise RuntimeError("No device connected")
        if serial:
            serials = {
                str(device.get_info(rs.camera_info.serial_number))
                for device in devices
                if device.supports(rs.camera_info.serial_number)
            }
            if serial not in serials:
                raise RuntimeError(f"RealSense serial {serial} is not connected")

        self.pipeline = rs.pipeline()
        config = rs.config()
        if serial:
            config.enable_device(serial)
        config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
        config.enable_stream(rs.stream.color, width, height, rs.format.rgb8, fps)
        self.profile = self.pipeline.start(config)
        self.align = rs.align(rs.stream.color)
        self.depth_scale = float(self.profile.get_device().first_depth_sensor().get_depth_scale())
        for _ in range(max(0, warmup)):
            self.pipeline.wait_for_frames(5000)

    def frame(self) -> Dict[str, Any]:
        t0 = time.perf_counter()
        frames = self.pipeline.wait_for_frames(5000)
        t_wait = time.perf_counter()
        aligned = self.align.process(frames)
        t_align = time.perf_counter()
        depth_frame = aligned.get_depth_frame()
        color_frame = aligned.get_color_frame()
        if not depth_frame or not color_frame:
            raise RuntimeError("RealSense returned incomplete color/depth frames")

        rgb = np.asanyarray(color_frame.get_data()).astype(np.uint8)
        depth_units = np.asanyarray(depth_frame.get_data()).astype(np.uint16)
        t_arrays = time.perf_counter()
        height, width = int(rgb.shape[0]), int(rgb.shape[1])
        intrinsics = _intrinsics_dict(
            color_frame.profile.as_video_stream_profile().get_intrinsics(),
            width,
            height,
        )
        now = time.time()
        color_frame_number = _frame_number(color_frame)
        depth_frame_number = _frame_number(depth_frame)
        color_timestamp_ms = _frame_timestamp_ms(color_frame)
        depth_timestamp_ms = _frame_timestamp_ms(depth_frame)
        frame_id = _make_frame_id("rs", color_frame_number, depth_frame_number, now)
        color_image = _jpeg_data_uri(rgb)
        t_color_jpeg = time.perf_counter()
        depth_data_uri = _depth_png_data_uri(depth_units)
        t_depth_png = time.perf_counter()
        depth_preview = _depth_preview_data_uri(depth_units, self.depth_scale)
        t_depth_preview = time.perf_counter()
        timing_ms = {
            "wait_for_frames": round((t_wait - t0) * 1000.0, 2),
            "align": round((t_align - t_wait) * 1000.0, 2),
            "arrays": round((t_arrays - t_align) * 1000.0, 2),
            "color_jpeg": round((t_color_jpeg - t_arrays) * 1000.0, 2),
            "depth_png": round((t_depth_png - t_color_jpeg) * 1000.0, 2),
            "depth_preview": round((t_depth_preview - t_depth_png) * 1000.0, 2),
            "total_server": round((t_depth_preview - t0) * 1000.0, 2),
        }
        depth = {
            "type": "realsense_aligned_depth",
            "format": "z16_png",
            "data_uri": depth_data_uri,
            "preview_image": depth_preview,
            "width": int(depth_units.shape[1]),
            "height": int(depth_units.shape[0]),
            "scale_meters_per_unit": self.depth_scale,
            "intrinsics": intrinsics,
            "aligned_to": "color",
            "timestamp": now,
            "frame_id": frame_id,
            "frame_number": depth_frame_number,
            "realsense_timestamp_ms": depth_timestamp_ms,
        }
        return {
            "ok": True,
            "frame_id": frame_id,
            "image": color_image,
            "depth_image": depth["preview_image"],
            "depth": depth,
            "sensor": {
                "type": "realsense_d435i_frame",
                "source": "windows_host_bridge",
                "frame_id": frame_id,
                "color_frame_number": color_frame_number,
                "depth_frame_number": depth_frame_number,
                "color_timestamp_ms": color_timestamp_ms,
                "depth_timestamp_ms": depth_timestamp_ms,
                "rgb": {"width": width, "height": height, "content_type": "image/jpeg"},
                "depth": {
                    "width": int(depth_units.shape[1]),
                    "height": int(depth_units.shape[0]),
                    "format": "z16_png",
                    "scale_meters_per_unit": self.depth_scale,
                    "frame_number": depth_frame_number,
                },
                "intrinsics": intrinsics,
                "timestamp": now,
                "timing_ms": timing_ms,
            },
            "timestamp": now,
        }

    def stop(self) -> None:
        self.pipeline.stop()


class MockCapture:
    def __init__(self, width: int, height: int, warning: str = "") -> None:
        self.width = int(width)
        self.height = int(height)
        self.depth_scale = 0.001
        self.warning = warning
        self._frame_number = 0

    def frame(self) -> Dict[str, Any]:
        self._frame_number += 1
        x = np.linspace(0, 1, self.width, dtype=np.float32)
        y = np.linspace(0, 1, self.height, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)
        rgb = np.stack(
            [
                (40 + xx * 160).astype(np.uint8),
                (70 + yy * 120).astype(np.uint8),
                (120 + (1.0 - xx) * 80).astype(np.uint8),
            ],
            axis=-1,
        )
        depth_m = 0.7 + yy * 1.6 + np.sin(xx * np.pi) * 0.2
        depth_units = np.clip(depth_m / self.depth_scale, 0, 65535).astype(np.uint16)
        intrinsics = _intrinsics_dict(None, self.width, self.height)
        now = time.time()
        frame_id = _make_frame_id("mock", self._frame_number, self._frame_number, now)
        depth = {
            "type": "realsense_aligned_depth",
            "format": "z16_png",
            "data_uri": _depth_png_data_uri(depth_units),
            "preview_image": _depth_preview_data_uri(depth_units, self.depth_scale),
            "width": self.width,
            "height": self.height,
            "scale_meters_per_unit": self.depth_scale,
            "intrinsics": intrinsics,
            "aligned_to": "color",
            "timestamp": now,
            "frame_id": frame_id,
            "frame_number": self._frame_number,
        }
        return {
            "ok": True,
            "frame_id": frame_id,
            "image": _jpeg_data_uri(rgb),
            "depth_image": depth["preview_image"],
            "depth": depth,
            "sensor": {
                "type": "realsense_d435i_frame",
                "source": "mock",
                "warning": self.warning,
                "frame_id": frame_id,
                "color_frame_number": self._frame_number,
                "depth_frame_number": self._frame_number,
                "rgb": {"width": self.width, "height": self.height, "content_type": "image/jpeg"},
                "depth": {
                    "width": self.width,
                    "height": self.height,
                    "format": "z16_png",
                    "scale_meters_per_unit": self.depth_scale,
                    "frame_number": self._frame_number,
                },
                "intrinsics": intrinsics,
                "timestamp": now,
            },
            "timestamp": now,
        }

    def stop(self) -> None:
        return None


class ResilientRealSenseCapture:
    def __init__(
        self,
        width: int,
        height: int,
        fps: int,
        serial: str = "",
        warmup: int = 8,
        mock_when_unavailable: bool = False,
        reconnect_interval_sec: float = 1.5,
        frame_cache_ttl_sec: float = 0.06,
    ) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.serial = serial
        self.warmup = warmup
        self.mock_when_unavailable = mock_when_unavailable
        self.reconnect_interval_sec = max(0.25, float(reconnect_interval_sec))
        self.frame_cache_ttl_sec = max(0.0, float(frame_cache_ttl_sec))
        self._lock = threading.Lock()
        self._capture: Any = None
        self._source = "starting"
        self._last_error = ""
        self._last_connect_attempt = 0.0
        self._cached_payload = None
        self._cached_at = 0.0
        self._connect()

    def _connect(self) -> None:
        self._last_connect_attempt = time.time()
        self._invalidate_cache()
        try:
            self._capture = RealSenseCapture(
                self.width,
                self.height,
                self.fps,
                self.serial,
                self.warmup,
            )
            self._source = "realsense"
            self._last_error = ""
        except Exception as exc:
            self._last_error = str(exc)
            if not self.mock_when_unavailable:
                raise
            self._capture = MockCapture(self.width, self.height, warning=self._last_error)
            self._source = "mock"

    def _invalidate_cache(self) -> None:
        self._cached_payload = None
        self._cached_at = 0.0

    def _decorate_payload(self, payload: Dict[str, Any], *, cached: bool, cache_age_sec: float = 0.0) -> Dict[str, Any]:
        decorated = _clone_frame_payload(payload)
        if isinstance(decorated.get("sensor"), dict):
            decorated["sensor"]["bridge_source"] = self._source
            decorated["sensor"]["bridge_cached"] = bool(cached)
            if cached:
                decorated["sensor"]["bridge_cache_age_ms"] = round(max(0.0, cache_age_sec) * 1000.0, 2)
            if self._last_error:
                decorated["sensor"]["last_error"] = self._last_error
        return decorated

    def _cache_and_return(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        decorated = self._decorate_payload(payload, cached=False)
        self._cached_payload = _clone_frame_payload(decorated)
        self._cached_at = time.time()
        return decorated

    def _should_retry_real_camera(self) -> bool:
        if self._source != "mock":
            return False
        return (time.time() - self._last_connect_attempt) >= self.reconnect_interval_sec

    def _retry_real_camera_if_needed(self) -> None:
        if not self._should_retry_real_camera():
            return

        previous_capture = self._capture
        try:
            real_capture = RealSenseCapture(
                self.width,
                self.height,
                self.fps,
                self.serial,
                self.warmup,
            )
        except Exception as exc:
            self._last_connect_attempt = time.time()
            self._last_error = str(exc)
            if isinstance(previous_capture, MockCapture):
                previous_capture.warning = self._last_error
            return

        with contextlib.suppress(Exception):
            if previous_capture is not None:
                previous_capture.stop()
        self._capture = real_capture
        self._source = "realsense"
        self._last_error = ""
        self._last_connect_attempt = time.time()
        self._invalidate_cache()

    def frame(self) -> Dict[str, Any]:
        with self._lock:
            now = time.time()
            if (
                self.frame_cache_ttl_sec > 0.0
                and self._cached_payload is not None
                and now - self._cached_at <= self.frame_cache_ttl_sec
            ):
                return self._decorate_payload(
                    self._cached_payload,
                    cached=True,
                    cache_age_sec=now - self._cached_at,
                )

            self._retry_real_camera_if_needed()
            if self._capture is None:
                self._connect()
            try:
                return self._cache_and_return(self._capture.frame())
            except Exception as exc:
                self._last_error = str(exc)
                with contextlib.suppress(Exception):
                    self._capture.stop()
                self._capture = None
                self._invalidate_cache()
                if self.mock_when_unavailable:
                    self._capture = MockCapture(self.width, self.height, warning=self._last_error)
                    self._source = "mock"
                    return self._cache_and_return(self._capture.frame())
                self._connect()
                return self._cache_and_return(self._capture.frame())

    def status(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "service": "realsense_d435i_bridge",
            "source": self._source,
            "last_error": self._last_error,
            "mock_when_unavailable": self.mock_when_unavailable,
        }

    def stop(self) -> None:
        with self._lock:
            if self._capture is not None:
                self._capture.stop()
            self._capture = None
            self._invalidate_cache()


def make_handler(capture: RealSenseCapture):
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return

        def do_GET(self) -> None:
            request_path = urlsplit(self.path).path
            if request_path not in {"/", "/frame", "/health"}:
                self._send_json(404, {"ok": False, "error": "not found"})
                return
            if request_path == "/health":
                status = capture.status() if hasattr(capture, "status") else {"ok": True, "service": "realsense_d435i_bridge"}
                self._send_json(200, status)
                return
            try:
                self._send_json(200, capture.frame())
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve Intel RealSense D435i RGB-D frames as JSON.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9180)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--serial", default="")
    parser.add_argument("--warmup", type=int, default=8)
    parser.add_argument("--mock-when-unavailable", action="store_true")
    parser.add_argument("--reconnect-interval-sec", type=float, default=1.5)
    parser.add_argument("--frame-cache-ttl-sec", type=float, default=0.06)
    args = parser.parse_args()

    capture = ResilientRealSenseCapture(
        args.width,
        args.height,
        args.fps,
        args.serial,
        args.warmup,
        args.mock_when_unavailable,
        reconnect_interval_sec=args.reconnect_interval_sec,
        frame_cache_ttl_sec=args.frame_cache_ttl_sec,
    )
    server = ThreadingHTTPServer((args.host, args.port), make_handler(capture))
    print(f"RealSense D435i bridge listening on http://{args.host}:{args.port}/frame", flush=True)
    try:
        server.serve_forever()
    finally:
        capture.stop()


if __name__ == "__main__":
    main()
