import json
import bpy
from copy import deepcopy
from datetime import datetime
from pathlib import Path


class History:
    path = Path(__file__).parent.joinpath("history.json")
    num = 10
    is_dirty = True
    cache_histories = []

    def put_history(history):
        try:
            if not history:
                return
            history = {"history": history, "name": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            if History.path.exists():
                histories = json.loads(History.path.read_text())
            else:
                histories = []
            histories.append(history)
            # 限制历史记录数量
            histories = histories[-History.num:]
            History.path.write_text(json.dumps(histories, indent=4, ensure_ascii=False))
            History.is_dirty = True
        finally:
            ...

    def get_history():
        if History.is_dirty and History.path.exists():
            History.cache_histories = json.loads(History.path.read_text())
            History.cache_histories.reverse()
            History.is_dirty = False
        return History.cache_histories

    def get_history_by_name(name):
        for i in History.get_history():
            if i["name"] != name:
                continue
            return deepcopy(i["history"])
        return None

    def update_timer():
        try:
            bpy.context.scene.sdn_history_item.clear()
            for i in History.get_history():
                item = bpy.context.scene.sdn_history_item.add()
                item.name = i["name"]
        except Exception as e:
            print("Update History Error: ", e)
        return 1

    def register_timer():
        bpy.app.timers.register(History.update_timer, persistent=True)
