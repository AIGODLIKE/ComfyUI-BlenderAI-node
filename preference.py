import typing
import bpy
import os
from pathlib import Path

from bpy.types import Context
from .utils import Icon, _T
from .translation import ctxt

class EnableMLT(bpy.types.Operator):
    bl_idname = "sdn.enable_mlt"
    bl_description = "Enable MLT"
    bl_label = "Enable MLT"
    bl_translation_context = ctxt
    
    def execute(self, context: Context):
        from .MultiLineText import enable_multiline_text
        if not enable_multiline_text():
            self.report({"ERROR"}, "MultiLineText Not Enabled")
        bpy.ops.object.multiline_text("INVOKE_DEFAULT")
        return {"FINISHED"}
    
class AddonPreference(bpy.types.AddonPreferences):
    bl_idname = __package__
    bl_translation_context = ctxt
    
    popup_scale: bpy.props.IntProperty(default=5, min=1, max=100, name="预览图尺寸")
    enable_hq_preview: bpy.props.BoolProperty(default=True, name="启用高清预览图")
    
    def update_model(self, context):
        from .SDNode import TaskManager
        TaskManager.restart_server()

    model_path: bpy.props.StringProperty(subtype="DIR_PATH", name="ComfyUI路径",
                                         default=str(Path(__file__).parent / "ComfyUI"),
                                         update=update_model)
    page: bpy.props.EnumProperty(items=[("通用", "通用", "", "COLLAPSEMENU", 0),
                                        ("常用路径", "常用路径", "", "URL", 1),
                                        ("友情链接", "友情链接", "", "URL", 2),
                                        ], default=0)
    cpu_only: bpy.props.BoolProperty(default=False)  # --cpu

    mem_level: bpy.props.EnumProperty(name="显存模式",
                                      items=[("--highvram", "高显存", "模型常驻显存, 减少加载时间", 1),
                                             ("--normalvram", "中显存", "自动启用 低显存 模式时强制使用normal vram", 2),
                                             ("--lowvram", "低显存", "拆分UNet来降低显存开销", 3),
                                             ("--novram", "超低显存", "如果低显存依然不够", 4),
                                             ("--cpu", "仅CPU", "只使用CPU", 5),
                                             ],
                                      default="--lowvram")
    with_webui_model: bpy.props.StringProperty(default="", name="With WEBUI Model", description="webui位置", subtype="DIR_PATH")
    with_comfyui_model: bpy.props.StringProperty(default="", name="With ComfyUI Model", description="ComfyUI位置", subtype="DIR_PATH")

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
