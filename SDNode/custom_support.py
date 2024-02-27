import bpy
import blf
from ..utils import Timer, update_screen, _T


class CrystoolsMonitorGPUProp(bpy.types.PropertyGroup):
    gpu: bpy.props.FloatProperty(name="GPU Usage", default=0.0, min=0, max=100, subtype="PERCENTAGE")
    vram: bpy.props.FloatProperty(name="VRAM Usage", default=0.0, min=0, max=100, subtype="PERCENTAGE")


class CrystoolsMonitorProp(bpy.types.PropertyGroup):
    cpu: bpy.props.FloatProperty(name="CPU Usage", default=0.0, min=0, max=100, subtype="PERCENTAGE")
    ram: bpy.props.FloatProperty(name="RAM Usage", default=0.0, min=0, max=100, subtype="PERCENTAGE")
    hdd: bpy.props.FloatProperty(name="HDD Usage", default=0.0, min=0, max=100, subtype="PERCENTAGE")
    gpus: bpy.props.CollectionProperty(type=CrystoolsMonitorGPUProp)


class CrystoolsMonitor:
    def __init__(self) -> None:
        self.enable = False

    def process_msg(self, msg) -> bool:
        mtype = msg.get("type", None)
        if mtype is None:
            return False
        if mtype != "crystools.monitor":
            return False
        self.enable = True
        data_example = {
            "type": "crystools.monitor",
            "data": {
                "cpu_utilization": 4.7,
                "ram_total": 17173536768,
                "ram_used": 7540858880,
                "ram_used_percent": 43.9,
                "hdd_total": 1089070039040,
                "hdd_used": 93980721152,
                "hdd_used_percent": 8.6,
                "device_type": "cuda",
                "gpus": [{"gpu_utilization": 1,
                          "vram_total": 11811160064,
                          "vram_used": 1924640768,
                          "vram_used_percent": 16.295103593306106}
                         ]
            }
        }
        data = msg.get("data", {})

        def f(data):
            p = bpy.context.scene.crystools_monitor_prop
            p.enabled = True
            p.cpu = data.get("cpu_utilization", 0)
            p.ram = data.get("ram_used_percent", 0)
            p.hdd = data.get("hdd_used_percent", 0)
            gpus = data.get("gpus", [])
            if len(p.gpus) < len(gpus):
                for i in range(len(p.gpus), len(gpus)):
                    p.gpus.add()
            for i, g in enumerate(gpus):
                p.gpus[i].gpu = g.get("gpu_utilization", 0)
                p.gpus[i].vram = g.get("vram_used_percent", 0)
            update_screen()
        # self.gpus = data.get("gpus", [])
        Timer.put((f, data))
        return True

    def draw(self, layout: bpy.types.UILayout):
        if not self.enable:
            return
        box = layout.box()
        box.label(text="CrystoolsMonitor")
        col = box.column(align=True)
        p = bpy.context.scene.crystools_monitor_prop
        col.prop(p, "cpu")
        col.prop(p, "ram")
        col.prop(p, "hdd")
        for g in p.gpus:
            col.prop(g, "gpu")
            col.prop(g, "vram")
        return
        if self.cpu is None:
            return
        box = layout.box()
        box.label(text="CrystoolsMonitor")
        row = box.row()
        row.alignment = "CENTER"
        t = _T("CPU Usage: ")
        row.label(text=self.make_progress_bar(self.cpu / 100, t))

        row = box.row()
        row.alignment = "CENTER"
        t = _T("RAM Usage: ")
        row.label(text=self.make_progress_bar(self.ram / 100, t))

        row = box.row()
        row.alignment = "CENTER"
        t = _T("HDD Usage: ")
        row.label(text=self.make_progress_bar(self.hdd / 100, t))

        for gpu in self.gpus:
            row = box.row()
            row.alignment = "CENTER"
            t = _T("GPU Usage: ")
            row.label(text=self.make_progress_bar(gpu.get("gpu_utilization", 0) / 100, t))
            row = box.row()

            row.alignment = "CENTER"
            t = _T("VRAM Usage:")
            row.label(text=self.make_progress_bar(gpu.get("vram_used_percent", 0) / 100, t))
        row = box.row()
        # row.label(text="| A B  C  D   E|")

    def make_progress_bar(self, per, head="", tail="", bt1="█", bt2="░"):
        "A"  # 15
        " "  # 6
        "█"  # 22
        content = f"{head}{per*100:　>4.1f}% "
        # 面板宽度(dim)
        pwidth = bpy.context.region.width - 21
        bt1w = blf.dimensions(0, bt1)[0]
        bt2w = blf.dimensions(0, bt2)[0]

        lnum = int(pwidth)
        # lnum = int(lnum * 0.3)
        lnum = int((bpy.context.region.width - blf.dimensions(0, content)[0]) / bt1w) - 10
        v = int(per * lnum)
        content = content + bt1 * v + bt2 * (lnum - v)
        return content[:134]


crystools_monitor = CrystoolsMonitor()


def custom_support_reg():
    bpy.utils.register_class(CrystoolsMonitorGPUProp)
    bpy.utils.register_class(CrystoolsMonitorProp)
    bpy.types.Scene.crystools_monitor_prop = bpy.props.PointerProperty(type=CrystoolsMonitorProp)


def custom_support_unreg():
    del bpy.types.Scene.crystools_monitor_prop
    bpy.utils.unregister_class(CrystoolsMonitorProp)
    bpy.utils.unregister_class(CrystoolsMonitorGPUProp)
