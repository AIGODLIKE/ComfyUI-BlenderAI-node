import typing
import bpy
import os
from pathlib import Path

from .utils import Icon, _T
from .translations import ctxt


class AddonPreference(bpy.types.AddonPreferences):
    bl_idname = __package__
    bl_translation_context = ctxt

    popup_scale: bpy.props.IntProperty(default=5, min=1, max=100, name="预览图尺寸")
    enable_hq_preview: bpy.props.BoolProperty(default=True, name="启用高清预览图")

    model_path: bpy.props.StringProperty(subtype="DIR_PATH", name="ComfyUI路径",
                                         default=str(Path(__file__).parent / "ComfyUI"))
    page: bpy.props.EnumProperty(items=[("通用", "通用", "", "COLLAPSEMENU", 0),
                                        ("常用路径", "常用路径", "", "URL", 1),
                                        ("友情链接", "友情链接", "", "URL", 2),
                                        ], default=0)
    cpu_only: bpy.props.BoolProperty(default=False)  # --cpu

    mem_level: bpy.props.EnumProperty(name="显存模式",
                                      items=[("--gpu-only", "极高显存", "所有数据存储到显存", 0),
                                             ("--highvram", "高显存", "模型常驻显存, 减少加载时间", 1),
                                             ("--normalvram", "中显存", "自动启用 低显存 模式时强制使用normal vram", 2),
                                             ("--lowvram", "低显存", "拆分UNet来降低显存开销", 3),
                                             ("--novram", "超低显存", "如果低显存依然不够", 4),
                                             ("--cpu", "仅CPU", "只使用CPU", 5),
                                             ],
                                      default="--lowvram")
    with_webui_model: bpy.props.StringProperty(default="", name="With WEBUI Model", description="webui位置", subtype="DIR_PATH")
    with_comfyui_model: bpy.props.StringProperty(default="", name="With ComfyUI Model", description="ComfyUI位置", subtype="DIR_PATH")
    install_deps: bpy.props.BoolProperty(default=False, name="启动服务时检查依赖", description="启动服务时进行ComfyUI插件(部分)依赖安装检查")
    force_log: bpy.props.BoolProperty(default=False, name="强制日志", description="强制输出日志, 一般不需要开启")
    def get_cuda_list():
        """
        借助nvidia-smi获取CUDA版本列表
        """
        import subprocess
        import re
        try:
            res = subprocess.check_output("nvidia-smi -L", shell=True).decode("utf-8")
            # GPU 0: NVIDIA GeForce GTX 1060 5GB (UUID: xxxx)
            items = []
            for line in res.split("\n"):
                m = re.search(r"GPU (\d+): NVIDIA GeForce (.*) \(UUID: GPU-.*\)", line)
                if not line.startswith("GPU") or not m:
                    continue
                items.append((m.group(1), m.group(2), "", len(items),))
            return items
        except:
            return []
        
    cuda: bpy.props.EnumProperty(name="cuda", items=get_cuda_list())
    def ip_check(self, context):
        """检查IP地址是否合法"""
        ip = self.ip.split(".")
        if len(ip) < 4:
            ip.extend(["0"] * (4 - len(ip)))
        ip = ip[:4]
        for i in range(4):
            if not ip[i].isdigit():
                ip[i] = "0"
            v = int(ip[i])
            ip[i] = str(min(255, max(0, v)))
        self["ip"] = ".".join(ip)

    ip: bpy.props.StringProperty(default="127.0.0.1", name="IP", description="服务IP地址",
                                 update=ip_check)
    port: bpy.props.IntProperty(default=5000, min=1000, max=65535, name="端口", description="服务端口号")

    def update_open_dir1(self, context):
        if self.open_dir1:
            self.open_dir1 = False
            os.startfile(Path(self.model_path) / "models/checkpoints")

    open_dir1: bpy.props.BoolProperty(default=False, name="打开CKPT模型文件夹", update=update_open_dir1)

    def update_open_dir2(self, context):
        if self.open_dir2:
            self.open_dir2 = False
            os.startfile(Path(self.model_path) / "models/loras")
    open_dir2: bpy.props.BoolProperty(default=False, name="打开LoRA模型文件夹", update=update_open_dir2)

    def update_open_dir3(self, context):
        if self.open_dir3:
            self.open_dir3 = False
            os.startfile(self.model_path)

    open_dir3: bpy.props.BoolProperty(default=False, name="打开ComfyUI文件夹", update=update_open_dir3)

    def update_open_dir4(self, context):
        if self.open_dir4:
            self.open_dir4 = False
            os.startfile(Path(self.model_path) / "SDNodeTemp")

    open_dir4: bpy.props.BoolProperty(default=False,
                                      name="打开输出缓存文件夹",
                                      update=update_open_dir4)

    def draw_general(self, layout: bpy.types.UILayout):
        layout.prop(self, "model_path", text_ctxt=ctxt)
        layout.prop(self, "mem_level", text_ctxt=ctxt)
        row = layout.row(align=True)
        row.prop(self, "popup_scale", text_ctxt=ctxt)
        row.prop(self, "enable_hq_preview", text="", icon="IMAGE_BACKGROUND", text_ctxt=ctxt)
        layout.prop(self, "with_webui_model")
        layout.prop(self, "with_comfyui_model")
        row = layout.row(align=True)
        row.prop(self, "ip")
        row.prop(self, "port")
        layout.prop(self, "cuda")
        row = layout.row(align=True)
        row.prop(self, "install_deps", toggle=True, text_ctxt=ctxt)
        row.prop(self, "force_log", toggle=True, text_ctxt=ctxt)

    def draw_website(self, layout: bpy.types.UILayout):

        layout.label(text="-AIGODLIKE冒险社区", text_ctxt=ctxt)
        row = layout.row()
        row.operator("wm.url_open", text="AIGODLIKE开源社区-主站", icon="URL", text_ctxt=ctxt).url = "https://www.aigodlike.com"
        row.label(text=" ", text_ctxt=ctxt)

        layout.label(text="-在AI世界探索的好朋友们(首字母排序)", text_ctxt=ctxt)
        col = layout.column(align=True)
        col.scale_y = 1.1
        row = col.row(align=True)
        icon_id = Icon().get_icon_id("up")
        row.operator("wm.url_open", text="独立研究员-星空", icon_value=icon_id, text_ctxt=ctxt).url = "https://space.bilibili.com/250989068"
        row.operator("wm.url_open", text="秋葉aaaki", icon_value=icon_id, text_ctxt=ctxt).url = "https://space.bilibili.com/12566101"
        row = col.row(align=True)
        row.operator("wm.url_open", text="小李xiaolxl", icon_value=icon_id, text_ctxt=ctxt).url = "https://space.bilibili.com/34590220"

        row.operator("wm.url_open", text="元素法典制作委员会", icon_value=icon_id, text_ctxt=ctxt).url = "https://space.bilibili.com/1981251194"
        row.operator("wm.url_open", text="只剩一瓶辣椒酱", icon_value=icon_id, text_ctxt=ctxt).url = "https://space.bilibili.com/35723238"

        layout.label(text="“感谢，这些在AI领域探索并分享经验的冒险者，快去关注啦～”", text_ctxt=ctxt)

    def draw_path(self, layout: bpy.types.UILayout):
        row = layout.row()
        row.prop(self, "open_dir1", toggle=True, text_ctxt=ctxt)
        row.prop(self, "open_dir2", toggle=True, text_ctxt=ctxt)
        row.prop(self, "open_dir3", toggle=True, text_ctxt=ctxt)
        row.prop(self, "open_dir4", toggle=True, text_ctxt=ctxt)

    def draw(self, context):
        self.layout.row(align=True).prop(self, "page", expand=True, text_ctxt=ctxt)
        box = self.layout.box()
        if self.page == "通用":
            self.draw_general(box)
        elif self.page == "常用路径":
            self.draw_path(box)
        elif self.page == "友情链接":
            self.draw_website(box)


def get_pref():
    import bpy
    return bpy.context.preferences.addons[__package__].preferences
