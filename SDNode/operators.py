import bpy
import tempfile
import json
import time
from hashlib import md5
from pathlib import Path

from bpy.types import Context, Event
from .tree import CFNodeTree, TREE_TYPE
from ..translations import ctxt
from ..utils import Timer, _T, get_ai_mat_tree, set_ai_mat_tree


class AIMatSolutionLoad(bpy.types.Operator):
    bl_idname = "sdn.ai_mat_sol_load"
    bl_label = "AI Mat Solution Load"
    bl_description = "Load AI Mat Solution"
    bl_translation_context = ctxt
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.object and context.object.type == 'MESH'

    def get_resolution(self):
        size = bpy.context.scene.sdn.ai_mat_tex_size
        return size, size

    def draw(self, context):
        layout = self.layout
        if "AI_Mat_Gen_Ori" in bpy.context.object:
            layout.label(text="AI Mat already exists, Overwrite?")

    def invoke(self, context: Context, event: Event):
        if "AI_Mat_Gen_Ori" in bpy.context.object:
            wm = context.window_manager
            return wm.invoke_props_dialog(self, width=200)
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        workflow = self.read_workflow()
        ob = self.prepare_ob()
        self.prepare_scene()
        cam = self.prepare_cam(ob)
        maps = {
            "COLOR": "",
            "DEPTH": "",
            "NORMAL": "",
        }
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        for map_type in maps:
            if f"{{{map_type}}}" not in workflow and f"({map_type})" not in workflow:
                continue
            obj_name = bpy.path.clean_name(ob.name)
            obj_name += md5(ob.name.encode()).hexdigest()[:5]
            result = self.render_map(ob, f"_gen_{obj_name}_{map_type}.png", map_type)
            if not result:
                continue
            maps[map_type] = result
        if bpy.context.scene.sdn.clear_material_slots:
            ob.data.materials.clear()
        self.project_uv(ob)
        self.remove_cam(cam)
        self.prepare_combine(ob)
        mat = self.prepare_project_mat(ob)
        # read workflow
        # workflow = workflow.replace("{prompt}", "Stainless steel chest armor")
        # for map_type in maps:
        #     if not maps[map_type]:
        #         continue
        #     workflow = workflow.replace(f"{{{map_type}}}", maps[map_type])
        workflow = workflow.replace("\"{w}\"", str(self.get_resolution()[0]))
        workflow = workflow.replace("\"{h}\"", str(self.get_resolution()[1]))
        workflow = json.loads(workflow)
        node_tree = self.get_sdn_tree()
        node_tree.load_json(workflow)
        node_tree.name += "_" + ob.name
        # replace edit_tree
        for area in bpy.context.screen.areas:
            for space in area.spaces:
                if space.type != "NODE_EDITOR" or space.tree_type != TREE_TYPE:
                    continue
                space.node_tree = node_tree

        def prepare(ob: bpy.types.Object, node_tree: CFNodeTree):
            # 替换图片
            for node in node_tree.nodes:
                if not node.label:
                    continue
                if node.label[1:-1] in maps:
                    node.image = maps[node.label[1:-1]]
                    node.mode = "输入"

            def find_tex_recursive(tree: bpy.types.ShaderNodeTree, label: str = "") -> bpy.types.ShaderNodeTexImage:
                """
                    递归查找带有label的Tex节点, 如果没有则返回第一个tex节点, 如果都没有则返回None
                """
                if not tree:
                    return None
                tex = None  # 普通tex节点
                tex_recursive = None  # 递归查找结果
                tex_label = None  # 带标签的tex节点
                for node in tree.nodes:
                    if node.type == "TEX_IMAGE":
                        tex = node
                        if node.label == label:
                            tex_label = node
                    if node.type == "GROUP":
                        tex_recursive = tex_recursive or find_tex_recursive(node.node_tree, label)
                return tex_label or tex_recursive or tex
            tex_node = find_tex_recursive(mat.node_tree, "GenTex")
            if "ToMatImage" in node_tree.nodes:
                to_mat_img_node = node_tree.nodes["ToMatImage"]
                to_mat_img_node.mode = "ToImage"
                to_mat_img_node.image = tex_node.image if tex_node else None
            if tex_node:
                bpy.context.object["AI_Mat_Gen_Tex"] = tex_node.image
            for node in node_tree.nodes:
                if hasattr(node, "exe_rand"):
                    node.exe_rand = True

        Timer.put((prepare, ob, node_tree))
        set_ai_mat_tree(bpy.context.object, node_tree)
        return {"FINISHED"}

    def get_solution_path(self):
        return Path(bpy.context.scene.sdn.ai_gen_solution)

    def read_workflow(self):
        wk_path = self.get_solution_path().with_suffix(".json")
        if not wk_path.exists():
            wk_path = wk_path.parent.joinpath("_default.json")
        with open(wk_path) as f:
            return f.read()
        return "{}"

    def get_sdn_tree(self) -> CFNodeTree:
        return bpy.data.node_groups.new(name="AI_Mat_Gen", type=TREE_TYPE)

    def prepare_ob(self):
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        ori_ob = bpy.context.object
        if "AI_Mat_Gen_Ori" in ori_ob:
            bpy.ops.object.convert(target="MESH")
            ob = ori_ob
        else:
            for user_col in ori_ob.users_collection[:]:
                user_col.objects.unlink(ori_ob)
            if _T("Backups") not in bpy.data.collections:
                _col = bpy.data.collections.new(name=_T("Backups"))
                bpy.context.scene.collection.children.link(_col)
                _col.hide_render = True
                _col.hide_viewport = True
            back_col = bpy.data.collections.get(_T("Backups"))
            back_col.objects.link(ori_ob)
            old_name = ori_ob.name
            ob = ori_ob.copy()
            ob.data = ob.data.copy()
            ob["AI_Mat_Gen_Ori"] = ori_ob
            bpy.ops.object.select_all(action='DESELECT')
            bpy.context.scene.collection.objects.link(ob)
            bpy.context.view_layer.objects.active = ob
            ob.name = old_name + "_Copy"
            ob.select_set(state=True)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        if "Stack" not in bpy.data.node_groups:
            gn_path = self.get_solution_path().as_posix()
            with bpy.data.libraries.load(gn_path) as (df, dt):
                dt.node_groups = ["Stack"]
        ng = bpy.data.node_groups.get("Stack")
        mod = ob.modifiers.new(name='.Stack', type='NODES')
        mod.node_group = ng
        return ob

    def prepare_scene(self) -> bpy.types.Scene:
        scene = bpy.context.scene
        scene.cycles.samples = 16
        scene.render.film_transparent = True
        scene.render.resolution_x = self.get_resolution()[0]
        scene.render.resolution_y = self.get_resolution()[1]
        scene.use_nodes = True
        return scene

    def prepare_mat_norm(self, obj: bpy.types.Object):
        if "Normal" not in bpy.data.materials:
            gn_path = self.get_solution_path().as_posix()
            with bpy.data.libraries.load(gn_path) as (df, dt):
                dt.materials = ["Normal"]
        obj.active_material = bpy.data.materials["Normal"]
        return obj.active_material

    def prepare_mat_internal(self, obj: bpy.types.Object):
        if bpy.context.scene.sdn.clear_material_slots:
            obj.data.materials.clear()
        return obj.active_material

    def prepare_cam(self, obj: bpy.types.Object):
        from mathutils import Vector
        import numpy as np

        bpy.ops.object.camera_add()
        cam = bpy.context.object
        cam.name = "MapRenderCam"
        """
        1 -- 5
        |    |
        0 -- 4
        """
        sce = bpy.context.scene
        sce.camera = cam
        eobj = obj.evaluated_get(bpy.context.view_layer.depsgraph)

        points = np.array([Vector(corner) for corner in eobj.bound_box])
        center = Vector(points.mean(axis=0))
        size = max(points.max(axis=0) - points.min(axis=0)) * 1.5
        cam.location = center + Vector((0, -size, 0))
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = size
        cam.rotation_euler = 1.570796, 0, 0
        bpy.context.view_layer.objects.active = obj
        obj.select_set(state=True)
        bpy.ops.view3d.camera_to_view_selected()
        cam.location.xz = max(cam.location.xz), max(cam.location.xz)
        return cam

    def prepare_compositor_for_depth(self):
        bpy.context.scene.use_nodes = True
        tree = bpy.context.scene.node_tree
        nodes = tree.nodes
        nodes.clear()
        # Add required nodes
        render_layers_node = nodes.new(type='CompositorNodeRLayers')
        render_layers_node.location = (0, 0)
        normalize_node = nodes.new(type='CompositorNodeNormalize')
        normalize_node.location = (200, 0)
        alpha_math_node = nodes.new(type='CompositorNodeMath')
        alpha_math_node.location = (400, 0)
        alpha_math_node.operation = 'SUBTRACT'
        composite_node = nodes.new(type='CompositorNodeComposite')
        composite_node.location = (600, 0)
        # Link nodes
        tree.links.new(render_layers_node.outputs['Depth'], normalize_node.inputs[0])
        tree.links.new(normalize_node.outputs[0], alpha_math_node.inputs[1])  # Connect Depth output to input 1 of SUBTRACT node
        tree.links.new(render_layers_node.outputs['Alpha'], alpha_math_node.inputs[0])  # Connect Alpha output to input 0 of SUBTRACT node
        tree.links.new(alpha_math_node.outputs[0], composite_node.inputs[0])  # Connect the output of the SUBTRACT node to the Composite node

    def create_img_node(self, name, res, mat: bpy.types.Material):
        img: bpy.types.Image = bpy.data.images.new(name=name,
                                                   width=res[0],
                                                   height=res[1],
                                                   alpha=True)
        img_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        img_node.image = img
        img_node.select = True
        mat.node_tree.nodes.active = img_node
        return img_node

    def render_map(self, ob: bpy.types.Object, name, map_type):
        if map_type == "DEPTH":
            return self.render_depth(ob, name)
        if map_type == "NORMAL":
            return self.render_normal(ob, name)
        if map_type == "COLOR":
            return self.render_color(ob, name)
        return ""

    def render_depth_1(self, ob: bpy.types.Object, name: str):
        tempdir = tempfile.gettempdir()
        final_path = Path(tempdir, name)
        final_path.unlink(missing_ok=True)
        self.prepare_compositor_for_depth()
        bpy.context.scene.render.filepath = final_path.as_posix()
        bpy.ops.render.render(write_still=True)
        return final_path.as_posix()

    def render_depth(self, ob: bpy.types.Object, name: str):
        tempdir = tempfile.gettempdir()
        final_path = Path(tempdir, name)
        final_path.unlink(missing_ok=True)
        sce = bpy.context.scene.copy()
        view_layer = sce.view_layers.new("_AI_Mat_View_Layer_Temp")
        view_layer.use_pass_z = True
        # 记录渲染状态, 随后恢复
        obj_render_status: dict[bpy.types.Object, bool] = {}
        for obj in bpy.context.scene.objects:
            if obj == ob:
                continue
            if obj.type in {"LIGHT", "CAMERA", "LIGHT_PROBE"}:
                continue
            obj_render_status[obj] = obj.hide_render
            obj.hide_render = True
        sce.use_nodes = True
        # ----------准备渲染合成----------
        tree = sce.node_tree
        nodes = tree.nodes
        nodes.clear()
        # 创建合成器节点
        render_layers_node = nodes.new(type='CompositorNodeRLayers')
        render_layers_node.location = (0, 0)
        render_layers_node.scene = sce
        render_layers_node.layer = view_layer.name
        composite_node = nodes.new(type='CompositorNodeComposite')
        composite_node.location = (600, 0)
        alpha_math_node = nodes.new(type='CompositorNodeMath')
        alpha_math_node.location = (400, 0)
        alpha_math_node.operation = 'SUBTRACT'
        normalize_node = nodes.new(type='CompositorNodeNormalize')
        normalize_node.location = (200, 0)
        # 链接节点
        tree.links.new(render_layers_node.outputs["Depth"], normalize_node.inputs[0])
        tree.links.new(normalize_node.outputs[0], alpha_math_node.inputs[1])
        tree.links.new(alpha_math_node.outputs[0], composite_node.inputs[0])
        tree.links.new(render_layers_node.outputs['Alpha'], alpha_math_node.inputs[0])
        # 设置渲染参数
        sce.render.engine = "CYCLES"
        sce.render.image_settings.file_format = "PNG"
        sce.render.image_settings.color_mode = "RGB"
        sce.render.image_settings.color_depth = "8"
        sce.display_settings.display_device = "sRGB"
        sce.view_settings.view_transform = "Standard"
        sce.cycles.samples = 16
        sce.render.filepath = final_path.as_posix()
        sce.world = None
        bpy.ops.render.render(scene=sce.name, layer=view_layer.name, write_still=True)
        sce.view_layers.remove(view_layer)
        bpy.data.scenes.remove(sce)
        # 恢复渲染状态
        for obj, status in obj_render_status.items():
            obj.hide_render = status
        return final_path.as_posix()

    def render_normal(self, ob: bpy.types.Object, name: str):
        self.prepare_mat_norm(ob)
        bpy.context.scene.use_nodes = False
        tempdir = tempfile.gettempdir()
        final_path = Path(tempdir, name)
        final_path.unlink(missing_ok=True)
        sce = bpy.context.scene.copy()
        view_layer = sce.view_layers.new("_AI_Mat_View_Layer_Temp")
        view_layer.use_pass_normal = True
        # 记录渲染状态, 随后恢复
        obj_render_status: dict[bpy.types.Object, bool] = {}
        for obj in bpy.context.scene.objects:
            if obj == ob:
                continue
            if obj.type in {"LIGHT", "CAMERA", "LIGHT_PROBE"}:
                continue
            obj_render_status[obj] = obj.hide_render
            obj.hide_render = True

        # 准备场景设置
        sce.render.engine = 'CYCLES'
        sce.render.image_settings.file_format = 'PNG'
        sce.render.image_settings.color_mode = 'RGB'
        sce.render.image_settings.color_depth = '8'
        sce.display_settings.display_device = 'sRGB'
        sce.view_settings.view_transform = 'Standard'
        sce.cycles.samples = 16
        sce.render.filepath = final_path.as_posix()
        world = bpy.data.worlds.new("._")
        sce.world = world
        world.use_nodes = True
        for node in filter(lambda n: n.type == "BACKGROUND", world.node_tree.nodes):
            node.inputs[0].default_value = (0.5, 0.5, 1.0, 1.0)

        bpy.ops.render.render(scene=sce.name, layer=view_layer.name, write_still=True)
        sce.view_layers.remove(view_layer)
        bpy.data.scenes.remove(sce)
        bpy.data.worlds.remove(world)
        # 恢复渲染状态
        for obj, status in obj_render_status.items():
            obj.hide_render = status
        return final_path.as_posix()

    def render_color(self, ob: bpy.types.Object, name: str):
        tempdir = tempfile.gettempdir()
        final_path = Path(tempdir, name)
        final_path.unlink(missing_ok=True)

        sce = bpy.context.scene.copy()
        # 记录渲染状态, 随后恢复
        obj_render_status: dict[bpy.types.Object, bool] = {}
        for obj in bpy.context.scene.objects:
            if obj == ob:
                continue
            if obj.type in {"LIGHT", "CAMERA", "LIGHT_PROBE"}:
                continue
            obj_render_status[obj] = obj.hide_render
            obj.hide_render = True

        sce.render.engine = "CYCLES"
        sce.render.image_settings.file_format = "PNG"
        sce.render.image_settings.color_mode = "RGB"
        sce.render.image_settings.color_depth = "8"
        sce.display_settings.display_device = "sRGB"
        sce.view_settings.view_transform = "Standard"
        sce.cycles.samples = 16
        sce.render.filepath = final_path.as_posix()
        bpy.ops.render.render(scene=sce.name, write_still=True)
        bpy.data.scenes.remove(sce)

        # 恢复渲染状态
        for obj, status in obj_render_status.items():
            obj.hide_render = status
        return final_path.as_posix()

    def project_uv(self, ob: bpy.types.Object):
        # UV投射
        uv_layer_name = "Projected_UV"
        if uv_layer_name not in ob.data.uv_layers:
            ob.data.uv_layers.new(name=uv_layer_name)
        if ".Stack" in ob.modifiers:
            mod = ob.modifiers[".Stack"]
            mod.show_on_cage = False
            mod.show_in_editmode = False
            mod.show_viewport = False
            mod.show_render = False
        # 投射修改器
        mod = ob.modifiers.new(name=".UV_PROJECT", type='UV_PROJECT')
        mod.uv_layer = uv_layer_name
        mod.aspect_x = bpy.context.scene.render.resolution_x
        mod.aspect_y = bpy.context.scene.render.resolution_y
        mod.projectors[0].object = bpy.context.scene.camera
        bpy.ops.object.modifier_apply(modifier=mod.name)

    def remove_cam(self, cam: bpy.types.Object):
        cam_data = cam.data
        bpy.data.objects.remove(cam)
        bpy.data.cameras.remove(cam_data)

    def prepare_combine(self, ob: bpy.types.Object):
        if "Project" not in bpy.data.node_groups:
            gn_path = self.get_solution_path().as_posix()
            with bpy.data.libraries.load(gn_path) as (df, dt):
                dt.node_groups = ["Project"]
        ng = bpy.data.node_groups.get("Project")
        mod = ob.modifiers.new(name=".Project", type='NODES', )
        mod.node_group = ng

    def prepare_project_mat(self, ob: bpy.types.Object) -> bpy.types.Material:
        """
            每次生成新的材质
        """
        gn_path = self.get_solution_path().as_posix()
        old_mats = set(ob.data.materials)
        with bpy.data.libraries.load(gn_path) as (df, dt):
            dt.materials = ["Project"]
        new_mats = list(set(bpy.data.materials) - old_mats)
        for new_mat in new_mats:
            if new_mat.name == "Project":
                new_mat.name += "_" + ob.name
                ob.active_material = new_mat
                break
        return new_mat


class AIMatSolutionRun(bpy.types.Operator):
    bl_idname = "sdn.ai_mat_sol_run"
    bl_label = "Run AI Mat Solution"
    bl_description = "Use depth and normal map to Gen Mesh Mat"
    bl_translation_context = ctxt
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return get_ai_mat_tree(context.object)

    def execute(self, context):
        tree: CFNodeTree = get_ai_mat_tree(context.object)
        if not tree:
            self.report({"ERROR"}, "Can't find ComfyUI Node Tree")
            return {"CANCELLED"}
        tree.execute()
        return {"FINISHED"}


class AIMatSolutionSave(bpy.types.Operator):
    bl_idname = "sdn.ai_mat_sol_save"
    bl_label = "Save AI Mat Solution"
    bl_translation_context = ctxt

    name: bpy.props.StringProperty(name="Name", default="Solution")

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == "MESH"

    def invoke(self, context: Context, event: Event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=200)

    def execute(self, context: Context):
        if not bpy.context.object.active_material:
            self.report({"ERROR"}, "No active material")
            return {"CANCELLED"}
        # 只需要添加 工作流 和 最终渲染材质(需要借助几何属性)
        # 几何节点: Stack + Project
        # 材质: Normal + Depth + Project
        find_tree: CFNodeTree = None
        for area in bpy.context.screen.areas:
            for space in area.spaces:
                if space.type != "NODE_EDITOR" or space.tree_type != TREE_TYPE:
                    continue
                find_tree = space.node_tree
                break
        if not find_tree:
            self.report({"ERROR"}, "Can't find CFNodeTree")
            return {"CANCELLED"}
        try:
            workflow = find_tree.save_json()
        except Exception as e:
            self.report({"ERROR"}, str(e.args))
            return {"FINISHED"}
        # 老版本
        ori_stack_ng = bpy.data.node_groups.get("Stack")
        ori_proj_ng = bpy.data.node_groups.get("Project")
        ori_norm_mtl = bpy.data.materials.get("Normal")
        ori_proj_mtl = bpy.data.materials.get("Project")
        if ori_stack_ng:
            ori_stack_ng.name = "." + ori_stack_ng.name
        if ori_proj_ng:
            ori_proj_ng.name = "." + ori_proj_ng.name
        if ori_norm_mtl:
            ori_norm_mtl.name = "." + ori_norm_mtl.name
        if ori_proj_mtl:
            ori_proj_mtl.name = "." + ori_proj_mtl.name
        # 提前准备 Stack Project 几何节点 和 Normal 材质
        gn_path = self.get_solution_path().parent.joinpath("00-Default.blend")
        with bpy.data.libraries.load(gn_path.as_posix()) as (df, dt):
            dt.node_groups = ["Stack", "Project"]
            dt.materials = ["Normal"]
        wk_data = json.dumps(workflow, ensure_ascii=False, indent=4)
        save_path = self.get_save_path()
        stack_ng = bpy.data.node_groups.get("Stack")
        proj_ng = bpy.data.node_groups.get("Project")
        norm_mtl = bpy.data.materials.get("Normal")
        proj_mtl = bpy.context.object.active_material.copy()  # 目的材质
        proj_mtl.name = "Project"
        save_data = {stack_ng, proj_ng, norm_mtl, proj_mtl}
        # 存储 blend 和 json
        bpy.data.libraries.write(save_path.with_suffix(".blend").as_posix(), save_data)
        save_path.write_text(wk_data)
        bpy.data.node_groups.remove(stack_ng)
        bpy.data.node_groups.remove(proj_ng)
        bpy.data.materials.remove(norm_mtl)
        bpy.data.materials.remove(proj_mtl)
        # 恢复老版本名称
        if ori_stack_ng:
            ori_stack_ng.name = ori_stack_ng.name[1:]
        if ori_proj_ng:
            ori_proj_ng.name = ori_proj_ng.name[1:]
        if ori_norm_mtl:
            ori_norm_mtl.name = ori_norm_mtl.name[1:]
        if ori_proj_mtl:
            ori_proj_mtl.name = ori_proj_mtl.name[1:]
        return {"FINISHED"}

    def draw(self, context: Context):
        layout = self.layout
        col = layout.column()
        save_path = self.get_save_path()
        col.alert = save_path.exists()
        col.prop(self, "name")
        if col.alert:
            layout.label(text="AI Mat already exists, Overwrite?", icon="ERROR")
        else:
            layout.label(text="")

    def get_solution_path(self):
        return Path(bpy.context.scene.sdn.ai_gen_solution)

    def get_save_path(self) -> Path:
        return self.get_solution_path().parent / (self.name + ".json")


class AIMatSolutionDel(bpy.types.Operator):
    bl_idname = "sdn.ai_mat_sol_del"
    bl_label = "Delete AI Mat Solution"
    bl_translation_context = ctxt

    def execute(self, context: Context):
        res_path = self.get_solution_path()
        res_path.unlink(missing_ok=True)
        res_path.with_suffix(".blend").unlink(missing_ok=True)
        return {"FINISHED"}

    def get_solution_path(self):
        return Path(bpy.context.scene.sdn.ai_gen_solution)


class AIMatSolutionApply(bpy.types.Operator):
    bl_idname = "sdn.ai_mat_sol_apply"
    bl_label = "Apply"
    bl_translation_context = ctxt

    @classmethod
    def poll(cls, context):
        return get_ai_mat_tree(context.object)

    def execute(self, context: Context):
        if context.object.get("AI_Mat_Gen_Applied", None):
            self.report({"ERROR"}, "Already applied")
            return {"FINISHED"}
        try:
            # 新逻辑:
            # 1. 新建 BakeNodeTree 节点树
            self.tree = bpy.data.node_groups.new("AI_Mat_Gen_Bake_Tree_Temp", "BakeNodeTree")
            self.tree.is_running = True
            self.tree.initialize_ai()

            self.obj: bpy.types.Object = context.object
            self.ori: bpy.types.Object = self.obj.get("AI_Mat_Gen_Ori")

            self.tree.nodes["Mesh_Copy"].mesh_configs[0].target = self.obj
            self.tree.nodes["Pass"].bake_passes = {bpy.context.scene.sdn.apply_bake_pass, }
            self.tree.execute()
            self.obj["AI_Mat_Gen_Applied"] = True
            context.window_manager.modal_handler_add(self)

            # 2. 将新建的节点树中的 网格设置为当前的 Copy物体
            # 4. 执行 烘焙节点树
            # 5. 执行完成后删除Copy物体, 将原物体恢复
            return {"RUNNING_MODAL"}
        except Exception:
            import traceback
            traceback.print_exc()
            # 旧逻辑
            bpy.ops.object.convert(target="MESH")
        return {"FINISHED"}

    def modal(self, context: Context, event: bpy.types.Event):
        if self.tree.is_running:
            return {"PASS_THROUGH"}
        # tree 运行结束, 删除 Copy物体, 恢复原物体
        od = self.obj.data
        bpy.data.objects.remove(self.obj)
        bpy.data.meshes.remove(od)
        for col in self.ori.users_collection:
            col.objects.unlink(self.ori)
        bpy.context.scene.collection.objects.link(self.ori)
        bpy.data.node_groups.remove(self.tree)
        self.ori.select_set(True)
        bpy.context.view_layer.objects.active = self.ori
        mod = self.ori.modifiers.get(f"AI_Tex_Preview_Mod_{self.ori.name}", None)
        if not mod:
            return {"FINISHED"}
        # self.ori.data.materials.clear()
        # # 将该修改器应用
        # with bpy.context.temp_override(object=self.ori):
        #     bpy.ops.object.modifier_apply(modifier=mod.name)
        return {"FINISHED"}


class AIMatSolutionRestore(bpy.types.Operator):
    bl_idname = "sdn.ai_mat_sol_restore"
    bl_label = "Restore"
    bl_translation_context = ctxt

    @classmethod
    def poll(cls, context):
        return context.object and "AI_Mat_Gen_Ori" in context.object

    def execute(self, context: Context):
        """
            还原: 将Copy物体删除, 将原物体恢复
        """
        ori: bpy.types.Object = context.object.get("AI_Mat_Gen_Ori")
        if not ori:
            return {"CANCELLED"}
        od = context.object.data
        bpy.data.objects.remove(context.object)
        bpy.data.meshes.remove(od)
        for col in ori.users_collection:
            col.objects.unlink(ori)
        bpy.context.scene.collection.objects.link(ori)
        return {"FINISHED"}


clss = (
    AIMatSolutionLoad,
    AIMatSolutionRun,
    AIMatSolutionSave,
    AIMatSolutionDel,
    AIMatSolutionApply,
    AIMatSolutionRestore,
)

ops_register, ops_unregister = bpy.utils.register_classes_factory(clss)
