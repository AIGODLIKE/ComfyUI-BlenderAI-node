import typing
import bpy
import os
from pathlib import Path

from .utils import Icon, _T, FSWatcher
from .translations import ctxt
from .kclogger import logger


def dir_cb_test(path):
    return
    logger.info(f"{path} changed")


class PresetsDirDesc(bpy.types.PropertyGroup):
    def path_set(self, path):
        """检查路径是否合法"""
        if not path or path == self.path:
            return
        if not os.path.exists(path) or not os.path.isdir(path):
            return
        # 路径不能已经存在于pref_dirs中
        pref = get_pref()
        for item in pref.pref_dirs:
            if item.path != path:
                continue

            def error_draw(self, context):
                self.layout.label(text="Custom Preset Path already exists", text_ctxt=ctxt)
            bpy.context.window_manager.popup_menu(error_draw, title=_T("Error"), icon="ERROR")
            return

        self["path"] = path
        if pref.pref_dirs_init:
            # 创建presets/groups目录
            Path(path).joinpath("presets").mkdir(parents=True, exist_ok=True)
            Path(path).joinpath("groups").mkdir(parents=True, exist_ok=True)
        if self.enabled:
            FSWatcher.register(Path(path).joinpath("presets"), dir_cb_test)
            FSWatcher.register(Path(path).joinpath("groups"), dir_cb_test)

    def path_get(self):
        if "path" not in self:
            return ""
        return self["path"]
    path: bpy.props.StringProperty(name="Path", subtype="DIR_PATH", set=path_set, get=path_get)

    def update_enabled(self, context):
        p = Path(self.path)
        if self.enabled:
            FSWatcher.register(p.joinpath("presets"), dir_cb_test)
            FSWatcher.register(p.joinpath("groups"), dir_cb_test)
        else:
            FSWatcher.unregister(p.joinpath("presets"))
            FSWatcher.unregister(p.joinpath("groups"))
        from .prop import Prop
        Prop.mark_dirty()
    enabled: bpy.props.BoolProperty(name="Is Enabled?", default=True, update=update_enabled)


class PresetsDirEdit(bpy.types.Operator):
    bl_idname = "sdn.presets_dir_edit"
    bl_label = "Edit Presets Dir"
    bl_description = "Edit Presets Dir"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(items=[("ADD", "Add", "", "ADD", 0),
                                          ("REMOVE", "Remove", "", "REMOVE", 1)
                                          ],
                                   name="Action", options={"HIDDEN"})
    index: bpy.props.IntProperty(name="Index")

    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    def invoke(self, context, event):
        if self.action == "ADD":
            # 弹出文件夹选择框
            wm = bpy.context.window_manager
            wm.fileselect_add(self)
            return {"RUNNING_MODAL"}
        return self.execute(context)

    def execute(self, context):
        pref = get_pref()
        if self.action == "ADD":
            # 判断路径是否已经存在
            for item in pref.pref_dirs:
                if item.path != self.directory:
                    continue

                def error_draw(self, context):
                    self.layout.label(text="Custom Preset Path already exists", text_ctxt=ctxt)
                # 弹出一个面板
                bpy.context.window_manager.popup_menu(error_draw, title=_T("Error"), icon="ERROR")
                self.report({"ERROR"}, _T("Custom Preset Path already exists"))
                return {"CANCELLED"}
            item = pref.pref_dirs.add()
            item.path = self.directory
            p = Path(item.path)
            if pref.pref_dirs_init:
                # 创建presets/groups目录
                p.joinpath("presets").mkdir(parents=True, exist_ok=True)
                p.joinpath("groups").mkdir(parents=True, exist_ok=True)
            FSWatcher.register(p.joinpath("presets"), dir_cb_test)
            FSWatcher.register(p.joinpath("groups"), dir_cb_test)
        elif self.action == "REMOVE":
            pref.pref_dirs.remove(self.index)
            FSWatcher.unregister(Path(self.directory).joinpath("presets"))
            FSWatcher.unregister(Path(self.directory).joinpath("groups"))
        return {"FINISHED"}


class AddonPreference(bpy.types.AddonPreferences):
    bl_idname = __package__
    bl_translation_context = ctxt

    def update_debug(self, context):
        use_debug()
    debug: bpy.props.BoolProperty(default=False, name="Debug", update=update_debug)
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

    pref_dirs: bpy.props.CollectionProperty(type=PresetsDirDesc, name="Custom Presets", description="Custom Presets")
    pref_dirs_init: bpy.props.BoolProperty(default=True, name="Init Custom Preset Path", description="Create presets/groups dir if not exists")

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

    def draw_custom_presets(self, layout: bpy.types.UILayout):
        box = layout.box()
        box.label(text="Custom Presets", text_ctxt=ctxt)
        header = box.row(align=True)
        header.operator(PresetsDirEdit.bl_idname, text="Add Custom Presets Dir", icon="ADD", text_ctxt=ctxt).action = "ADD"
        header.prop(self, "pref_dirs_init", text="", icon="FILE_REFRESH", text_ctxt=ctxt)
        col = box.column(align=True)
        col.scale_y = 1.1
        for i, item in enumerate(self.pref_dirs):
            row = col.row(align=True)
            row.prop(item, "enabled", text="", icon="CHECKBOX_HLT", text_ctxt=ctxt)
            row.prop(item, "path", text="", text_ctxt=ctxt)
            op = row.operator(PresetsDirEdit.bl_idname, icon="REMOVE", text="", text_ctxt=ctxt)
            op.action = "REMOVE"
            op.index = i

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
        self.draw_custom_presets(layout)
        layout.prop(self, "debug", toggle=True, text_ctxt=ctxt)

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


@bpy.app.handlers.persistent
def pref_dirs_init(_):
    # 将pref_dirs 添加到 FSWatcher
    pref = get_pref()

    for item in pref.pref_dirs:
        logger.info(f"FS Register -> {item.path}")
        p = Path(item.path)
        if pref.pref_dirs_init:
            # 创建presets/groups目录
            p.joinpath("presets").mkdir(parents=True, exist_ok=True)
            p.joinpath("groups").mkdir(parents=True, exist_ok=True)
        FSWatcher.register(p.joinpath("presets"), dir_cb_test)
        FSWatcher.register(p.joinpath("groups"), dir_cb_test)


clss = [PresetsDirDesc, PresetsDirEdit, AddonPreference]
reg, unreg = bpy.utils.register_classes_factory(clss)


def use_debug():
    pref = get_pref()
    try:
        from .External.lupawrapper import LuaRuntime
        LuaRuntime.DEBUG = pref.debug
        for rt in LuaRuntime.get_rt_dict().values():
            liblogger = rt.load_dll("logger")
            if pref.debug:
                liblogger.set_global_level(0)
                print("Enable")
            else:
                liblogger.set_global_level(-1)
                print("Close")
            break
    except Exception:
        import traceback
        traceback.print_exc()


def pref_register():
    bpy.app.handlers.load_post.append(pref_dirs_init)
    reg()
    use_debug()


def pref_unregister():
    unreg()
    bpy.app.handlers.load_post.remove(pref_dirs_init)
