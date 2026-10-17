# -*- coding: utf-8 -*-
"""回放核心:Controller 注入 + 固定次数循环 + 软急停 + 拖拽插值。

- 延迟用 perf_counter 绝对目标时刻校准(不 sleep 累加,防漂移)
- 急停:每事件边界查 abort 标志,退出前补发所有 held 键/按钮(软停,防卡键)
- 拖拽:down(x1,y1) 与 up(x2,y2) 坐标差>阈值时插值移动,否则被控件判为单击
"""
import time
import math
import threading
from pynput import mouse, keyboard as kb

# 所有特殊键名(Key 枚举成员名),用于回放重建
_SPECIAL = {k.name for k in kb.Key}
_BTN = {
    "left": mouse.Button.left,
    "right": mouse.Button.right,
    "middle": mouse.Button.middle,
}


def _rebuild_key(ev):
    name = ev.get("name")
    if name and name in _SPECIAL:
        return getattr(kb.Key, name)
    if name and len(name) == 1:
        return name  # 普通字符
    if name:
        return name  # fallback
    return None


class Player:
    def __init__(self, events, loop=1, on_progress=None, on_done=None):
        self.events = events or []
        self.loop = max(1, int(loop))
        self.on_progress = on_progress
        self.on_done = on_done
        self.abort = threading.Event()
        self._thread = None
        self._mc = mouse.Controller()
        self._kc = kb.Controller()
        self._held = set()       # 回放期间按下的键名
        self._drag_start = None  # 当前按下位置(拖拽检测)

    def _move(self, x, y):
        try:
            self._mc.position = (int(x), int(y))
        except Exception:
            pass

    def _interpolate(self, p1, p2):
        x1, y1 = p1
        x2, y2 = p2
        dist = math.hypot(x2 - x1, y2 - y1)
        steps = max(1, int(dist / 8))
        for s in range(1, steps + 1):
            if self.abort.is_set():
                break
            self._move(x1 + (x2 - x1) * s / steps, y1 + (y2 - y1) * s / steps)
            time.sleep(0.005)

    def _inject(self, ev):
        t = ev.get("type")
        if t == "mouse":
            btn = _BTN.get(ev.get("button"), mouse.Button.left)
            if ev.get("action") == "down":
                self._move(ev["x"], ev["y"])
                try:
                    self._mc.press(btn)
                except Exception:
                    pass
                self._drag_start = (ev["x"], ev["y"])
            else:
                if self._drag_start and (
                    abs(ev["x"] - self._drag_start[0]) > 3
                    or abs(ev["y"] - self._drag_start[1]) > 3
                ):
                    self._interpolate(self._drag_start, (ev["x"], ev["y"]))
                else:
                    self._move(ev["x"], ev["y"])
                try:
                    self._mc.release(btn)
                except Exception:
                    pass
                self._drag_start = None
        elif t == "scroll":
            self._move(ev["x"], ev["y"])
            try:
                self._mc.scroll(int(ev.get("dx", 0)), int(ev.get("dy", 0)))
            except Exception:
                pass
        elif t == "key":
            k = _rebuild_key(ev)
            if k is None:
                return
            if ev.get("action") == "down":
                try:
                    self._kc.press(k)
                    self._held.add(ev.get("name"))
                except Exception:
                    pass
            else:
                try:
                    self._kc.release(k)
                except Exception:
                    pass
                self._held.discard(ev.get("name"))

    def _release_all(self):
        for name in list(self._held):
            k = _rebuild_key({"name": name})
            if k is not None:
                try:
                    self._kc.release(k)
                except Exception:
                    pass
        self._held.clear()
        for b in (mouse.Button.left, mouse.Button.right, mouse.Button.middle):
            try:
                self._mc.release(b)
            except Exception:
                pass

    def _run(self):
        completed = True
        try:
            for i in range(self.loop):
                if self.abort.is_set():
                    completed = False
                    break
                if self.on_progress:
                    try:
                        self.on_progress(i + 1, self.loop)
                    except Exception:
                        pass
                loop_start = time.perf_counter()
                self._drag_start = None
                for ev in self.events:
                    if self.abort.is_set():
                        completed = False
                        break
                    target = loop_start + ev.get("t", 0) / 1000.0
                    slip = target - time.perf_counter()
                    if slip > 0:
                        time.sleep(slip)
                    self._inject(ev)
        finally:
            self._release_all()
            if self.on_done:
                try:
                    self.on_done(completed)
                except Exception:
                    pass

    def start(self):
        self.abort.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.abort.set()
