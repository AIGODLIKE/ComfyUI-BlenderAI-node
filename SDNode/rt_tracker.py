import bpy
from bpy.types import Scene, Object, Collection, Mesh
from queue import Queue
from functools import lru_cache
from time import time
from ..preference import get_pref
from .utils import get_default_tree


class TrackerStatus:
    args = {}

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_init", False):
            return
        self.status = Queue()
        self.last_time = 0
        self._init = True

    def update_deps(self, depsgraph):
        check_list = ["MESH", "OBJECT", "COLLECTION"]
        for i in check_list:
            if not depsgraph.id_type_updated(i):
                continue
            self.push_status(i)
            return
        for update in depsgraph.updates:
            t = type(update.id)
            if t == Scene:
                continue
            elif t in {Object, Mesh, Collection}:
                self.push_status(t.__name__)
                break
            else:
                print(f"{t.__name__} {update.id.name} changed")

    def push_status(self, name):
        while not self.status.empty():
            self.status.get()
        self.status.put(name)

    def get_status(self):
        name = None
        while not self.status.empty():
            name = self.status.get()
        return name

    def exec(self):
        ct = time()
        if ct - self.last_time < get_pref().rt_track_freq:
            return
        tstatus = self.get_status()
        if not tstatus:
            return
        from .manager import TaskManager
        qr_num = len(TaskManager.query_server_task().get('queue_running', []))
        qp_num = TaskManager.get_task_num()
        if qp_num or qr_num:
            self.push_status(tstatus)
        else:
            tree = self.args.get("tree", None)
            with bpy.context.temp_override(sdn_tree=tree):
                bpy.ops.sdn.ops(action="Submit")
            self.last_time = ct


@lru_cache
def get_tracker_status() -> TrackerStatus:
    return TrackerStatus()


@bpy.app.handlers.persistent
def handler_pre(scene):
    depsgraph = bpy.context.view_layer.depsgraph
    status = get_tracker_status()
    status.update_deps(depsgraph)


def tracker_timer():
    status = get_tracker_status()
    status.exec()
    return 0.01


def is_looped():
    return bpy.app.timers.is_registered(tracker_timer)


class Tracker_Loop(bpy.types.Operator):
    bl_idname = "sdn.rt_tracker_loop"
    bl_label = "Tracker Loop"
    bl_description = "Tracker Loop"
    action: bpy.props.EnumProperty(items=[("START", "Start", ""),
                                          ("STOP", "Stop", ""),]
                                   )

    def execute(self, context):
        status = get_tracker_status()
        if self.action == "START":
            if is_looped():
                return {'FINISHED'}
            status.args["tree"] = get_default_tree()
            bpy.app.timers.register(tracker_timer)
        else:
            if not is_looped():
                return {'FINISHED'}
            status.args.clear()
            bpy.app.timers.unregister(tracker_timer)
        return {'FINISHED'}


def reg_tracker():
    h = bpy.app.handlers
    h.depsgraph_update_pre.append(handler_pre)
    bpy.utils.register_class(Tracker_Loop)


def unreg_tracker():
    h = bpy.app.handlers
    h.depsgraph_update_pre.remove(handler_pre)
    bpy.utils.unregister_class(Tracker_Loop)
