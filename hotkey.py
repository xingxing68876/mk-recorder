# -*- coding: utf-8 -*-
"""全局热键:常驻 suppress=False listener + 修饰键状态机。

关键:suppress 是 listener 级开关(开启会吞掉所有键),故不用,
改用回调里匹配 combo。默认热键避开 F10/Alt/Win(系统语义键)。
"""
from pynput import keyboard as kb

# 左右修饰键归一化(便于组合键匹配:ctrl_l/ctrl_r -> ctrl)
MOD_NORMALIZE = {
    "ctrl_l": "ctrl", "ctrl_r": "ctrl",
    "shift_l": "shift", "shift_r": "shift",
    "alt_l": "alt", "alt_r": "alt", "alt_gr": "alt",
    "cmd_l": "cmd", "cmd_r": "cmd",
}

MODIFIER_NAMES = {"ctrl", "alt", "shift", "cmd"}


def norm(key):
    """把 pynput key 规范化成小写 name(修饰键左右归一)。"""
    if isinstance(key, kb.Key):
        n = key.name.lower()
    elif isinstance(key, kb.KeyCode):
        # 注意:KeyCode 没有 .name 属性(只有 Key 枚举成员才有)
        if key.char:
            n = key.char.lower()
        elif key.vk:
            n = f"vk{key.vk}"
        else:
            n = "unknown"
    else:
        n = str(key).lower().strip("'")
    return MOD_NORMALIZE.get(n, n)


def parse_combo(s):
    """'ctrl+shift+x' -> {'ctrl','shift','x'}。"""
    return {p.strip().lower() for p in s.split("+") if p.strip()}


class HotkeyManager:
    def __init__(self, config, callbacks):
        # callbacks: {"record": fn, "play": fn, "abort": fn}
        self.config = config
        self.callbacks = callbacks
        self.combos = {}
        self._rebuild()
        self.held = set()
        self.listener = None

    def _rebuild(self):
        self.combos = {}
        for role, s in self.config.get("hotkeys", {}).items():
            self.combos[role] = parse_combo(s)

    def update_config(self, config):
        self.config = config
        self._rebuild()

    def _check(self):
        combo = set(self.held)
        for role, target in self.combos.items():
            if combo == target:
                cb = self.callbacks.get(role)
                if cb:
                    try:
                        cb()
                    except Exception:
                        pass
                # 触发后清掉非修饰键,避免按住不放连发
                self.held = {k for k in self.held if k in MODIFIER_NAMES}
                return

    def _on_press(self, key):
        self.held.add(norm(key))
        self._check()

    def _on_release(self, key):
        self.held.discard(norm(key))

    def start(self):
        self.listener = kb.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=False,
        )
        self.listener.daemon = True
        self.listener.start()

    def stop(self):
        if self.listener:
            self.listener.stop()
            self.listener = None
