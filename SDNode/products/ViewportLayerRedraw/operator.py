import bpy
import json
from pathlib import Path
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


clss = [
    RunRedraw,
]

reg, unreg = bpy.utils.register_classes_factory(clss)


def register():
    reg()


def unregister():
    unreg()
