# -*- coding: utf-8 -*-
"""tkinter GUI(主线程)。

线程模型:GUI 主线程;录制/回放/热键监听都在工作线程。
跨线程回 GUI 一律走 queue,root.after 轮询处理,**绝不在工作线程改控件**。
"""
import os
import queue
import datetime
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import config as cfg
import schema
from recorder import Recorder
from player import Player
from hotkey import HotkeyManager

try:
    import pyautogui
    pyautogui.PAUSE = 0       # 防默认 0.1s 污染回放间隔
    pyautogui.FAILSAFE = False  # 关掉"鼠标到角落急停",我们用 F12
except Exception:
    pyautogui = None


class App:
    def __init__(self, root):
        self.root = root
        self.config = cfg.load()
        cfg.ensure_dirs()
        self.q = queue.Queue()
        self.recorder = None
        self.player = None
        self.recording = False
        self.playing = False

        self.hotkey_mgr = HotkeyManager(self.config, {
            "record": lambda: self.q.put(("hk", "toggle_record")),
            "play": lambda: self.q.put(("hk", "play")),
            "abort": lambda: self.q.put(("hk", "abort")),
        })
        self.hotkey_mgr.start()

        self._build_ui()
        self._refresh_scripts()
        self._poll()

    # ---------- UI ----------
    def _build_ui(self):
        hk = self.config["hotkeys"]
        self.hk_label = f"录制 {hk.get('record','?')} / 回放 {hk.get('play','?')} / 急停 {hk.get('abort','?')}"

        top = ttk.Frame(self.root, padding=8)
        top.grid(row=0, column=0, sticky="ew")
        self.status_var = tk.StringVar(value=f"IDLE  ({self.hk_label})")
        ttk.Label(top, textvariable=self.status_var,
                  font=("Microsoft YaHei", 11, "bold")).pack(anchor="w")

        btns = ttk.Frame(self.root, padding=8)
        btns.grid(row=1, column=0, sticky="ew")
        ttk.Button(btns, text="● 录制", command=lambda: self.q.put(("cmd", "record"))).pack(side="left", padx=4)
        ttk.Button(btns, text="■ 停止录制", command=lambda: self.q.put(("cmd", "stop_record"))).pack(side="left", padx=4)
        ttk.Button(btns, text="▶ 回放", command=lambda: self.q.put(("cmd", "play"))).pack(side="left", padx=4)
        ttk.Button(btns, text="⏸ 急停", command=lambda: self.q.put(("cmd", "abort"))).pack(side="left", padx=4)

        mid = ttk.Frame(self.root, padding=8)
        mid.grid(row=2, column=0, sticky="nsew")
        self.root.rowconfigure(2, weight=1)
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(0, weight=1)

        left = ttk.Frame(mid)
        left.grid(row=0, column=0, sticky="nsew")
        ttk.Label(left, text="脚本列表:").pack(anchor="w")
        self.script_list = tk.Listbox(left, height=12)
        self.script_list.pack(fill="both", expand=True)
        sf = ttk.Frame(left)
        sf.pack(fill="x", pady=(4, 0))
        ttk.Button(sf, text="刷新", command=self._refresh_scripts).pack(side="left", padx=2)
        ttk.Button(sf, text="删除", command=self._delete_script).pack(side="left", padx=2)

        right = ttk.Frame(mid)
        right.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        ttk.Label(right, text="循环次数:").pack(anchor="w")
        self.loop_var = tk.IntVar(value=self.config.get("default_loop", 1))
        ttk.Spinbox(right, from_=1, to=100000, textvariable=self.loop_var, width=8).pack(anchor="w")

        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=8)
        ttk.Label(right, text="热键(小写,+分隔)").pack(anchor="w")
        self.hk_vars = {}
        for role, label in (("record", "录制"), ("play", "回放"), ("abort", "急停")):
            f = ttk.Frame(right)
            f.pack(fill="x", pady=2)
            ttk.Label(f, text=label, width=6).pack(side="left")
            v = tk.StringVar(value=self.config["hotkeys"].get(role, ""))
            self.hk_vars[role] = v
            ttk.Entry(f, textvariable=v, width=16).pack(side="left", padx=4)
        ttk.Button(right, text="保存热键", command=self._save_hotkeys).pack(anchor="w", pady=4)

        tip = ttk.Frame(self.root, padding=8)
        tip.grid(row=3, column=0, sticky="ew")
        ttk.Label(tip, text="提示:中文输入请改用 复制+Ctrl+V 录制;坐标基于当前屏幕,窗口别挪动。",
                  foreground="#666").pack(anchor="w")

    # ---------- 脚本列表 ----------
    def _refresh_scripts(self):
        self.script_list.delete(0, tk.END)
        if os.path.isdir(cfg.SCRIPTS_DIR):
            for fn in sorted(os.listdir(cfg.SCRIPTS_DIR)):
                if fn.lower().endswith(".json"):
                    self.script_list.insert(tk.END, fn)

    def _delete_script(self):
        sel = self.script_list.curselection()
        if not sel:
            return
        fn = self.script_list.get(sel[0])
        if messagebox.askyesno("删除", f"删除脚本 {fn}?"):
            try:
                os.remove(os.path.join(cfg.SCRIPTS_DIR, fn))
            except Exception:
                pass
            self._refresh_scripts()

    def _save_hotkeys(self):
        for role, v in self.hk_vars.items():
            s = v.get().strip().lower()
            if s:
                self.config["hotkeys"][role] = s
        self.config["default_loop"] = int(self.loop_var.get())
        cfg.save(self.config)
        self.hotkey_mgr.update_config(self.config)
        hk = self.config["hotkeys"]
        self.hk_label = f"录制 {hk.get('record','?')} / 回放 {hk.get('play','?')} / 急停 {hk.get('abort','?')}"
        messagebox.showinfo("热键", "热键已保存并立即生效。")

    # ---------- 录制/回放 ----------
    def _start_record(self):
        if self.recording or self.playing:
            return
        combos = list(self.hotkey_mgr.combos.values())
        self.recorder = Recorder(combos)
        self.recorder.start()
        self.recording = True
        self.status_var.set("● RECORDING...  (再按录制键停止并保存)")

    def _stop_record(self):
        if not self.recording:
            return
        events = self.recorder.stop()
        self.recorder = None
        self.recording = False
        self.status_var.set(f"IDLE  ({self.hk_label})")
        if not events:
            messagebox.showinfo("录制", "没录到任何事件。")
            return
        name = simpledialog.askstring("保存脚本", "脚本名(不含扩展名):")
        if not name:
            return
        name = "".join(c for c in name if c not in '\\/:*?"<>|').strip()
        if not name:
            return
        if pyautogui:
            sz = pyautogui.size()
            w, h = sz.width, sz.height
        else:
            w, h = 1920, 1080
        doc = schema.make_header(w, h, created=datetime.datetime.now().isoformat(timespec="seconds"))
        doc["events"] = events
        path = os.path.join(cfg.SCRIPTS_DIR, name + ".json")
        schema.save_script(path, doc)
        self._refresh_scripts()
        messagebox.showinfo("录制", f"已保存 {len(events)} 个事件 -> {name}.json")

    def _start_play(self):
        if self.recording or self.playing:
            return
        sel = self.script_list.curselection()
        if not sel:
            messagebox.showwarning("回放", "请先在列表选一个脚本。")
            return
        fn = self.script_list.get(sel[0])
        try:
            doc = schema.load_script(os.path.join(cfg.SCRIPTS_DIR, fn))
        except Exception as e:
            messagebox.showerror("回放", f"读取脚本失败: {e}")
            return
        loop = int(self.loop_var.get())
        self.playing = True
        self.status_var.set("▶ PLAYING...  (急停键停止)")
        self.player = Player(
            doc["events"], loop,
            on_progress=lambda c, t: self.q.put(("prog", c, t)),
            on_done=lambda ok: self.q.put(("done", ok)),
        )
        self.player.start()

    def _abort(self):
        if self.player:
            self.player.stop()

    # ---------- 跨线程消息 ----------
    def _poll(self):
        try:
            while True:
                self._handle(self.q.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _handle(self, msg):
        kind = msg[0]
        if kind in ("hk", "cmd"):
            self._dispatch(msg[1])
        elif kind == "prog":
            self.status_var.set(f"▶ PLAYING  {msg[1]}/{msg[2]}  (急停键停止)")
        elif kind == "done":
            self.playing = False
            self.player = None
            self.status_var.set(
                f"IDLE  ({self.hk_label})" if msg[1] else f"已急停  IDLE  ({self.hk_label})")

    def _dispatch(self, action):
        if action == "toggle_record":
            self._stop_record() if self.recording else self._start_record()
        elif action == "record":
            self._start_record()
        elif action == "stop_record":
            self._stop_record()
        elif action == "play":
            self._start_play()
        elif action == "abort":
            self._abort()

    def on_close(self):
        try:
            if self.player:
                self.player.stop()
            if self.recorder:
                self.recorder.stop()
            self.hotkey_mgr.stop()
        except Exception:
            pass
        self.root.destroy()
