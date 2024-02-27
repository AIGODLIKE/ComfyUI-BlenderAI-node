import bpy
import blf
from ..utils import Timer, update_screen


class CrystoolsMonitor:
    def __init__(self) -> None:
        self.cpu = None
        self.ram = None
        self.hdd = None
        self.gpus = []

    def process_msg(self, msg) -> bool:
        mtype = msg.get("type", None)
        if mtype is None:
            return False
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
        self.cpu = data.get("cpu_utilization", None)
        self.ram = data.get("ram_used_percent", None)
        self.hdd = data.get("hdd_used_percent", None)
        self.gpus = data.get("gpus", [])
        Timer.put(update_screen)
        return True

    def draw(self, layout: bpy.types.UILayout):
        if self.cpu is None:
            return
        box = layout.box()
        box.label(text="CrystoolsMonitor")
        row = box.row()
        row.alignment = "CENTER"
        row.label(text="CPU Usage: " + self.make_progress_bar(self.cpu / 100, len("CPU Usage: ")))

        row = box.row()
        row.alignment = "CENTER"
        row.label(text="RAM Usage: " + self.make_progress_bar(self.ram / 100, len("RAM Usage: ")))

        row = box.row()
        row.alignment = "CENTER"
        row.label(text="HDD Usage: " + self.make_progress_bar(self.hdd / 100, len("HDD Usage: ")))

        for gpu in self.gpus:
            row = box.row()
            row.alignment = "CENTER"
            row.label(text="GPU Usage: " + self.make_progress_bar(gpu.get("gpu_utilization", 0) / 100, len("GPU Usage: ")))
            row = box.row()
            row.alignment = "CENTER"
            row.label(text="VRAM Usage: " + self.make_progress_bar(gpu.get("vram_used_percent", 0) / 100, len("VRAM Usage: ")))

    def make_progress_bar(self, per, ocp=0, bt1="█", bt2="░"):
        content = f"{per*100:3.0f}% "
        lnum = int(bpy.context.region.width / bpy.context.preferences.view.ui_scale / 7 - 21)
        lnum = int(lnum * 0.3)
        lnum = int((bpy.context.region.width - blf.dimensions(0, content + bt1 * ocp)[0]) / blf.dimensions(0, bt1)[0]) - 10
        v = int(per * lnum)
        content = content + bt1 * v + bt2 * (lnum - v)
        return content[:134]


crystools_monitor = CrystoolsMonitor()
