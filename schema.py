# -*- coding: utf-8 -*-
"""事件 schema 与脚本 JSON 读写(共享契约层)。

事件统一存成 events 数组,每条带 t = 相对首条的延迟(ms)。
事件类型:
  mouse       {action: down|up, x, y, button: left|right|middle}
  key         {action: down|up, name, char?, vk?}
  scroll      {x, y, dx, dy}
  checkpoint  二期预留(识别+分支),一期不产生
"""
import json

SCHEMA_VERSION = 1

T_MOUSE = "mouse"
T_KEY = "key"
T_SCROLL = "scroll"
T_CHECKPOINT = "checkpoint"  # 二期预留

A_DOWN = "down"
A_UP = "up"


def make_header(screen_w, screen_h, created=None):
    return {
        "version": SCHEMA_VERSION,
        "created": created,
        "screen": {"w": int(screen_w), "h": int(screen_h)},
        "events": [],
    }


def validate(doc):
    """校验脚本结构,返回 (ok, msg)。"""
    if not isinstance(doc, dict):
        return False, "脚本根不是对象"
    if "events" not in doc or not isinstance(doc["events"], list):
        return False, "缺少 events 数组"
    for i, ev in enumerate(doc["events"]):
        if not isinstance(ev, dict) or "type" not in ev or "t" not in ev:
            return False, f"第 {i} 个事件格式错: {ev!r}"
    return True, "ok"


def save_script(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def load_script(path):
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    ok, msg = validate(doc)
    if not ok:
        raise ValueError(f"脚本校验失败({path}): {msg}")
    return doc
