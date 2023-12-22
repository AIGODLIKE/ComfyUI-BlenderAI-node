import bpy
import time
from mathutils import Vector
from ..utils import _T
from .nodes import NodeBase


class SDNCustomGroup(bpy.types.NodeCustomGroup, NodeBase):
    bl_idname = 'SDNCustomGroup'
    bl_label = 'SDNCustomGroup'
    bl_icon = 'NODETREE'
    bl_description = 'SDNCustomGroup'

    class_type = 'SDNCustomGroup'

    def is_group(self) -> bool:
        return True

    def update(self):
        print("update group", self.name, time.time())
        if not self.node_tree:
            self.clear_sockets()
            return
        tree_inputs = list(self.node_tree.sockets('INPUT'))
        tree_outputs = list(self.node_tree.sockets('OUTPUT'))
        self.validate_sockets(self.inputs, tree_inputs)
        self.validate_sockets(self.outputs, tree_outputs)
        self.clear_unused_sockets()

    def validate_sockets(self, sts: bpy.types.NodeInputs, sfs: list[bpy.types.NodeSocket]):
        sfi = {s.identifier for s in sfs}
        sti = {s.identifier for s in sts}
        for st in list(sts):
            if st.identifier in sfi:
                continue
            sts.remove(st)
        # add new sockets
        for sf in sfs:
            if sf.identifier in sti:
                continue
            t = getattr(sf, "bl_socket_idname", sf.bl_idname)
            sts.new(t, sf.name, identifier=sf.identifier)

    def clear_sockets(self):
        for s in list(self.inputs):
            self.inputs.remove(s)
        for s in list(self.outputs):
            self.outputs.remove(s)

    def clear_unused_sockets(self):
        for s in list(self.inputs):
            if s.links:
                continue
            self.inputs.remove(s)
        for s in list(self.outputs):
            if s.links:
                continue
            self.outputs.remove(s)


class SDNGroupEdit(bpy.types.Operator):
    bl_idname = 'sdn.group_edit'
    bl_label = 'Edit node group'
    action: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context: bpy.types.Context):
        tree = getattr(context.space_data, 'edit_tree', None)
        return tree and tree.bl_idname == 'CFNodeTree'

    def execute(self, context: bpy.types.Context):
        node = context.active_node
        if node and hasattr(node, 'node_tree'):
            sub_tree: bpy.types.NodeTree = node.node_tree
            context.space_data.path.append(sub_tree, node=node)
        elif len(context.space_data.path) > 1:
            context.space_data.path.pop()
        return {'FINISHED'}


class PackGroupTree(bpy.types.Operator):
    bl_idname = "sdn.pack_group_tree"
    bl_label = "Pack group tree"
    action: bpy.props.StringProperty()

    def get_center(self, nodes: list[bpy.types.Node]) -> Vector:
        center = Vector().to_2d()
        for n in nodes:
            center += n.location
        return center / len(nodes)

    def execute(self, context):
        tree: bpy.types.NodeTree = context.space_data.edit_tree
        if len(context.space_data.path) > 1:
            self.report({'ERROR'}, _T("Depth of group tree is limited to 1"))
            return {"CANCELLED"}
        if not tree:
            return {"CANCELLED"}
        selected = [n for n in tree.nodes if n.select]
        if self.action == "SELECT":
            if selected:
                # 如果选中的节点中有组节点，则报深度错误
                if any([n.bl_idname == "SDNCustomGroup" for n in selected]):
                    self.report({"ERROR"}, _T("Node group can't be nested"))
                    return {"CANCELLED"}
                bpy.ops.node.clipboard_copy()
            else:
                return {"CANCELLED"}
        gp: bpy.types.NodeCustomGroup = tree.nodes.new("SDNCustomGroup")
        sub_tree = bpy.data.node_groups.new("Group", "CFNodeTree")
        sub_tree.use_fake_user = True
        sub_tree.root = False
        gp.node_tree = sub_tree
        sub_tree.nodes.new("NodeGroupInput").location = (-250, 0)
        sub_tree.nodes.new("NodeGroupOutput").location = (250, 0)
        tree.nodes.active = gp
        bpy.ops.sdn.group_edit()
        if self.action == "SELECT":
            bpy.ops.node.select_all(action="DESELECT")
            bpy.ops.node.clipboard_paste()
            # 将粘贴的节点和组节点移动到中心
            center = self.get_center(selected)
            for n in sub_tree.nodes:
                if not n.select:
                    continue
                n.location -= center
            gp.location = center
            # 清理
            for n in selected:
                tree.nodes.remove(n)
        return {"FINISHED"}


class UnPackGroupTree(bpy.types.Operator):
    bl_idname = "sdn.unpack_group_tree"
    bl_label = "Unpack group to nodes"
    action: bpy.props.StringProperty()

    def get_center(self, nodes: list[bpy.types.Node]) -> Vector:
        center = Vector().to_2d()
        for n in nodes:
            center += n.location
        return center / len(nodes)

    def execute(self, context):
        tree: bpy.types.NodeTree = context.space_data.edit_tree
        node = context.active_node
        if not tree or not node or not hasattr(node, "node_tree"):
            return {"CANCELLED"}
        bpy.ops.sdn.group_edit()
        bpy.ops.node.select_all(action="SELECT")
        # 取消 NodeGroupInput 和 NodeGroupOutput 的选择
        for n in context.space_data.edit_tree.nodes:
            if n.bl_idname not in ("NodeGroupInput", "NodeGroupOutput"):
                continue
            n.select = False
        bpy.ops.node.clipboard_copy()
        if len(context.space_data.path) > 1:
            context.space_data.path.pop()
        bpy.ops.node.select_all(action="DESELECT")
        bpy.ops.node.clipboard_paste()
        # 将粘贴的节点的中心移动到组节点的位置
        loc = node.location
        selected = [n for n in tree.nodes if n.select]
        center = self.get_center(selected)
        offset = loc - center
        for n in selected:
            n.location += offset
        tree.nodes.remove(node)
        return {"FINISHED"}


nodeview_keymaps = []


def add_keymap():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    km = kc.keymaps.new(name="Node Editor", space_type="NODE_EDITOR")

    # ctrl+G
    kmi = km.keymap_items.new(PackGroupTree.bl_idname, "G", "PRESS", ctrl=True)
    kmi.properties.action = "SELECT"
    nodeview_keymaps.append((km, kmi))

    # ctrl+alt+G
    kmi = km.keymap_items.new(UnPackGroupTree.bl_idname, "G", "PRESS", ctrl=True, alt=True)
    nodeview_keymaps.append((km, kmi))

    # TAB
    kmi = km.keymap_items.new(SDNGroupEdit.bl_idname, "TAB", "PRESS")
    nodeview_keymaps.append((km, kmi))


def nodegroup_reg():
    bpy.utils.register_class(SDNCustomGroup)
    bpy.utils.register_class(SDNGroupEdit)
    bpy.utils.register_class(PackGroupTree)
    bpy.utils.register_class(UnPackGroupTree)
    add_keymap()


def nodegroup_unreg():
    bpy.utils.unregister_class(SDNCustomGroup)
    bpy.utils.unregister_class(SDNGroupEdit)
    bpy.utils.unregister_class(PackGroupTree)
    bpy.utils.unregister_class(UnPackGroupTree)
