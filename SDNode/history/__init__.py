import json
import bpy
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from ...utils import read_json


class History:
    path = Path(__file__).parent.joinpath("history.json")
    num = 20
    is_dirty = True
    cache_histories = []

    @staticmethod
    def put_history(history):
        try:
            if not history:
                return
            history = {"history": history, "name": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            if History.path.exists():
                histories = read_json(History.path)
            else:
                histories = []
            histories.append(history)
            # 限制历史记录数量
            histories = histories[-History.num:]
            History.path.write_text(json.dumps(histories, indent=4, ensure_ascii=False), encoding="utf8")
            History.is_dirty = True
        finally:
            ...

    @staticmethod
    def get_history():
        if History.is_dirty and History.path.exists():
            History.cache_histories = read_json(History.path)
            History.cache_histories.reverse()
            History.is_dirty = False
        return History.cache_histories

    @staticmethod
    def get_history_by_name(name):
        for i in History.get_history():
            if i["name"] != name:
                continue
            return deepcopy(i["history"])
        return None

    @staticmethod
    def update_timer():
        if not bpy.context.scene:
            return 1
        try:
            bpy.context.scene.sdn_history_item.clear()
            for i in History.get_history():
                item = bpy.context.scene.sdn_history_item.add()
                item.name = i["name"]
        except Exception as e:
            print("Update History Error: ", e)
        return 1

    @staticmethod
    def register_timer():
        bpy.app.timers.register(History.update_timer, persistent=True)

    @staticmethod
    def unregister_timer():
        bpy.app.timers.unregister(History.update_timer)
