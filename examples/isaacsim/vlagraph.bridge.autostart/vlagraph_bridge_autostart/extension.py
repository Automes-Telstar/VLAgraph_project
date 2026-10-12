import time
import traceback
from pathlib import Path

import omni.ext
import omni.kit.app


BRIDGE_STARTER = Path(r"C:/Users/0/Desktop/vlagraph/examples/isaacsim/StartVlaGraphBridge9900.py")


class Extension(omni.ext.IExt):
    def on_startup(self, ext_id):
        self._started = False
        self._start_at = time.time() + 3.0
        self._subscription = (
            omni.kit.app.get_app()
            .get_update_event_stream()
            .create_subscription_to_pop(
                self._on_update,
                name="VLA Graph Bridge Autostart",
            )
        )

    def on_shutdown(self):
        if getattr(self, "_subscription", None) is not None:
            try:
                self._subscription.unsubscribe()
            except Exception:
                pass
            self._subscription = None

    def _on_update(self, _event):
        if self._started or time.time() < self._start_at:
            return

        self._started = True
        if getattr(self, "_subscription", None) is not None:
            try:
                self._subscription.unsubscribe()
            except Exception:
                pass
            self._subscription = None
        self._start_bridge()

    def _start_bridge(self):
        try:
            namespace = {
                "__name__": "vlagraph_bridge_autostart_runner",
                "__file__": str(BRIDGE_STARTER),
            }
            exec(compile(BRIDGE_STARTER.read_text(encoding="utf-8"), str(BRIDGE_STARTER), "exec"), namespace)
        except Exception as exc:
            print(f"[VlaGraphBridgeAutostart] failed: {exc}")
            print(traceback.format_exc())
