import bpy
import re
import json
import tempfile
import time
import re
import uuid
from typing import Any
from pathlib import Path
from bpy.types import Context, Event
from mathutils import Vector
from functools import partial
from .translations import ctxt
from .prop import Prop
from .utils import _T, logger, FSWatcher, read_json
from .timer import Timer, Worker, WorkerFunc
from .SDNode import TaskManager
from .SDNode.history import History
from .SDNode.tree import InvalidNodeType, CFNodeTree, TREE_TYPE, rtnode_reg, rtnode_unreg
from .SDNode.utils import get_default_tree
from .datas import IMG_SUFFIX
from .preference import get_pref


def find_nodes_by_idname(tree, idname, find_nodes=None):
    if find_nodes is None:
        find_nodes = []
    for node in tree.nodes:
        if node.bl_idname == idname:
            find_nodes.append(node)
        if node.type == "GROUP":
            find_nodes_by_idname(node.node_tree, idname, find_nodes)
    return find_nodes


class LoopExec(WorkerFunc):
    args = {}
    # 单例
    instance = None

    def __new__(cls, *args, **kwargs):
        if not cls.instance:
            cls.instance = super().__new__(cls)
            cls.instance.args = {}
        return cls.instance

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if TaskManager.get_task_num() != 0:
            return
        tree: CFNodeTree = LoopExec.args.get("tree", None)
        try:
            tree.load_json
        except ReferenceError:
            return
        except AttributeError:
            return
        with bpy.context.temp_override(sdn_tree=tree):
            bpy.ops.sdn.ops(action="Submit")


class Ops(bpy.types.Operator):
    bl_idname = "sdn.ops"
    bl_description = "SD Node"
    bl_label = "SD Node"
    bl_translation_context = ctxt
    action: bpy.props.StringProperty(default="")
    save_name: bpy.props.StringProperty(name="Preset Name", default="预设")
    alt: bpy.props.BoolProperty(default=False)
    is_advanced_enable = False

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
            desc = _T("Launch/Connect to ComfyUI")
        elif action == "Restart":
            desc = _T("Restart ComfyUI")
        elif action == "Connect":
            desc = _T("Connect to existing & running ComfyUI server")
        elif action == "Submit":
            desc = _T("Submit Task, with Clear Cache if Alt pressed")
        elif action == "Close":
            desc = _T("Close/Disconnect from ComfyUI")
        return desc

    def draw(self, context):
        layout = self.layout
        if self.action == "Submit" and not TaskManager.is_launched():
            layout.label(text=_T("ComfyUI not running, run?"), icon="INFO", text_ctxt=ctxt)
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
            layout.prop(bpy.context.scene.sdn, "import_bookmark", text_ctxt=ctxt)

    def invoke(self, context, event: bpy.types.Event):
        self.exec_tree: CFNodeTree = None
        wm = bpy.context.window_manager
        self.alt = event.alt
        self.select_nodes = []
        self.init_pos = context.space_data.cursor_location.copy()
        if self.action == "Submit" and not TaskManager.is_launched():
            return wm.invoke_props_dialog(self, width=200)
        if self.action in {"Load", "Del"}:
            if not bpy.context.scene.sdn.presets:
                self.report({"ERROR"}, _T("Preset Not Selected!"))
                return {"FINISHED"}

        if self.action in {"LoadGroup", "DelGroup"}:
            if not bpy.context.scene.sdn.groups:
                self.report({"ERROR"}, _T("Preset Not Selected!"))
                return {"FINISHED"}

        if self.action in {"Save", "SaveGroup", "Del", "DelGroup", "PresetFromBookmark"}:
            return wm.invoke_props_dialog(self, width=200)
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        try:
            if res := getattr(self, self.action)():
                return res
            return {"FINISHED"}
        except InvalidNodeType as e:
            self.report({"ERROR"}, str(e.args))
        return {"FINISHED"}

    def modal(self, context, event: bpy.types.Event):
        if not self.select_nodes:
            return {"FINISHED"}
        if event.type == "MOUSEMOVE":
            self.update_nodes_pos(event)

        # exit
        if event.value == "PRESS" and event.type in {"ESC", "LEFTMOUSE", "ENTER"}:
            return {"FINISHED"}
        if event.value == "PRESS" and event.type in {"RIGHTMOUSE"}:
            self.exec_tree.safe_remove_nodes(self.select_nodes[:])
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    def find_frames_nodes(self, tree):
        nodes = [n for n in find_nodes_by_idname(tree, "输入图像") if n.mode == "序列图"]
        return nodes

    def find_mat_image_nodes(self, tree):
        nodes = find_nodes_by_idname(tree, "材质图")
        return nodes[0] if nodes else None

    def ensure_tree(self) -> CFNodeTree:
        tree = get_default_tree()
        if not tree:
            bpy.ops.node.new_node_tree(type=TREE_TYPE, name="NodeTree")
            tree = get_default_tree()
        return tree

    def submit(self):
        tree: CFNodeTree = get_default_tree()
        if not tree:
            logger.error(_T("No Node Tree Found!"))
            self.report({"ERROR"}, _T("No Node Tree Found!"))
            return
        def reset_error_mark(tree: CFNodeTree):
            if not tree:
                return
            from mathutils import Color
            for n in tree.nodes:
                if not n.label.endswith(("-ERROR", "-EXEC")) or n.color != Color((1, 0, 0)):
                    continue
                n.use_custom_color = False
                n.label = ""
        reset_error_mark(tree)

        def get_task(tree: CFNodeTree):
            prompt = tree.serialize()
            workflow = tree.save_json()
            return {"prompt": prompt, "workflow": workflow, "api": "prompt"}
        if bpy.context.scene.sdn.advanced_exe and not Ops.is_advanced_enable:
            Ops.is_advanced_enable = True
            if bpy.context.scene.sdn.loop_exec:
                loop_exec = LoopExec()
                loop_exec.args["tree"] = tree
                Worker.push_worker(loop_exec)
                return {"FINISHED"}
            for _ in range(bpy.context.scene.sdn.batch_count):
                bpy.ops.sdn.ops(action="Submit")
            Ops.is_advanced_enable = False
            return {"FINISHED"}
        elif frames_nodes := self.find_frames_nodes(tree):

            def find_frames(path):
                frames_map = {}
                for file in Path(path).iterdir():
                    if file.suffix.lower() not in IMG_SUFFIX:
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
                pre_img_map = {pnode: pframes[frame]}
                for fnode, node_frame in node_frames.items():
                    if not (fpath := node_frame.get(frame, "")):
                        error_info = _T("Frame <{}> Not Found in <{}> Node Path!").format(frame, fnode.name)
                        # self.report({"ERROR"}, error_info)
                        logger.error(error_info)
                        break
                    fnode.mode = "输入"
                    fnode.image = fpath
                    pre_img_map[fnode] = fpath
                    # logger.debug(f"F {frame}: {fnode.image}")
                else:
                    logger.debug(_T("Frame Task <{}> Added!").format(frame))
                    def pre(pre_img_map: dict):
                        for fnode, fpath in pre_img_map.items():
                            try:
                                fnode.image = fpath
                            except Exception:
                                ...
                    TaskManager.push_task(get_task(tree), tree=tree, pre=partial(pre, pre_img_map))
            # restore config
            for fnode, cfg in old_cfg.items():
                setattr(fnode, "mode", cfg["mode"])
                setattr(fnode, "image", cfg["image"])
            return {"FINISHED"}
        elif mat_image_node := self.find_mat_image_nodes(tree):
            def recursive_node_parent(node, find_nodes=None):
                # 查找 node 相连的所有父级节点
                if find_nodes is None:
                    find_nodes = []
                for inp in node.inputs:
                    if not inp.is_linked:
                        continue
                    for link in inp.links:
                        if link.from_node in find_nodes:
                            continue
                        find_nodes.append(link.from_node)
                        recursive_node_parent(link.from_node, find_nodes)
                return find_nodes

            def find_obj_mat_images(obj):
                # 搜索 Mesh Object的所有材质的所有图片节点
                images = []
                image_nodes = []
                for mat in obj.data.materials:
                    fnodes = find_nodes_by_idname(mat.node_tree, "ShaderNodeTexImage")
                    image_nodes.extend(fnodes)
                for img_node in image_nodes:
                    if not img_node.image:
                        continue
                    images.append(img_node.image)
                return images
            save_nodes = find_nodes_by_idname(tree, "存储")
            images = []
            query_objs = []
            if mat_image_node.mode == "Object":
                query_objs.append(mat_image_node.obj)
            elif mat_image_node.mode == "Selected Objects":
                query_objs.extend(bpy.context.selectable_objects)
            elif mat_image_node.mode == "Collection":
                collection: bpy.types.Collection = mat_image_node.collection
                query_objs.extend(collection.objects)
            for obj in query_objs:
                if obj.type != "MESH":
                    continue
                images.extend(find_obj_mat_images(obj))
            if not images:
                self.report({"ERROR"}, _T("No Images Found!"))
                return {"FINISHED"}
            marked_sn = []
            for sn in save_nodes:
                if sn.mode != "ToImage":
                    continue
                p = recursive_node_parent(sn)
                if mat_image_node not in p:
                    continue
                marked_sn.append(sn)
            # 批量构造任务
            for img in set(images):
                for sn in marked_sn:
                    sn.image = img
                # 过滤 Render Result
                if img.source == "VIEWER":
                    continue
                # mat_image_node的image必须为路径, 因此需要将img存储到本地(如果不是本地图片)
                filepath = Path(img.filepath)
                if not filepath.exists() or filepath.suffix.lower() not in IMG_SUFFIX:
                    filepath = Path(tempfile.gettempdir()) / img.name
                    filepath = filepath.with_suffix(".png")
                    tf = filepath.resolve().as_posix()
                    img.save(filepath=tf)
                    img.filepath = filepath.resolve().as_posix()
                    img.filepath_raw = img.filepath
                mat_image_node.image = FSWatcher.to_str(filepath)
                TaskManager.push_task(get_task(tree), tree=tree)
            return {"FINISHED"}
        else:
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
                    TaskManager.push_task(get_task(tree), pre, tree=tree)
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
                    if file.suffix not in IMG_SUFFIX:
                        continue
                    select_node.image = file.as_posix()
                    TaskManager.push_task(get_task(tree), tree=tree)
                select_node.mode, select_node.image = old_mode, old_image
            else:
                TaskManager.push_task(get_task(tree), tree=tree)
        return {"FINISHED"}

    def update_nodes_pos(self, event):
        for n in self.select_nodes:
            n.location = self.init_node_pos[n] + bpy.context.space_data.cursor_location - self.init_pos

    def Launch(self):
        if TaskManager.is_launched():
            self.report({"ERROR"}, "服务已经启动!")
            return
        self.Restart()

    def Submit(self):
        if not TaskManager.is_launched():
            self.Launch()
        self.submit()

    def Connect(self):
        TaskManager.connect_existing = not TaskManager.connect_existing
        if TaskManager.connect_existing:
            TaskManager.launch_ip = get_pref().ip
            TaskManager.launch_port = get_pref().port
            TaskManager.launch_url = f"http://{get_pref().ip}:{get_pref().port}"
            rtnode_unreg()
            rtnode_reg()
            CFNodeTree.refresh_current_tree()
            TaskManager.start_polling()

    def Close(self):
        if tree := get_default_tree():
            # 恢复节点颜色
            for n in tree.nodes:
                if not n.label.endswith(("-EXEC", "-ERROR")):
                    continue
                n.use_custom_color = False
                n.label = ""
        TaskManager.close_server()
        # hack fix tree update crash
        CFNodeTree.refresh_current_tree()

    def Restart(self):
        TaskManager.restart_server()
        # hack fix tree update crash
        CFNodeTree.refresh_current_tree()

    def Cancel(self):
        TaskManager.interrupt()

    def StopLoop(self):
        Ops.is_advanced_enable = False
        Worker.remove_worker(LoopExec())

    def ClearTask(self):
        TaskManager.clear_all()

    def Save(self):
        tree = get_default_tree()

        if not tree:
            logger.error(_T("No Node Tree Found!"))
            self.report({"ERROR"}, _T("No Node Tree Found!"))
            return
        if not self.save_name:
            self.report({"ERROR"}, _T("Invalid Preset Name!"))
            return
        data = tree.save_json()
        file = Path(bpy.context.scene.sdn.presets_dir) / f"{self.save_name}.json"
        with open(file, "w", encoding="utf8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        Prop.mark_dirty()

    def Del(self):
        if not bpy.context.scene.sdn.presets:
            self.report({"ERROR"}, _T("Preset Not Selected!"))
            return
        preset = Path(bpy.context.scene.sdn.presets)
        preset.unlink()
        self.report({"INFO"}, f"{preset.stem} {_T('Removed')}")
        Prop.mark_dirty()

    def Load(self):
        if not bpy.context.scene.sdn.presets:
            self.report({"ERROR"}, _T("Preset Not Selected!"))
            return
        tree = self.ensure_tree()
        tree.load_json(read_json(bpy.context.scene.sdn.presets))

    def SaveGroup(self):
        tree = get_default_tree()
        if not tree:
            logger.error(_T("No Node Tree Found!"))
            self.report({"ERROR"}, _T("No Node Tree Found!"))
            return
        if not self.save_name:
            self.report({"ERROR"}, _T("Invalid Preset Name!"))
            return
        data = tree.save_json_group()
        file = Path(bpy.context.scene.sdn.groups_dir) / f"{self.save_name}.json"
        with open(file, "w", encoding="utf8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        Prop.mark_dirty()

    def DelGroup(self):
        if not bpy.context.scene.sdn.groups:
            self.report({"ERROR"}, _T("Preset Not Selected!"))
            return
        preset = Path(bpy.context.scene.sdn.groups)
        preset.unlink()
        self.report({"INFO"}, f"{preset.stem} {_T('Removed')}")
        Prop.mark_dirty()

    def LoadGroup(self):
        if not bpy.context.scene.sdn.groups:
            self.report({"ERROR"}, _T("Preset Not Selected!"))
            return
        tree = self.ensure_tree()
        select_nodes = tree.load_json_group(read_json(bpy.context.scene.sdn.groups))
        if not select_nodes:
            return
        self.select_nodes = select_nodes
        v = Vector([0, 0])
        for n in select_nodes:
            v += n.location
        v /= len(select_nodes)
        self.init_node_pos = {}
        for n in select_nodes:
            n.location += bpy.context.space_data.cursor_location - v
            self.init_node_pos[n] = n.location.copy()
        bpy.context.window_manager.modal_handler_add(self)
        self.exec_tree = tree
        return {"RUNNING_MODAL"}

    def PresetFromBookmark(self):
        return

    def PresetFromClipBoard(self):
        try:
            data = bpy.context.window_manager.clipboard
            data = json.loads(data)
            if not isinstance(data, dict):
                self.report({"ERROR"}, _T("ClipBoard Content Format Error"))
                return
            if "workflow" in data:
                data = data["workflow"]
            tree = self.ensure_tree()
            tree.load_json(data)
        except json.JSONDecodeError:
            self.report({"ERROR"}, _T("ClipBoard Content Format Error"))


class Ops_Mask(bpy.types.Operator):
    bl_idname = "sdn.mask"
    bl_label = "蒙版"
    bl_description = "Mask Operator"
    action: bpy.props.StringProperty(default="add")
    node_name: bpy.props.StringProperty()
    cam_name: bpy.props.StringProperty(default="")

    def execute(self, context):
        tree = get_default_tree(context)
        if not tree:
            self.report({"ERROR"}, "No NodeTree Found")
            return {"FINISHED"}
        node = tree.nodes.get(self.node_name)
        if not node:
            self.report({"ERROR"}, _T("Node Not Found: ") + self.node_name)
            return {"FINISHED"}
        cam = bpy.context.scene.camera
        if self.cam_name:
            cam = bpy.context.scene.objects.get(self.cam_name)
            self.cam_name = ""

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


class Load_History(bpy.types.Operator):
    bl_idname = "sdn.load_history"
    bl_label = "Load History"
    bl_description = "Load History Workflow"
    name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context: Context):
        return get_default_tree(context)

    def execute(self, context):
        tree = get_default_tree(context)
        if not tree:
            self.report({"ERROR"}, _T("No Node Tree Found!"))
            return {"FINISHED"}
        data = History.get_history_by_name(self.name)
        if not data:
            self.report({"ERROR"}, _T("History Not Found: ") + self.name)
            return {"FINISHED"}
        if "workflow" in data:
            data = data["workflow"]
        tree.load_json(data)
        return {"FINISHED"}


class Popup_Load(bpy.types.Operator):
    bl_idname = "sdn.popup_load"
    bl_label = "Popup Load"
    bl_description = "Popup Load"
    filepath: bpy.props.StringProperty()

    def execute(self, context):
        file = Path(self.filepath)
        if file.suffix == ".csv":
            bpy.ops.sdn.load_batch("EXEC_DEFAULT", filepath=file.as_posix())
        elif file.suffix in {".png", ".json"}:
            bpy.context.scene.sdn.import_bookmark = file.as_posix()
        return {"FINISHED"}


class Copy_Tree(bpy.types.Operator):
    bl_idname = "sdn.copy_tree"
    bl_label = "Copy Tree to ClipBoard"
    bl_description = "Copy Tree to ClipBoard"
    bl_translation_context = ctxt
    name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context: Context):
        return getattr(bpy.context.space_data, "edit_tree", False)

    def execute(self, context):
        tree: CFNodeTree = get_default_tree(context)
        try:
            workflow = tree.save_json()
        except Exception as e:
            self.report({"ERROR"}, str(e.args))
            return {"FINISHED"}
        bpy.context.window_manager.clipboard = json.dumps(workflow, ensure_ascii=False)
        # 弹出提示 已复制到剪切板

        def draw(pm: bpy.types.UIPopupMenu, context):
            layout = pm.layout
            layout.label(text=_T("Tree Copied to ClipBoard"))
        bpy.context.window_manager.popup_menu(draw, title=_T("Tree Copied to ClipBoard"), icon="INFO")
        return {"FINISHED"}


class Load_Batch(bpy.types.Operator):
    bl_idname = "sdn.load_batch"
    bl_label = "Load Batch Task"
    bl_description = "Load Batch Task"
    bl_translation_context = ctxt
    filter_glob: bpy.props.StringProperty(default="*.csv", options={"HIDDEN"})
    filepath: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context: Context):
        return getattr(bpy.context.space_data, "edit_tree", False)

    def invoke(self, context: Context, event: Event):
        # 弹出文件选择框
        wm = bpy.context.window_manager
        wm.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        import csv
        # 批量任务格式
        # 任务索引, 节点名.参数名, 参数值, 节点名.参数名, 参数值, ...
        csv_path = Path(self.filepath)

        if not csv_path.exists():
            self.report({"ERROR"}, _T("File Not Found: ") + self.filepath)
            return {"FINISHED"}
        tree = get_default_tree(context)
        if not tree:
            self.report({"ERROR"}, _T("No Node Tree Found!"))
            return {"FINISHED"}
        tasks = []
        for coding in ["utf-8", "gbk"]:
            try:
                tasks.clear()
                with open(csv_path, "r", encoding=coding) as f:
                    reader = csv.reader(f)
                    for row in reader:
                        tasks.append(row)
                break
            except UnicodeDecodeError:
                continue

        for task in tasks:
            if not task:
                continue
            task_index = task[0]
            pairs = task[1:]
            if set(pairs) == {""}:
                continue
            for i in range(len(pairs) // 2):
                n_dot_pname, pvalue = pairs[i * 2: i * 2 + 2]
                if not n_dot_pname or not pvalue:
                    continue
                # nodes["nname"].pname
                nname, pname = re.match(r"nodes\[\"(.+)\"\]\.(.+)", n_dot_pname).groups()
                node = tree.nodes.get(nname)
                if not node or not node.get_meta(pname):
                    continue
                ptype = type(getattr(node, pname))
                # print(node, pname, pvalue, ptype)
                setattr(node, pname, ptype(pvalue))

            # 提交任务
            bpy.ops.sdn.ops("INVOKE_DEFAULT", action="Submit")
        return {"FINISHED"}


class Fetch_Node_Status(bpy.types.Operator):
    bl_idname = "sdn.fetch_node_status"
    bl_label = "Fetch Node Status"
    bl_description = "Fetch Node Status"
    bl_translation_context = ctxt

    @classmethod
    def poll(cls, context: Context):
        return getattr(bpy.context.space_data, "edit_tree", False)

    def execute(self, context):
        # from .SDNode.tree import rtnode_reg_diff
        # t0 = time.time()
        # rtnode_reg_diff()
        # logger.info(_T("RegNodeDiff Time:") + f" {time.time()-t0:.2f}s")
        Timer.clear()
        t1 = time.time()
        rtnode_unreg()
        t2 = time.time()
        logger.info(_T("UnregNode Time:") + f" {t2-t1:.2f}s")

        t3 = time.time()
        rtnode_reg()
        t4 = time.time()
        logger.info(_T("RegNode Time:") + f" {t4-t3:.2f}s")
        CFNodeTree.refresh_current_tree()
        return {"FINISHED"}


class NodeSearch(bpy.types.Operator):
    bl_idname = "sdn.node_search"
    bl_label = "Node Search"
    bl_options = {"REGISTER"}
    bl_property = "item"

    def node_items(self, context):
        from .SDNode.tree import NodeBase
        from .utils import _T2
        return [(sb.class_type, _T2(sb.class_type), "") for sb in NodeBase.__subclasses__()]
    item: bpy.props.EnumProperty(items=node_items)

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"CANCELLED"}

    def execute(self, context):
        if not get_default_tree():
            self.report({'ERROR'}, _T("No NodeTree Found"))
            return {"FINISHED"}
        try:
            bpy.ops.node.add_node(use_transform=True, settings=[], type=self.item)
        except BaseException:
            self.report({'WARNING'}, f"未定义的节点 > {self.item}")
        try:
            bpy.ops.node.translate_attach("INVOKE_DEFAULT")
        except RuntimeError:
            ...
        return {"FINISHED"}


class Clear_Node_Cache(bpy.types.Operator):
    bl_idname = "sdn.clear_node_cache"
    bl_label = "Clear Node Cache"
    bl_description = "If there is a node parsing error, you can delete the node cache with this button, then restart Blender"
    bl_translation_context = ctxt

    def execute(self, context):
        node_cache_path = Path(__file__).parent.joinpath("SDNode", "object_info.json")
        if not node_cache_path.exists():
            return {"FINISHED"}
        try:
            node_cache_path.unlink()
            self.report({"INFO"}, _T("Node Cache Cleared!"))
        except Exception as e:
            self.report({"ERROR"}, _T("Node Cache Clear Failed!") + f" {e}")
        return {"FINISHED"}


class Sync_Stencil_Image(bpy.types.Operator):
    bl_idname = "sdn.sync_stencil_image"
    bl_label = "Sync Stencil Image"
    bl_description = "Sync Stencil Image"
    bl_translation_context = ctxt
    action: bpy.props.StringProperty(default="")
    areas = set()

    def execute(self, context: Context):
        if self.action == "Clear":
            self.areas.discard(context.area)
            return {"FINISHED"}
        self.areas.add(context.area)
        wm = context.window_manager
        wm.modal_handler_add(self)
        self._timer = wm.event_timer_add(1 / 60, window=context.window)
        return {"RUNNING_MODAL"}

    def modal(self, context: Context, event: Event):
        if context.area not in self.areas:
            return {"FINISHED"}
        if not context.area:
            return {"FINISHED"}
        if context.area.type != "VIEW_3D":
            return {"PASS_THROUGH"}
        # 鼠标不在当前viewport则返回
        in_area = context.area.x + context.area.width > event.mouse_x > context.area.x and context.area.y + context.area.height > event.mouse_y > context.area.y
        if not in_area:
            return {"PASS_THROUGH"}

        from bl_ui.properties_paint_common import UnifiedPaintPanel

        rv3d: bpy.types.RegionView3D = bpy.context.space_data.region_3d
        area = context.area
        # zoom to fac powf((float(M_SQRT2) + camzoom / 50.0f), 2.0f) / 4.0f;
        # max(area.width, area.height) * fac
        fac = (2**0.5 + rv3d.view_camera_zoom / 50)**2 / 4
        length = max(area.width, area.height) * fac

        settings = UnifiedPaintPanel.paint_settings(context)
        brush: bpy.types.Brush = settings.brush  # 可能报错 没brush(settings为空)
        width, height = area.width, area.height
        if not brush:
            return {"PASS_THROUGH"}
        sos = get_pref().stencil_offset_size_xy
        offset_top = Vector(sos) * bpy.context.preferences.view.ui_scale
        enable_cam_offset = False
        if enable_cam_offset:
            coffx, coffy = rv3d.view_camera_offset
            coffw = coffx * width
            coffh = coffy * height
            hwidth = width / 2
            hheight = height / 2
            fac = (2**0.5 + rv3d.view_camera_zoom / 50)**2 / 4
            brush.stencil_pos = (hwidth - coffw, hheight - offset_top.y - coffh)
        else:
            rv3d.view_camera_offset = (0, 0)
            pos = (width / 2 - offset_top.x, height / 2 - offset_top.y)
            dim = (length / 2, length / 2)
            self.update_brush(brush, pos, dim)
        if rv3d.view_perspective != "CAMERA":
            rv3d.view_perspective = "CAMERA"
        return {"PASS_THROUGH"}

    def update_brush(self, brush: bpy.types.Brush, pos, dim):
        pos = Vector(pos)
        dim = Vector(dim)
        if brush.stencil_dimension != dim:
            brush.stencil_dimension = dim
        if brush.stencil_pos != pos:
            brush.stencil_pos = pos


def menu_sync_stencil_image(self: bpy.types.Menu, context: bpy.types.Context):
    if context.space_data.type != "VIEW_3D":
        return
    if context.area in Sync_Stencil_Image.areas:
        col = self.layout.column()
        col.alert = True
        col.operator(Sync_Stencil_Image.bl_idname, text="Stop Syncing Stencil Image", icon="PAUSE").action = "Clear"
    else:
        self.layout.operator(Sync_Stencil_Image.bl_idname, icon="PLAY")


bpy.types.VIEW3D_PT_tools_brush_settings.append(menu_sync_stencil_image)
# bpy.types.VIEW3D_PT_tools_brush_display.append(menu_sync_stencil_image)

def sdn_get_image(node: bpy.types.Node):
    if node.bl_idname in ('PreviewImage', '预览') and len(node.prev) > 0: # '预览' "Preview" Blender-side node
        return node.prev[0].image

    if node.bl_idname == '输入图像': # "Input Image" Blender-side node
        return node.prev

    if node.bl_idname == '存储' and node.mode == 'ToImage': # "Save" Blender-side node
        return node.image

    image = None

    if node.bl_idname == 'SaveImage' or (node.bl_idname == '存储' and node.mode == 'Save'):
        path = Path(node.output_dir)
        prefix = node.filename_prefix
        file_re = re.compile(f'{prefix}_([0-9]+)') # Should the _ at the end be included? 
        biggest = (None, -1)
        if (len(node.inputs) == 1 or node.inputs[1].connections == ()) and path.is_dir():
            # Find newest image, by filename
            for f in path.iterdir():
                if f.is_file():
                    match = file_re.match(f.stem)
                    if match and int(match.groups()[0]) > biggest[1]:
                        biggest = (f, int(match.groups()[0]))

            # If found, see if loaded, create if not
            if biggest[0] != None:
                for im in bpy.data.images:
                    if im.filepath == f.as_posix():
                        image = im
                        break
                
                if image == None:
                    image = bpy.data.images.new(f.stem + f.suffix, 32, 32)
                    image.source = 'FILE'
                    image.filepath = f.as_posix()
                
                return image
    
    return image

def get_imeditor(context: bpy.types.Context, check_for_image: bool = False):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if check_for_image:
                if area.type == 'IMAGE_EDITOR' and area.spaces[0].image and len(area.spaces[0].image.pixels) > 0:
                    return area
            else:
                if area.type == 'IMAGE_EDITOR' and not area.spaces[0].use_image_pin:
                    return area
    
    return None

def get_sdneditor(context: bpy.types.Context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'NODE_EDITOR' and area.spaces[0].tree_type == TREE_TYPE and area.spaces[0].edit_tree:
                return area
    
    return None

class SDNode_To_Image(bpy.types.Operator):
    bl_idname = "sdn.sdn_to_image"
    bl_label = "ComfyUI node to Image Editor"
    bl_description = "Open the selected Save/Preview/Input Image node's image in an Image Editor"
    bl_translation_context = ctxt

    @classmethod
    def poll(cls, context: Context):
        return (context.space_data.type == 'IMAGE_EDITOR' and context.space_data.image and get_sdneditor(context)) or \
               (context.space_data.type == 'NODE_EDITOR' and context.space_data.tree_type == TREE_TYPE and get_imeditor(context))

    def execute(self, context):

        node = None
        ime_area = None

        if context.area.type == 'NODE_EDITOR':
            node = context.active_node
            ime_area = get_imeditor(context, False)
                    
        if context.area.type == 'IMAGE_EDITOR':
            ime_area = context.area
            sdn_area = get_sdneditor(context)
            if not sdn_area:
                self.report({'ERROR'}, "No ComfyUI Node Editor found!")
            node = sdn_area.spaces[0].node_tree.nodes.active

        if not node:
            self.report({'ERROR'}, "No active ComfyUI node!")
            return {'CANCELLED'}
        if not ime_area:
            self.report({'ERROR'}, "No Image Editor with an open unpinned image found!")
            return {'CANCELLED'}

        image = sdn_get_image(node)
        if not image:
            self.report({'ERROR'}, "Could not retrieve node image!")
            return {'CANCELLED'}

        ime_area.spaces[0].image = image
        ime_area.spaces[0].image.alpha_mode = 'CHANNEL_PACKED'

        return {'FINISHED'}
    
MODIFIED_IMAGE_SUFFIX = '_m'

class Image_To_SDNode(bpy.types.Operator):
    bl_idname = "sdn.image_to_sdn"
    bl_label = "Image Editor to ComfyUI node"
    bl_description = "Move the current image to a ComfyUI Node Editor node"
    bl_translation_context = ctxt

    force_centered: bpy.props.BoolProperty(name="Force Centered", description="If creating a new node, put it in the centre of the editor",
                                           translation_context=ctxt, default=False)

    @classmethod
    def poll(cls, context: Context):

        return (context.space_data.type == 'IMAGE_EDITOR' and context.space_data.image and get_sdneditor(context)) or \
               (context.space_data.type == 'NODE_EDITOR' and context.space_data.tree_type == TREE_TYPE and get_imeditor(context, True))
    
    def execute(self, context):
        sdn_area = None
        ime_area = None
        image = None
        new_node_loc = None

        if context.area.type == 'IMAGE_EDITOR':
            ime_area = context.area
            image = context.space_data.image
            sdn_area = get_sdneditor(context)
            
            if not sdn_area:
                self.report({'ERROR'}, "No ComfyUI Node Editor found!")
                return {'CANCELLED'}
            
            new_node_loc = sdn_area.regions[3].view2d.region_to_view(sdn_area.x + sdn_area.width / 2.0, sdn_area.y + sdn_area.height / 2.0)
            
        if context.area.type == 'NODE_EDITOR':
            sdn_area = context.area
            ime_area = get_imeditor(context, True)
            image = ime_area.spaces[0].image

            if not ime_area:
                self.report({'ERROR'}, "No Image Editor with an open image found!")
                return {'CANCELLED'}
            
            if not self.force_centered:
                new_node_loc = sdn_area.spaces[0].cursor_location
            else:
                new_node_loc = sdn_area.regions[3].view2d.region_to_view(sdn_area.x + sdn_area.width / 2.0, sdn_area.y + sdn_area.height / 2.0)

        if image.is_dirty:
            image.file_format = 'PNG'
            if image.alpha_mode != 'CHANNEL_PACKED':
                self.report({'WARNING'}, "The image is not using channel packed alpha. If you have painted a mask, the color underneath is black!")
            
            if image.source in ['VIEWER', 'GENERATED']: # viewer = render result
                filename = f"render_{uuid.uuid4()}"
                newpath = f"/tmp/{filename}.png"
                image.alpha_mode = 'CHANNEL_PACKED'
                image.save_render(filepath=newpath, scene=context.scene)
                newim = bpy.data.images.new(image.name + MODIFIED_IMAGE_SUFFIX, 32, 32, alpha=True)
                newim.source = 'FILE'
                newim.filepath = newpath
                ime_area.spaces[0].image = newim
            else:
                extensionless = image.filepath_raw[:image.filepath_raw.rfind(".")]
                if not extensionless.endswith(MODIFIED_IMAGE_SUFFIX):
                    newpath = extensionless + MODIFIED_IMAGE_SUFFIX + ".png"
                    image.save_render(filepath=newpath, scene=context.scene) # save_render is needed to properly save channel packed images
                    image.filepath = newpath
                    image.name = image.name 
                else:
                    image.save()
                

        active = sdn_area.spaces[0].node_tree.nodes.active
        if active and active.bl_idname == '输入图像' and active.select: # "Input Image" Blender-side node
            active.image = image.filepath_raw
        else:
            new_node = sdn_area.spaces[0].node_tree.nodes.new('输入图像')
            new_node.location = new_node_loc
            new_node.image = image.filepath_raw
            for n in sdn_area.spaces[0].node_tree.nodes:
                n.select = False
            new_node.select = True
            sdn_area.spaces[0].node_tree.nodes.active = new_node

        return {'FINISHED'}

@bpy.app.handlers.persistent
def clear(_):
    Ops.is_advanced_enable = False


bpy.app.handlers.load_pre.append(clear)
