# -*- coding: utf-8 -*-
"""配置读写:热键、默认循环次数、脚本目录。"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    # 热键避开 F10/Alt/Win(系统语义键);格式:单键 "f6" 或组合 "ctrl+shift+x"
    "hotkeys": {
        "record": "f6",
        "play": "f7",
        "abort": "f12",
    },
    "default_loop": 1,
}


def load():
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg.update(data)
            if "hotkeys" in data:
                cfg["hotkeys"] = {**DEFAULT_CONFIG["hotkeys"], **data["hotkeys"]}
        except Exception:
            pass
    return cfg


def save(c):
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)


def ensure_dirs():
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
