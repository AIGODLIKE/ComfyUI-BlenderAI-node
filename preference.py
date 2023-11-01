import typing
import bpy
import os
from pathlib import Path

from .utils import Icon, _T
from .translations import ctxt


class AddonPreference(bpy.types.AddonPreferences):
    bl_idname = __package__
    bl_translation_context = ctxt

    popup_scale: bpy.props.IntProperty(default=5, min=1, max=100, name="Preview Image Size")
    enable_hq_preview: bpy.props.BoolProperty(default=True, name="Enable High Quality Preview Image")
    server_type: bpy.props.EnumProperty(items=[("Local", "LocalServer", "", "LOCKVIEW_ON", 0),
                                               ("Remote", "RemoteServer", "", "WORLD_DATA", 1)
                                               ],
                                        name="Server Type")  # --server_type
    model_path: bpy.props.StringProperty(subtype="DIR_PATH", name="ComfyUI Path",
                                         default=str(Path(__file__).parent / "ComfyUI"))
    python_path: bpy.props.StringProperty(subtype="FILE_PATH",
                                          name="Python Path",
                                          description="Select python dir or python.exe")
    page: bpy.props.EnumProperty(items=[("通用", "General", "", "COLLAPSEMENU", 0),
                                        ("常用路径", "Common Path", "", "URL", 1),
                                        ("友情链接", "Friendly Links", "", "URL", 2),
                                        ], default=0)
    cpu_only: bpy.props.BoolProperty(default=False)  # --cpu

    mem_level: bpy.props.EnumProperty(name="VRam Mode",
                                      items=[("--gpu-only", "Gpu Only", "Store and run everything (text encoders/CLIP models, etc... on the GPU).", 0),
                                             ("--highvram", "High VRam", "By default models will be unloaded to CPU memory after being used. This option keeps them in GPU memory.", 1),
                                             ("--normalvram", "Normal VRam", "Used to force normal vram use if lowvram gets automatically enabled.", 2),
                                             ("--lowvram", "Low VRam", "Split the unet in parts to use less vram.", 3),
                                             ("--novram", "No VRam", "When lowvram isn't enough.", 4),
                                             ("--cpu", "Cpu Only", "To use the CPU for everything (slow).", 5),
                                             ],
                                      default="--lowvram")
    with_webui_model: bpy.props.StringProperty(default="", name="With WEBUI Model", subtype="DIR_PATH")
    with_comfyui_model: bpy.props.StringProperty(default="", name="With ComfyUI Model", subtype="DIR_PATH")
    auto_launch: bpy.props.BoolProperty(default=False, name="Auto Launch Browser")
    install_deps: bpy.props.BoolProperty(default=False, name="Check Depencies Before Server Launch", description="Check ComfyUI(some) Depencies Before Server Launch")
    force_log: bpy.props.BoolProperty(default=False, name="Force Log", description="Force Log, Generally Not Needed")
    fixed_preview_image_size: bpy.props.BoolProperty(default=False, name="Fixed Preview Image Size")
    preview_image_size: bpy.props.IntProperty(default=256, min=64, max=8192, name="Preview Image Size")
    stencil_offset_size_xy: bpy.props.IntVectorProperty(default=(0, 18), size=2, min=-100, max=100, name="Stencil Offset Size")
    drag_link_result_count_col: bpy.props.IntProperty(default=4, min=1, max=10, name="Drag Link Result Count Column")
    drag_link_result_count_row: bpy.props.IntProperty(default=10, min=1, max=100, name="Drag Link Result Count Row")
    count_page_total: bpy.props.IntProperty(default=0, min=0, name="Drag Link Result Page Total")

    count_page_current: bpy.props.IntProperty(default=0, min=0, name="Drag Link Result Page Current")

    def update_count_page_next(self, context):
        if self.count_page_next:
            self.count_page_next = False
            self.count_page_current += 1
            self.count_page_current = min(self.count_page_current, self.count_page_total)
            bpy.ops.sdn.mouse_pos_rec("INVOKE_DEFAULT", action="ORI")
            from .Linker.linker import P
            bpy.context.window.cursor_warp(P.x, P.y)
            bpy.ops.comfy.swapper("INVOKE_DEFAULT", action="DRAW")
            bpy.context.window.cursor_warp(P.ori_x, P.ori_y)

    count_page_next: bpy.props.BoolProperty(default=False,
                                            name="Drag Link Result Page Next",
                                            update=update_count_page_next)

    def update_count_page_prev(self, context):
        if self.count_page_prev:
            self.count_page_prev = False
            self.count_page_current -= 1
            bpy.ops.sdn.mouse_pos_rec("INVOKE_DEFAULT", action="ORI")
            from .Linker.linker import P
            bpy.context.window.cursor_warp(P.x, P.y)
            bpy.ops.comfy.swapper("INVOKE_DEFAULT", action="DRAW")
            bpy.context.window.cursor_warp(P.ori_x, P.ori_y)
    count_page_prev: bpy.props.BoolProperty(default=False,
                                            name="Drag Link Result Page Prev",
                                            update=update_count_page_prev)

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
        except BaseException:
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

    ip: bpy.props.StringProperty(default="127.0.0.1", name="IP", description="Service IP Address",
                                 update=ip_check)
    port: bpy.props.IntProperty(default=8189, min=1000, max=65535, name="Port", description="Service Port")

    def update_open_dir1(self, context):
        if self.open_dir1:
            self.open_dir1 = False
            os.startfile(Path(self.model_path) / "models/checkpoints")

    open_dir1: bpy.props.BoolProperty(default=False, name="Open CKPT Folder", update=update_open_dir1)

    def update_open_dir2(self, context):
        if self.open_dir2:
            self.open_dir2 = False
            os.startfile(Path(self.model_path) / "models/loras")
    open_dir2: bpy.props.BoolProperty(default=False, name="Open LoRA Folder", update=update_open_dir2)

    def update_open_dir3(self, context):
        if self.open_dir3:
            self.open_dir3 = False
            os.startfile(self.model_path)

    open_dir3: bpy.props.BoolProperty(default=False, name="Open ComfyUI Folder", update=update_open_dir3)

    def update_open_dir4(self, context):
        if self.open_dir4:
            self.open_dir4 = False
            os.startfile(Path(self.model_path) / "SDNodeTemp")

    open_dir4: bpy.props.BoolProperty(default=False,
                                      name="Open Cache Folder",
                                      update=update_open_dir4)

    def draw_general(self, layout: bpy.types.UILayout):
        row = layout.row()
        row.prop(self, "server_type", text_ctxt=ctxt)
        if self.server_type == "Local":
            layout.prop(self, "model_path", text_ctxt=ctxt)
            layout.prop(self, "python_path", text_ctxt=ctxt)
            layout.prop(self, "with_webui_model")
            layout.prop(self, "with_comfyui_model")
            layout.prop(self, "cuda")
            layout.prop(self, "mem_level", text_ctxt=ctxt)
        row = layout.row(align=True)
        row.prop(self, "stencil_offset_size_xy", text_ctxt=ctxt)
        row.prop(self, "popup_scale", text_ctxt=ctxt)
        row.prop(self, "enable_hq_preview", text="", icon="IMAGE_BACKGROUND", text_ctxt=ctxt)
        row = layout.row(align=True)
        row.prop(self, "ip")
        row.prop(self, "port")
        row = layout.row(align=True)
        row.prop(self, "fixed_preview_image_size", toggle=True, text_ctxt=ctxt)
        row.prop(self, "preview_image_size", text_ctxt=ctxt)
        row = layout.row(align=True)
        row.label(text="Drag Link Result Count", text_ctxt=ctxt)
        row.prop(self, "drag_link_result_count_col", text="", text_ctxt=ctxt)
        row.prop(self, "drag_link_result_count_row", text="", text_ctxt=ctxt)
        if self.server_type == "Local":
            row = layout.row(align=True)
            row.prop(self, "auto_launch", toggle=True, text_ctxt=ctxt)
            row.prop(self, "install_deps", toggle=True, text_ctxt=ctxt)
            row.prop(self, "force_log", toggle=True, text_ctxt=ctxt)

    def draw_website(self, layout: bpy.types.UILayout):

        layout.label(text="-AIGODLIKE Adventure Community", text_ctxt=ctxt)
        row = layout.row()
        row.operator("wm.url_open", text="AIGODLIKE Open Source Community - Main Site", icon="URL", text_ctxt=ctxt).url = "https://www.aigodlike.com"
        row.label(text=" ", text_ctxt=ctxt)

        layout.label(text="-Good friends exploring in the AI world (alphabetical order)", text_ctxt=ctxt)
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

        layout.label(text="\"Thank you, these adventurers who are exploring and sharing their experience in the AI field, hurry up and follow them\"", text_ctxt=ctxt)

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
