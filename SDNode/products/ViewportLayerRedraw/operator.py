import bpy
import json
from pathlib import Path
from bpy_extras import view3d_utils
from bpy_extras.io_utils import ImportHelper
from ...tree import CFNodeTree, TREE_TYPE
from ....timer import Timer


class RunRedraw(bpy.types.Operator):
    bl_idname = "sdn.viewport_layer_run_redraw"
    bl_label = "Run Redraw"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        prop = scene.sdn_viewport_layer_redraw
        img = prop.get_active_image()
        if not img:
            return {"CANCELLED"}
        print("重绘: ", img)
        workflow = self.load_workflow()
        sdn_tree = self.get_sdn_tree()
        sdn_tree.load_json(workflow)

        def run(sdn_tree: CFNodeTree):
            input_image = sdn_tree.nodes["InputImage"]
            input_image.mode = "输入"
            input_image.input_type = "IMAGE"
            input_image.inner_image = img

            save_image = sdn_tree.nodes["SaveImage"]
            save_image.mode = "ToImage"
            save_image.image = img

            neg_prompt = sdn_tree.nodes["NegPrompt"]
            pos_prompt = sdn_tree.nodes["PosPrompt"]
            pos_prompt.text = prop.prompt
            sdn_tree.execute()

        Timer.put((run, sdn_tree))
        return {"FINISHED"}

    def load_workflow(self) -> dict:
        return json.loads(Path.read_text(Path(__file__).parent / "workflow/redraw.json"))

    def get_sdn_tree(self) -> CFNodeTree:
        return bpy.data.node_groups.new(name="Viewport_Layer_Redraw", type=TREE_TYPE)


class CFNodeImageImporter(bpy.types.Operator, ImportHelper):
    bl_idname = "sdn.cfnode_image_importer"
    bl_label = "Import Image To ComfyUI Node Image"

    filter_glob: bpy.props.StringProperty(default="*.png;*.jpg;*.jpeg;*.bmp;*.tiff;", options={"HIDDEN"})
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    tree_name: bpy.props.StringProperty(default="Viewport_Layer_Redraw")
    node_name: bpy.props.StringProperty(default="Image")
    prop_name: bpy.props.StringProperty(default="image")

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        bpy.context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        img_path = Path(self.filepath).as_posix()
        sdn_tree = bpy.data.node_groups.get(self.tree_name)
        if not sdn_tree:
            return {"CANCELLED"}
        img_node = sdn_tree.nodes.get(self.node_name)
        if not img_node:
            return {"CANCELLED"}
        setattr(img_node, self.prop_name, img_path)
        return {"FINISHED"}


class CFNodeCanvasPicker(bpy.types.Operator):
    bl_idname = "sdn.cfnode_canvas_picker"
    bl_label = "Render Canvas To ComfyUI Node Image"
    tree_name: bpy.props.StringProperty(default="Viewport_Layer_Redraw")
    node_name: bpy.props.StringProperty(default="Image")
    prop_name: bpy.props.StringProperty(default="image")

    def invoke(self, context, event):
        # img_path = Path(self.filepath).as_posix()
        # sdn_tree = bpy.data.node_groups.get(self.tree_name)
        # if not sdn_tree:
        #     return {"CANCELLED"}
        # img_node = sdn_tree.nodes.get(self.node_name)
        # if not img_node:
        #     return {"CANCELLED"}
        # setattr(img_node, self.prop_name, img_path)
        bpy.context.window.cursor_modal_set("EYEDROPPER")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            # 射线检测
            region = context.region
            rv3d = context.region_data
            coord = event.mouse_region_x, event.mouse_region_y

            view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
            ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
            ray_target = ray_origin + view_vector * 10000

            success, location, normal, index, object, matrix = context.scene.ray_cast(context.view_layer.depsgraph, ray_origin, ray_target)

            bpy.context.window.cursor_modal_restore()
            if success and object:
                print("选中物体: ", object)
                return {"FINISHED"}
            return {"CANCELLED"}
        elif event.type in {"RIGHTMOUSE", "ESC"}:
            bpy.context.window.cursor_modal_restore()
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}


clss = [
    RunRedraw,
    CFNodeImageImporter,
    CFNodeCanvasPicker,
]

reg, unreg = bpy.utils.register_classes_factory(clss)


def register():
    reg()


def unregister():
    unreg()
