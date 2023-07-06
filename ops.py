import bpy
import json
from pathlib import Path
from mathutils import Vector
from functools import partial
from .translation import ctxt
from .prop import Prop
from .utils import _T, logger, PngParse
from .timer import Timer
from .SDNode import TaskManager
from .SDNode.tree import InvalidNodeType


class Ops(bpy.types.Operator):
    bl_idname = "sdn.ops"
    bl_description = "SD Node"
    bl_label = "SD Node"
    bl_translation_context = ctxt
    action: bpy.props.StringProperty(default="")
    save_name: bpy.props.StringProperty(name="Preset Name", default="预设")
    alt: bpy.props.BoolProperty(default=False)

    @classmethod
    def description(cls, context: bpy.types.Context,
                    properties: bpy.types.OperatorProperties) -> str:
        desc = "SD Node"
        action = properties.get("action", "")
        if action == "PresetFromBookmark":
            desc = _T("Load from Bookmark")
        if action == "PresetFromClipBoard":
            desc = _T("Load from ClipBoard")
        elif action == "Launch":
            desc = _T(action)
        elif action == "Restart":
            desc = _T(action)
        elif action == "Submit":
            desc = _T("Submit Task and with Clear Cache if Alt Pressed")
        return desc

    def import_bookmark_set(self, value):
        path = Path(value)
        if not path.exists() or path.suffix.lower() not in {".png", ".json"}:
            logger.error(_T("Image not found or format error(png/json)"))
            logger.error(str(path))
            logger.error(path.cwd())
            return
        data = None
        if path.suffix.lower() == ".png":
            odata = PngParse.read_text_chunk(value)
            data = odata.get("workflow")
            if not data:
                logger.error(_T("Load Preset from Image Error -> MetaData Not Found in") + " " + str(odata))
                return
        elif path.suffix.lower() == ".json":
            data = path.read_text()

        tree = bpy.context.space_data.edit_tree
        if not tree:
            return
        tree.load_json(json.loads(data))

    import_bookmark: bpy.props.StringProperty(name="Preset Bookmark", default=str(Path.cwd()), subtype="FILE_PATH", set=import_bookmark_set)

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
        if self.action == "PresetFromBookmark":
            layout.label(text="Click Folder Icon to Select Bookmark:", text_ctxt=ctxt)
            layout.prop(self, "import_bookmark", text_ctxt=ctxt)

    def invoke(self, context, event: bpy.types.Event):
        self.alt = event.alt
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
        if self.action in {"Save", "SaveGroup", "Del", "DelGroup", "PresetFromBookmark"}:
            return wm.invoke_props_dialog(self, width=200)
        return self.execute(context)

    def find_frames_nodes(self, tree):
        frames_nodes = []
        for node in tree.nodes:
            if node.bl_idname != "输入图像":
                continue
            if node.mode != "序列图":
                continue
            frames_nodes.append(node)
        return frames_nodes

    def execute(self, context: bpy.types.Context):
        try:
            res = self.execute_ex(context)
            return res
        except InvalidNodeType as e:
            self.report({"ERROR"}, str(e.args))
            return {"FINISHED"}
        return {"FINISHED"}

    def execute_ex(self, context: bpy.types.Context):
        # logger.debug("EXE")
        if self.action == "Launch":
            if TaskManager.pid != -1:
                self.report({"ERROR"}, "服务已经启动!")
                return {"FINISHED"}
            TaskManager.restart_server()
            return {"FINISHED"}
        elif self.action == "Restart":
            TaskManager.restart_server()
            return {"FINISHED"}
        elif self.action == "Cancel":
            TaskManager.interrupt()
            return {"FINISHED"}
        tree = bpy.context.space_data.edit_tree
        if not tree:
            return {"FINISHED"}

        def get_task(tree):
            prompt = tree.serialize()
            workflow = tree.save_json()
            return {"prompt": prompt, "workflow": workflow, "api": "prompt"}
        # special for frames image mode
        if self.action == "Submit" and (frames_nodes := self.find_frames_nodes(tree)):
            def find_frames(path):
                frames_map = {}
                for file in Path(path).iterdir():
                    if file.suffix.lower() not in {".png", ".jpg"}:
                        continue
                    piece = file.stem.split("_")
                    try:
                        frames_map[int(piece[-1])] = file.as_posix()
                    except BaseException:
                        ...
                return frames_map
            node_frames = {}
            old_cfg = {}
            for fnode in frames_nodes:
                frames_dir = fnode.frames_dir
                if not frames_dir:
                    self.report({"ERROR"}, _T("Node<{}>Directory is Empty!").format(fnode.name))
                    return {"FINISHED"}
                if not Path(frames_dir).exists():
                    self.report({"ERROR"}, _T("Node<{}>Directory Not Exists!").format(fnode.name))
                    return {"FINISHED"}
                node_frames[fnode] = find_frames(frames_dir)
                old_cfg[fnode] = {}
                old_cfg[fnode]["mode"] = fnode.mode
                old_cfg[fnode]["image"] = fnode.image
            pnode, pframes = node_frames.popitem()
            pnode.mode = "输入"
            for frame in pframes:
                pnode.image = pframes[frame]
                # logger.debug(f"F {frame}: {pnode.image}")
                for fnode in node_frames:
                    if not (fpath := node_frames[fnode].get(frame, "")):
                        error_info = _T("Frame <{}> Not Found in <{}> Node Path!").format(frame, fnode.name)
                        # self.report({"ERROR"}, error_info)
                        logger.error(error_info)
                        break
                    fnode.mode = "输入"
                    fnode.image = fpath
                    # logger.debug(f"F {frame}: {fnode.image}")
                else:
                    logger.debug(_T("Frame Task <{}> Added!").format(frame))
                    TaskManager.push_task(get_task(tree))
            # restore config
            for fnode in old_cfg:
                setattr(fnode, "mode", old_cfg[fnode]["mode"])
                setattr(fnode, "image", old_cfg[fnode]["image"])
            return {"FINISHED"}
        elif self.action == "Submit":
            if self.alt:
                TaskManager.clear_cache()
            if bpy.context.scene.sdn.frame_mode == "MultiFrame":
                sf = bpy.context.scene.frame_start
                ef = bpy.context.scene.frame_end
                for cf in range(sf, ef + 1):
                    @Timer.wait_run
                    def pre(cf):
                        bpy.context.scene.frame_set(cf)
                    pre = partial(pre, cf)
                    TaskManager.push_task(get_task(tree), pre)
            elif bpy.context.scene.sdn.frame_mode == "Batch":
                batch_dir = bpy.context.scene.sdn.batch_dir
                select_node = tree.nodes.active
                if not select_node or select_node.bl_idname != "输入图像":
                    self.report({"ERROR"}, "Input Image Node Not Selected!")
                    return {"FINISHED"}

                if not batch_dir or not Path(batch_dir).exists():
                    self.report({"ERROR"}, "Batch Directory Not Set!")
                    return {"FINISHED"}
                old_mode, old_image = select_node.mode, select_node.image
                select_node.mode = "输入"
                for file in Path(batch_dir).iterdir():
                    if file.is_dir():
                        continue
                    if file.suffix not in {".png", ".jpg", ".jpeg"}:
                        continue
                    select_node.image = file.as_posix()
                    TaskManager.push_task(get_task(tree))
                select_node.mode, select_node.image = old_mode, old_image
            else:
                TaskManager.push_task(get_task(tree))
        elif self.action == "Restart":
            TaskManager.restart_server()
        elif self.action == "ClearTask":
            TaskManager.clear_all()
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
        elif self.action == "PresetFromBookmark":
            return {"FINISHED"}
            # png = Path(self.import_bookmark)
            # logger.error(self.import_bookmark)
            # if not png.exists() or png.suffix != ".png":
            #     self.report({"ERROR"}, "魔法图鉴不存在或格式不正确(仅png)")
            #     return {"FINISHED"}
            # data = PngParse.read_text_chunk(self.import_bookmark)
            # logger.error(data)
        elif self.action == "PresetFromClipBoard":
            try:
                from . import pyperclip
            except BaseException:
                self.report({"ERROR"}, _T("pyperclip import error"))
                return {"FINISHED"}
            try:
                data = pyperclip.paste()
                tree.load_json(json.loads(data))
            except json.JSONDecodeError:
                self.report({"ERROR"}, _T("ClipBoard Content Format Error"))
                return {"FINISHED"}
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
            if cam:
                mask = cam.get("SD_Mask", [])
                if None in mask:
                    mask.remove(None)
                mask.append(gpo)
                cam["SD_Mask"] = mask
        return {"FINISHED"}
