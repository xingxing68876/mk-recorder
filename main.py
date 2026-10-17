# -*- coding: utf-8 -*-
"""mk_recorder 入口。

pythonw 无 stdout/stderr(无控制台)-> 重定向到 logs/app.log,
防止任何 print/reconfigure 在 pythonw 下崩溃。
"""
import sys
import os

_BASE = os.path.dirname(os.path.abspath(__file__))

if sys.stdout is None:
    _logdir = os.path.join(_BASE, "logs")
    os.makedirs(_logdir, exist_ok=True)
    _log = open(os.path.join(_logdir, "app.log"), "a", encoding="utf-8")
    sys.stdout = _log
    sys.stderr = _log
else:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import tkinter as tk
from gui import App


def main():
    root = tk.Tk()
    root.title("鼠标键盘录制回放器  mk_recorder")
    root.geometry("600x580")
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
