# -*- coding: utf-8 -*-
"""录制核心:pynput 双 Listener。

- on_move 不注册 -> 鼠标移动轨迹天然不录
- 热键事件过滤:只过滤"单键热键"的成员(F6/F7/F12);组合键热键不过滤(见已知限制)
- 时间戳转成相对首条的延迟(ms)
- 停止时为"按下未起"的键补发 up,防回放卡键
"""
import time
from pynput import mouse, keyboard as kb

import schema
from hotkey import norm


def _raw_name(key):
    """原始名(不归一):Key 用 name,KeyCode 用 char。回放据此重建。"""
    if isinstance(key, kb.Key):
        return key.name
    if isinstance(key, kb.KeyCode):
        # 注意:KeyCode 没有 .name 属性
        if key.char:
            return key.char
    return None


def _vk(key):
    if isinstance(key, kb.KeyCode) and key.vk:
        return key.vk
    return None


class Recorder:
    def __init__(self, hotkey_combos):
        # hotkey_combos: list[set],当前热键的归一化 combo(用于过滤单键热键)
        self.hotkey_combos = hotkey_combos or []
        self.events = []
        self._base = None
        self._recording = False
        self._ml = None
        self._kl = None
        self._held = set()

    def _t(self):
        now = time.perf_counter()
        if self._base is None:
            self._base = now
        return int((now - self._base) * 1000)

    def _is_hotkey(self, n):
        # 只过滤单键热键成员,避免误伤组合键里的修饰键
        for combo in self.hotkey_combos:
            if len(combo) == 1 and n in combo:
                return True
        return False

    def _on_click(self, x, y, button, pressed):
        if not self._recording:
            return
        self.events.append({
            "type": schema.T_MOUSE,
            "t": self._t(),
            "action": schema.A_DOWN if pressed else schema.A_UP,
            "x": int(x), "y": int(y),
            "button": button.name,
        })

    def _on_scroll(self, x, y, dx, dy):
        if not self._recording:
            return
        self.events.append({
            "type": schema.T_SCROLL,
            "t": self._t(),
            "x": int(x), "y": int(y),
            "dx": int(dx), "dy": int(dy),
        })

    def _key_event(self, key, action):
        n = norm(key)
        if self._is_hotkey(n):
            return
        name = _raw_name(key)
        ev = {"type": schema.T_KEY, "t": self._t(), "action": action}
        if name is not None:
            ev["name"] = name
        vk = _vk(key)
        if vk is not None:
            ev["vk"] = vk
        if action == schema.A_DOWN and isinstance(key, kb.KeyCode) and key.char and len(key.char) == 1:
            ev["char"] = key.char
        self.events.append(ev)
        if name is not None:
            if action == schema.A_DOWN:
                self._held.add(name)
            else:
                self._held.discard(name)

    def _on_press(self, key):
        if self._recording:
            self._key_event(key, schema.A_DOWN)

    def _on_release(self, key):
        if self._recording:
            self._key_event(key, schema.A_UP)

    def start(self):
        self.events = []
        self._base = None
        self._held = set()
        self._recording = True
        self._ml = mouse.Listener(on_click=self._on_click, on_scroll=self._on_scroll)
        self._kl = kb.Listener(on_press=self._on_press, on_release=self._on_release)
        self._ml.daemon = True
        self._kl.daemon = True
        self._ml.start()
        self._kl.start()

    def stop(self):
        self._recording = False
        if self._ml:
            self._ml.stop()
            self._ml = None
        if self._kl:
            self._kl.stop()
            self._kl = None
        # 补发按下未起的键(边界:录到一半停了)
        for name in list(self._held):
            self.events.append({
                "type": schema.T_KEY, "t": self._t(),
                "action": schema.A_UP, "name": name,
            })
        self._held.clear()
        return list(self.events)
