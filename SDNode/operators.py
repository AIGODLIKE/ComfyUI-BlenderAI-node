import bpy
import tempfile
import json
import time
from random import uniform
from hashlib import md5
from pathlib import Path
from mathutils import Vector
from bpy.types import Context, Event
from .tree import CFNodeTree, TREE_TYPE
from ..translations.translation import ctxt
from ..utils import Timer, _T, get_ai_mat_tree, set_ai_mat_tree, find_area_by_type, find_areas_of_type, find_region_by_type


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
        sce.render.image_settings.file_format = "PNG"
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
        sce.render.image_settings.file_format = "PNG"
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
        sce.render.image_settings.file_format = "PNG"
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


class PreviewImageInPlane(bpy.types.Operator):
    bl_idname = "sdn.prev_img_in_plane"
    bl_label = "PreviewImage"
    bl_translation_context = ctxt

    img_name: bpy.props.StringProperty(name="Image Name", default="PreviewImage")

    def execute(self, context):
        if not self.img_name or self.img_name not in bpy.data.images:
            self.report({"ERROR"}, "Image not found")
            return {"FINISHED"}
        cam = bpy.context.scene.camera
        # 1. 创建一个平面
        rot = Vector(cam.rotation_euler) + Vector((uniform(-1, 1), uniform(-1, 1), 0)) * 0.002
        bpy.ops.mesh.primitive_plane_add(size=2, calc_uvs=True, align="VIEW", location=cam.location, rotation=rot.to_tuple())
        obj = bpy.context.object
        local_translation = obj.matrix_world.to_3x3() @  Vector((0, 0, -4))
        obj.location += local_translation
        bpy.context.view_layer.objects.active.visible_shadow = False
        # 2. 赋予一个材质: 一张图像输入, 一个原理化, 一个材质输出, 图像的输出连接到原理化的自发光
        mtl = bpy.data.materials.new(name="PreviewImage")
        mtl.use_nodes = True
        obj.data.materials.append(mtl)
        obj.active_material = mtl
        nodes = mtl.node_tree.nodes
        nodes.clear()
        img_node = nodes.new("ShaderNodeTexImage")
        img_node.image = bpy.data.images.get(self.img_name)
        img_node.location = -300, 0
        principled_node = nodes.new("ShaderNodeBsdfPrincipled")
        principled_node.location = 0, 0
        principled_node.inputs["Roughness"].default_value = 1
        principled_node.inputs["Emission Strength"].default_value = 1
        output_node = nodes.new("ShaderNodeOutputMaterial")
        output_node.location = 300, 0
        mtl.node_tree.links.new(img_node.outputs["Color"], principled_node.inputs["Emission Color"])
        mtl.node_tree.links.new(img_node.outputs["Alpha"], principled_node.inputs["Alpha"])
        mtl.node_tree.links.new(img_node.outputs["Color"], principled_node.inputs["Base Color"])
        mtl.node_tree.links.new(principled_node.outputs[0], output_node.inputs[0])
        return {"FINISHED"}


class ImageAsPBRMat(bpy.types.Operator):
    bl_idname = "sdn.img_as_pbr_mat"
    bl_label = "PreviewImage"
    bl_translation_context = ctxt

    img_name: bpy.props.StringProperty(name="Image Name", default="PreviewImage")

    def create_mat(self):
        mtl = bpy.data.materials.new(name=f"PBRMat_{self.img_name}")
        mtl.use_nodes = True
        nodes = mtl.node_tree.nodes
        nodes.clear()
        texcoord_node = nodes.new("ShaderNodeTexCoord")
        mapping_node = nodes.new("ShaderNodeMapping")
        img_node = nodes.new("ShaderNodeTexImage")
        bump_node = nodes.new("ShaderNodeBump")
        principled_node = nodes.new("ShaderNodeBsdfPrincipled")
        output_node = nodes.new("ShaderNodeOutputMaterial")
        texcoord_node.location = -1200, 0
        mapping_node.location = -900, 0

        img_node.image = bpy.data.images.get(self.img_name)
        img_node.interpolation = "Cubic"
        img_node.location = -600, 0

        principled_node.location = 0, 0

        bump_node.inputs["Strength"].default_value = 0.1
        bump_node.location = -300, 0

        output_node.location = 300, 0

        mtl.node_tree.links.new(texcoord_node.outputs["UV"], mapping_node.inputs[0])
        mtl.node_tree.links.new(mapping_node.outputs[0], img_node.inputs[0])
        mtl.node_tree.links.new(img_node.outputs["Alpha"], principled_node.inputs["Alpha"])
        mtl.node_tree.links.new(img_node.outputs["Color"], bump_node.inputs["Height"])
        mtl.node_tree.links.new(img_node.outputs["Color"], principled_node.inputs["Base Color"])
        mtl.node_tree.links.new(bump_node.outputs[0], principled_node.inputs["Normal"])
        mtl.node_tree.links.new(principled_node.outputs[0], output_node.inputs[0])
        return mtl

    def execute(self, context):
        if not self.img_name or self.img_name not in bpy.data.images:
            self.report({"ERROR"}, "Image not found")
            return {"FINISHED"}
        obj = bpy.context.object
        mtl = self.create_mat()
        if bpy.context.mode == "OBJECT":
            obj.active_material = mtl
            obj.data.materials.clear()
        obj.data.materials.append(mtl)
        obj.active_material_index = len(obj.data.materials) - 1
        if bpy.context.mode == "EDIT_MESH":
            bpy.ops.object.material_slot_assign("INVOKE_DEFAULT")
        return {"FINISHED"}


class ImageProjectOnObject(bpy.types.Operator):
    bl_idname = "sdn.img_project_on_obj"
    bl_label = "Apply/Project this Image on active object"
    bl_description = "Projects/Applys this Image to the object. like painting it. IF Using in object mode = it will project the image through whole object (using UV project from view). IF Using in EDIT MODE = it will only paint the image to the visible mesh, remember to have not overlappen UVmap before when using in object mode.."
    bl_translation_context = ctxt

    bl_options = {"REGISTER", "UNDO"}

    img_name: bpy.props.StringProperty(name="Image Name", default="PreviewImage")
    
    _pass_args = {
        "active_uvmap_render_by_index": 0,
        "active_uvmap_name_from_index": "",
        "active_selected_uvmap_by_index": 0,
    }
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == "MESH" and context.object.mode in {"OBJECT", "EDIT"} and context.scene.camera

    def find_biggest_area_by_type(self, screen: bpy.types.Screen, area_type):
        areas = find_areas_of_type(screen, area_type)
        if not areas:
            return []
        max_area = (areas[0], areas[0].width * areas[0].height)
        for area in areas:
            if area.width * area.height > max_area[1]:
                max_area = (area, area.width * area.height)
        return max_area[0]

    def create_mtl_pbr(self, mtl_name, image) -> bpy.types.Material:
        mtl = bpy.data.materials.new(name=mtl_name)
        mtl.use_nodes = True
        nodes = mtl.node_tree.nodes
        nodes.clear()
        texcoord_node = nodes.new("ShaderNodeTexCoord")
        mapping_node = nodes.new("ShaderNodeMapping")
        img_node = nodes.new("ShaderNodeTexImage")
        bump_node = nodes.new("ShaderNodeBump")
        principled_node = nodes.new("ShaderNodeBsdfPrincipled")
        output_node = nodes.new("ShaderNodeOutputMaterial")
        texcoord_node.location = -1200, 0
        mapping_node.location = -900, 0

        img_node.image = image
        img_node.interpolation = "Cubic"
        img_node.location = -600, 0

        principled_node.location = 0, 0

        bump_node.inputs["Strength"].default_value = 0.1
        bump_node.location = -300, 0

        output_node.location = 300, 0

        mtl.node_tree.links.new(texcoord_node.outputs["UV"], mapping_node.inputs[0])
        mtl.node_tree.links.new(mapping_node.outputs[0], img_node.inputs[0])
        mtl.node_tree.links.new(img_node.outputs["Alpha"], principled_node.inputs["Alpha"])
        mtl.node_tree.links.new(img_node.outputs["Color"], bump_node.inputs["Height"])
        mtl.node_tree.links.new(img_node.outputs["Color"], principled_node.inputs["Base Color"])
        mtl.node_tree.links.new(bump_node.outputs[0], principled_node.inputs["Normal"])
        mtl.node_tree.links.new(principled_node.outputs[0], output_node.inputs[0])
        return mtl

    def ensure_uv(self, obj: bpy.types.Object):
        if "Comfy_Project_Through_UVMAP" not in obj.data.uv_layers:
            uv_layer = obj.data.uv_layers.new(name="Comfy_Project_Through_UVMAP")
            uv_layer.active_render = True
            uv_layer.active = True
            obj.data.uv_layers.active_index = len(obj.data.uv_layers) - 1
        uv_layer = obj.data.uv_layers[obj.data.uv_layers.active_index]
        return uv_layer

    def execute(self, context):
        self._pass_args.clear()
        act_obj = bpy.context.view_layer.objects.active
        if "OBJECT" == bpy.context.mode:
            active_uvmap_render_by_index = 0
            active_selected_uvmap_by_index = act_obj.data.uv_layers.active_index
            active_uvmap_name_from_index = ""
            for i, l in enumerate(act_obj.data.uv_layers):
                if not l.active_render:
                    continue
                active_uvmap_render_by_index = i
                active_uvmap_name_from_index = l.name
            self.ensure_uv(act_obj)
            w, h = bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y
            proj_img_name = f"Image_Name_from_Preview_Node_{hash(act_obj)}"
            bpy.ops.image.new(name=proj_img_name, width=w, height=h)
            proj_img = bpy.data.images[proj_img_name]
            proj_mtl = self.create_mtl_pbr(f"Material_Name_From_Project_Image_{hash(act_obj)}", proj_img)
            act_obj.data.materials.append(material=proj_mtl, )
            area = find_area_by_type(bpy.context.screen, 'VIEW_3D', 0)
            if not area:
                self.report({"ERROR"}, "No View3D Window Found!")
                return {"CANCELLED"}
            with bpy.context.temp_override(area=area, region=area.regions[0], ):
                bpy.ops.view3d.view_camera()
            bpy.ops.object.mode_set("INVOKE_DEFAULT", mode='EDIT')
            bpy.ops.mesh.select_all("INVOKE_DEFAULT", action='SELECT')
            window_region = find_region_by_type(area, "WINDOW")
            with bpy.context.temp_override(area=area, region=window_region, ):
                bpy.ops.uv.project_from_view("INVOKE_DEFAULT", )
            context.object.active_material_index = len(act_obj.material_slots)
            bpy.ops.object.material_slot_assign("INVOKE_DEFAULT", )
            bpy.ops.object.mode_set("INVOKE_DEFAULT", mode="TEXTURE_PAINT")
            bpy.ops.object.mode_set("INVOKE_DEFAULT", mode="OBJECT")
            bpy.ops.object.shade_flat("INVOKE_DEFAULT", )
            bpy.ops.paint.project_image(image=self.img_name)
            self._pass_args.update({
                "active_uvmap_render_by_index": active_uvmap_render_by_index,
                "active_uvmap_name_from_index": active_uvmap_name_from_index,
                "active_selected_uvmap_by_index": active_selected_uvmap_by_index,

            })
            with bpy.context.temp_override(area=area, region=area.regions[0]):
                bpy.ops.view3d.view_camera()
                bpy.ops.wm.call_menu(name=OkBakeMenu.bl_idname)
        if "EDIT_MESH" == bpy.context.mode:
            bpy.ops.object.mode_set("INVOKE_DEFAULT", mode="TEXTURE_PAINT")
            bpy.ops.object.mode_set("INVOKE_DEFAULT", mode="OBJECT")
            bpy.ops.object.shade_flat("INVOKE_DEFAULT", )
            bpy.ops.paint.project_image(image=self.img_name)
            bpy.ops.object.mode_set("INVOKE_DEFAULT", mode="EDIT")

        return {"FINISHED"}

    def invoke(self, context, event):

        return self.execute(context)


class ProjectThenBake(bpy.types.Operator):
    bl_idname = "sdn.proj_then_bake"
    bl_label = "OK BAKE"
    bl_translation_context = ctxt
    bl_description = "Will bake image to previous UV map that was as active render, if didnt had any UV map then it will create new one..."
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        old_engine = bpy.context.scene.render.engine
        act_obj = context.object
        if act_obj.data.uv_layers:
            active_uvmap_name_from_index = ImageProjectOnObject._pass_args["active_uvmap_name_from_index"]
            bpy.context.scene.render.engine = "CYCLES"
            active_uvmap_render_by_index = ImageProjectOnObject._pass_args["active_uvmap_render_by_index"]
            active_selected_uvmap_by_index = ImageProjectOnObject._pass_args["active_selected_uvmap_by_index"]
            bpy.ops.object.bake(
                type="DIFFUSE",
                pass_filter={"COLOR"},
                width=bpy.context.scene.render.resolution_x,
                height=bpy.context.scene.render.resolution_y,
                margin=16,
                margin_type="ADJACENT_FACES",
                use_selected_to_active=False,
                target="IMAGE_TEXTURES",
                save_mode="INTERNAL",
                use_clear=False,
                uv_layer=active_uvmap_name_from_index,
            )
            bpy.context.scene.render.engine = old_engine
            bpy.ops.mesh.uv_texture_remove("INVOKE_DEFAULT")
            for i, l in enumerate(act_obj.data.uv_layers):
                if (i == active_uvmap_render_by_index):
                    l.active_render = True
            bpy.context.active_object.data.uv_layers.active_index = active_selected_uvmap_by_index
        else:
            uv_layer = act_obj.data.uv_layers.new(name="Image_Name_from_Preview_Node")
            act_obj.data.uv_layers.active_index = 1
            bpy.ops.object.mode_set(mode="EDIT")
            area = find_area_by_type(bpy.context.screen, 'VIEW_3D', 0)
            with bpy.context.temp_override(area=area, region=area.regions[7], ):
                bpy.ops.uv.smart_project()
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.context.scene.render.engine = "CYCLES"
            bpy.ops.object.bake(
                type="DIFFUSE",
                pass_filter={"COLOR"},
                width=bpy.context.scene.render.resolution_x,
                height=bpy.context.scene.render.resolution_y,
                margin=16,
                margin_type="ADJACENT_FACES",
                use_selected_to_active=False,
                target="IMAGE_TEXTURES",
                save_mode="INTERNAL",
                use_clear=False,
                uv_layer=uv_layer.name,
            )
            bpy.context.scene.render.engine = old_engine
            act_obj.data.uv_layers[1].active_render = True
            act_obj.data.uv_layers.remove(layer=act_obj.data.uv_layers["Comfy_Project_Through_UVMAP"], )
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class OkBakeMenu(bpy.types.Menu):
    bl_idname = "SDN_MT_OKBAKE"
    bl_label = "Bake Image?"

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.column_flow(columns=2)
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator(ProjectThenBake.bl_idname, text="YES", icon_value=0, emboss=True, depress=False)


clss = (
    AIMatSolutionLoad,
    AIMatSolutionRun,
    AIMatSolutionSave,
    AIMatSolutionDel,
    AIMatSolutionApply,
    AIMatSolutionRestore,
    PreviewImageInPlane,
    ImageAsPBRMat,
    ImageProjectOnObject,
    ProjectThenBake,
    OkBakeMenu,
)

ops_register, ops_unregister = bpy.utils.register_classes_factory(clss)
