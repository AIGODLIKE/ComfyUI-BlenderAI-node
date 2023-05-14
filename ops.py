import bpy
import json
from pathlib import Path
from mathutils import Vector
from .translation import ctxt
from .prop import Prop
from .utils import _T, logger, PngParse
from .SDNode import TaskManager




class Ops(bpy.types.Operator):
    bl_idname = "sdn.ops"
    bl_description = "SD Node"
    bl_label = "SD Node"
    bl_translation_context = ctxt
    action: bpy.props.StringProperty(default="")
    save_name: bpy.props.StringProperty(name="Preset Name", default="预设")

    @classmethod
    def description(cls, context: bpy.types.Context,
                    properties: bpy.types.OperatorProperties) -> str:
        desc = "SD Node"
        if properties.get("action") == "Preset_from_Image":
            desc = "Load from Image"
        return desc

    def import_image_set(self, value):
        png = Path(value)
        if not png.exists() or png.suffix != ".png":
            logger.error(_T("Image not found or format error(png only)"))
            logger.error(str(png))
            logger.error(png.cwd())
            return
        odata = PngParse.read_text_chunk(value)
        data = odata.get("workflow")
        if not data:
            logger.error(_T("Load Preset from Image Error -> MetaData Not Found in") + " " + str(odata))
            return
        tree = bpy.context.space_data.edit_tree
        if not tree:
            return
        tree.load_json(json.loads(data))

    import_image: bpy.props.StringProperty(name="Preset Image", default=str(Path.cwd()), subtype="FILE_PATH", set=import_image_set)

    def draw(self, context):
        layout = self.layout
        if self.action == "Save":
            if (Path(bpy.context.scene.sdn.presets_dir) / f"{self.save_name}.json").exists():
                layout.alert = True
                layout.label(text=f"{_T('Preset')}<{self.save_name}>{_T('exists, Click Ok to Overwrite!')}", icon="ERROR", text_ctxt=ctxt)
                layout.label(text="Click Outside to Cancel!", icon="ERROR", text_ctxt=ctxt)
            layout.prop(self, "save_name", text_ctxt=ctxt)
        if self.action == "SaveGroup":
            if (Path(bpy.context.scene.sdn.groups_dir) / f"{self.save_name}.json").exists():
                layout.alert = True
                layout.label(text=f"{_T('Preset')}<{self.save_name}>{_T('exists, Click Ok to Overwrite!')}", icon="ERROR", text_ctxt=ctxt)
                layout.label(text="Click Outside to Cancel!", icon="ERROR", text_ctxt=ctxt)
            layout.prop(self, "save_name", text_ctxt=ctxt)

        if self.action == "Del":
            layout.alert = True
            layout.label(text=f"{_T('Preset')}<{Path(bpy.context.scene.sdn.presets).stem}>{_T('will be removed?')}", icon="ERROR", text_ctxt=ctxt)
            layout.label(text="Click Outside to Cancel!", icon="ERROR", text_ctxt=ctxt)
        if self.action == "DelGroup":
            layout.alert = True
            layout.label(text=f"{_T('Preset')}<{Path(bpy.context.scene.sdn.groups).stem}>{_T('will be removed?')}", icon="ERROR", text_ctxt=ctxt)
            layout.label(text="Click Outside to Cancel!", icon="ERROR", text_ctxt=ctxt)
        if self.action == "Preset_from_Image":
            layout.label(text="Click Folder Icon to Select Image:", text_ctxt=ctxt)
            layout.prop(self, "import_image", text_ctxt=ctxt)

    def invoke(self, context, event: bpy.types.Event):
        # logger.error("INVOKE")
        self.select_nodes = []
        self.init_pos = context.space_data.cursor_location.copy()
        if self.action in {"Load", "Del"}:
            if not bpy.context.scene.sdn.presets:
                self.report({"ERROR"}, _T("Preset Not Selected!"))
                return {"FINISHED"}

        if self.action in {"LoadGroup", "DelGroup"}:
            if not bpy.context.scene.sdn.groups:
                self.report({"ERROR"}, _T("Preset Not Selected!"))
                return {"FINISHED"}

        wm = bpy.context.window_manager
        if self.action in {"Save", "SaveGroup", "Del", "DelGroup", "Preset_from_Image"}:
            return wm.invoke_props_dialog(self, width=200)
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        # logger.debug("EXE")
        tree = bpy.context.space_data.edit_tree
        if not tree:
            return {"FINISHED"}
        if self.action == "Submit":
            prompt = tree.serialize()
            workflow = tree.save_json()
            TaskManager.push_task({"prompt": prompt, "workflow": workflow, "api": "prompt"})
        elif self.action == "Restart":
            TaskManager.restart_server()
        elif self.action == "Save":
            data = tree.save_json()
            if not self.save_name:
                self.report({"ERROR"}, _T("Invalid Preset Name!"))
                return {"CANCELLED"}
            file = Path(bpy.context.scene.sdn.presets_dir) / f"{self.save_name}.json"
            with open(file, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            Prop.mark_dirty()

        elif self.action == "Del":
            if not bpy.context.scene.sdn.presets:
                self.report({"ERROR"}, _T("Preset Not Selected!"))
                return {"FINISHED"}
            preset = Path(bpy.context.scene.sdn.presets)
            preset.unlink()
            self.report({"INFO"}, f"{preset.stem} {_T('Removed')}")
            Prop.mark_dirty()
        elif self.action == "Load":
            if not bpy.context.scene.sdn.presets:
                self.report({"ERROR"}, _T("Preset Not Selected!"))
                return {"FINISHED"}
            tree.load_json(json.load(open(bpy.context.scene.sdn.presets)))

        elif self.action == "SaveGroup":
            data = tree.save_json_group()
            if not self.save_name:
                self.report({"ERROR"}, _T("Invalid Preset Name!"))
                return {"CANCELLED"}
            file = Path(bpy.context.scene.sdn.groups_dir) / f"{self.save_name}.json"
            with open(file, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            Prop.mark_dirty()
        elif self.action == "DelGroup":
            if not bpy.context.scene.sdn.groups:
                self.report({"ERROR"}, _T("Preset Not Selected!"))
                return {"FINISHED"}
            preset = Path(bpy.context.scene.sdn.groups)
            preset.unlink()
            self.report({"INFO"}, f"{preset.stem} {_T('Removed')}")
            Prop.mark_dirty()
        elif self.action == "LoadGroup":
            if not bpy.context.scene.sdn.groups:
                self.report({"ERROR"}, _T("Preset Not Selected!"))
                return {"FINISHED"}
            select_nodes = tree.load_json_group(json.load(open(bpy.context.scene.sdn.groups)))
            if not select_nodes:
                return {"FINISHED"}
            self.select_nodes = select_nodes
            v = Vector([0, 0])
            for n in select_nodes:
                v += n.location
            v /= len(select_nodes)
            self.init_node_pos = {}
            for n in select_nodes:
                n.location += context.space_data.cursor_location - v
                self.init_node_pos[n] = n.location.copy()

            bpy.context.window_manager.modal_handler_add(self)
            return {"RUNNING_MODAL"}
        elif self.action == "Preset_from_Image":
            return {"FINISHED"}
            # png = Path(self.import_image)
            # logger.error(self.import_image)
            # if not png.exists() or png.suffix != ".png":
            #     self.report({"ERROR"}, "魔法图鉴不存在或格式不正确(仅png)")
            #     return {"FINISHED"}
            # data = PngParse.read_text_chunk(self.import_image)
            # logger.error(data)
        return {"FINISHED"}

    def update_nodes_pos(self, event):
        for n in self.select_nodes:
            n.location = self.init_node_pos[n] + bpy.context.space_data.cursor_location - self.init_pos

    def modal(self, context, event: bpy.types.Event):
        if not self.select_nodes:
            return {"FINISHED"}
        if event.type == "MOUSEMOVE":
            self.update_nodes_pos(event)

        # exit
        if event.value == "PRESS" and event.type in {"ESC", "LEFTMOUSE", "ENTER"}:
            return {"FINISHED"}
        if event.value == "PRESS" and event.type in {"RIGHTMOUSE"}:
            tree = bpy.context.space_data.edit_tree
            tree.safe_remove_nodes(self.select_nodes[:])
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}


class Ops_Mask(bpy.types.Operator):
    bl_idname = "sdn.mask"
    bl_label = "蒙版"
    bl_description = "Mask Operator"
    action: bpy.props.StringProperty(default="add")
    node_name: bpy.props.StringProperty()

    def execute(self, context):
        tree = bpy.context.space_data.edit_tree
        if not tree:
            self.report({"ERROR"}, "No NodeTree Found")
            return {"FINISHED"}
        node = tree.nodes.get(self.node_name)
        if not node:
            self.report({"ERROR"}, _T("Node Not Found: ") + self.node_name)
            return {"FINISHED"}
        cam = bpy.context.scene.camera

        if self.action == "add":
            if bpy.context.area.type == "IMAGE_EDITOR":
                # 激活笔刷
                context.space_data.ui_mode = "PAINT"
                context.space_data.display_channels = "COLOR"
                bpy.ops.wm.tool_set_by_id(name="builtin_brush.Draw")
                brush = context.tool_settings.image_paint.brush
                brush.blend = "ERASE_ALPHA"
                brush.color = 1, 1, 1
                brush.strength = 1
                brush.curve_preset = 'CONSTANT'
                context.tool_settings.unified_paint_settings.size = 50

                return {"FINISHED"}

            mask = []
            if cam and "SD_Mask" in cam:
                mask.extend(cam["SD_Mask"])

            gp = bpy.data.grease_pencils.new("AI_GP")
            layer = gp.layers.new("GP_Layer")
            layer.frames.new(bpy.context.scene.frame_current)
            # for frame in layer.frames:
            #     print("Layer: %s, Frame: %d" % (layer.info, frame.frame_number))
            gpo = bpy.data.objects.new(name=gp.name, object_data=gp)
            gpo.hide_render = True
            node.gp = gpo
            
            bpy.context.scene.collection.objects.link(gpo)
            bpy.context.view_layer.objects.active = gpo
            mat = bpy.data.materials.new(gpo.name)
            bpy.data.materials.create_gpencil_data(mat)
            gpo.data.materials.append(mat)
            gpo.active_material = mat
            mat.grease_pencil.color = (1, 1, 1, 1)
            gpo.show_in_front = True
            bpy.ops.object.mode_set(mode="PAINT_GPENCIL")
            brush = bpy.context.tool_settings.gpencil_paint.brush
            brush.gpencil_settings.pen_strength = 1
            brush.size = 250
            mask.append(gpo)
            if cam:
                cam["SD_Mask"] = mask
        return {"FINISHED"}
