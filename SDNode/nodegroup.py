import bpy
import time
from bpy.types import Context, Event, UILayout, Node, NodeTree, NodeSocket, NodeInputs
from mathutils import Vector
from ..kclogger import logger
from ..utils import _T
from .nodes import NodeBase
from .utils import get_default_tree


class SDNGroup(bpy.types.NodeCustomGroup, NodeBase):
    bl_idname = "SDNGroup"
    bl_label = "SDNGroup"
    bl_icon = "NODETREE"
    bl_description = "SDNGroup"

    class_type = "SDNGroup"
    inp_types = {}
    out_types = {}

    def is_group(self) -> bool:
        return True

    def update(self):
        from ..utils import ScopeTimer
        t = ScopeTimer(f"G {self.name} Update", prt=logger.error)
        super().update()
        if not self.node_tree:
            self.clear_sockets()
            return
        tree_inputs = list(self.node_tree.sockets("INPUT"))
        tree_outputs = list(self.node_tree.sockets("OUTPUT"))
        self.validate_sockets(self.inputs, tree_inputs)
        self.validate_sockets(self.outputs, tree_outputs)
        self.inner_links_update()
        self.adjust_sockets_order()

    def inner_links_update(self):
        # 将未连接的 socket 全连到 GroupInput 和 GroupOutput
        tree: bpy.types.NodeTree = self.node_tree

        def get_in_out_node(tree: bpy.types.NodeTree) -> list[bpy.types.Node]:
            in_node = None
            out_node = None
            for n in tree.nodes:
                if n.bl_idname == "NodeGroupInput":
                    in_node = n
                elif n.bl_idname == "NodeGroupOutput":
                    out_node = n
            return in_node, out_node
        inode, onode = get_in_out_node(tree)
        if not inode or not onode:
            return
        inode.update()
        onode.update()

        def ensure_interface(tree: NodeTree, node: Node, s: NodeSocket, in_out):
            sid = node.name + " " + s.identifier
            stype = getattr(s, "bl_socket_idname", s.bl_idname)
            for it in tree.interface.items_tree:
                if it.sid == sid and it.in_out == in_out:
                    return it
            it = tree.interface.new_socket(sid, in_out=in_out, socket_type=stype)
            it.sid = sid
            return it

        def find_socket(io: Node, node: Node, name, in_out):
            sockets = io.inputs if in_out == "OUTPUT" else io.outputs
            for s in sockets:
                if s.name == node.name + " " + name:
                    return s
            return None

        for n in tree.nodes:
            if n.bl_idname in {"NodeGroupInput", "NodeGroupOutput"}:
                continue
            for s in n.inputs:
                if s.links:
                    continue
                in_out = "INPUT"
                it = ensure_interface(tree, n, s, in_out)
                oo = find_socket(inode, n, s.identifier, in_out)
                if it and oo:
                    tree.links.new(s, oo)
            for s in n.outputs:
                if s.links:
                    continue
                in_out = "OUTPUT"
                it = ensure_interface(tree, n, s, in_out)
                oi = find_socket(onode, n, s.identifier, in_out)
                if it and oi:
                    tree.links.new(oi, s)
        if self.is_dirty():
            return
        # 移除多余的socket
        self.clear_unused_sockets(tree, inode, onode)

    def adjust_sockets_order(self):
        """
        # self.inputs.move(from, to)
        # 使用move调整self的inputs 和 outputs 顺序和tree中的一致
        """
        interface_inputs = {}
        interface_outputs = {}
        for it in self.node_tree.interface.items_tree:
            if it.in_out == "INPUT":
                interface_inputs[it.sid] = len(interface_inputs)
            if it.in_out == "OUTPUT":
                interface_outputs[it.sid] = len(interface_outputs)
        for i in range(len(self.inputs) - 1):
            while True:
                inp = self.inputs[i]
                tindex = interface_inputs.get(inp.name, -1)
                if tindex == -1:
                    self.clear_sockets()
                    self.update()
                    return
                if i == tindex or tindex == -1:
                    break
                self.inputs.move(i, tindex)
        for i in range(len(self.outputs) - 1):
            while True:
                outp = self.outputs[i]
                tindex = interface_outputs.get(outp.name, -1)
                if tindex == -1:
                    self.clear_sockets()
                    self.update()
                    return
                if i == tindex or tindex == -1:
                    break
                self.outputs.move(i, tindex)

    def validate_sockets(self, sts: NodeInputs, sfs: list[NodeSocket]):
        sfi = {s.identifier for s in sfs}
        sti = {s.identifier for s in sts}
        for st in list(sts):
            if st.identifier in sfi:
                continue
            sts.remove(st)
        # add new sockets
        for sf in list(sfs):
            if sf.identifier in sti:
                continue
            t = getattr(sf, "bl_socket_idname", sf.bl_idname)
            sts.new(t, sf.name, identifier=sf.identifier)

    def clear_sockets(self):
        for s in list(self.inputs):
            self.inputs.remove(s)
        for s in list(self.outputs):
            self.outputs.remove(s)

    def clear_unused_sockets(self, tree: NodeTree, inode: NodeBase, onode: NodeBase):
        rmit = []
        for s in list(inode.outputs) + list(onode.inputs):
            if s.links:
                continue
            for it in list(tree.interface.items_tree):
                if it.identifier != s.identifier:
                    continue
                rmit.append(it)
        # hack: post remove avoid crash
        for it in rmit:
            tree.update()
            inode.update()
            onode.update()
            tree.interface.remove(it)

    def draw_buttons(self, context: Context, layout: UILayout):
        layout.template_ID(self, "node_tree", new=SDNNewGroup.bl_idname)
        tree = self.node_tree
        if not tree:
            return
        # 显示tree中的所有未连接属性
        for node in tree.nodes:
            if node.bl_idname in ("NodeGroupInput", "NodeGroupOutput"):
                continue
            box = layout.box()
            box.label(text=node.name)
            node.draw_buttons(context, box)


class SDNNewGroup(bpy.types.Operator):
    bl_idname = "sdn.new_group"
    bl_label = "New node group"
    bl_description = "New node group"
    bl_options = {"REGISTER", "UNDO"}

    def new_tree(self):
        sub_tree = bpy.data.node_groups.new("Group", "CFNodeTree")
        sub_tree.use_fake_user = True
        sub_tree.root = False
        sub_tree.nodes.new("NodeGroupInput").location = (-250, 0)
        sub_tree.nodes.new("NodeGroupOutput").location = (250, 0)
        return sub_tree

    def execute(self, context: Context):
        node: NodeBase = context.node
        if not node or not node.is_group():
            return {"CANCELLED"}
        tree = self.new_tree()
        node.node_tree = tree
        return {"FINISHED"}

    def modal(self, context: Context, event: Event):
        if self.action != "NEW":
            return {"FINISHED"}
        if event.type == "MOUSEMOVE":
            context.active_node.location = context.space_data.cursor_location
        elif event.type in ("LEFTMOUSE", "RIGHTMOUSE"):
            return {"FINISHED"}
        elif event.type == "ESC":
            bpy.ops.node.delete()
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}


class SDNGroupEdit(bpy.types.Operator):
    bl_idname = 'sdn.group_edit'
    bl_label = 'Edit node group'
    action: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context: bpy.types.Context):
        tree = get_default_tree(context)
        return tree and tree.bl_idname == "CFNodeTree"

    def execute(self, context: bpy.types.Context):
        node: NodeBase = context.active_node
        if node and hasattr(node, 'node_tree'):
            sub_tree: bpy.types.NodeTree = node.node_tree
            if not sub_tree:
                return {"CANCELLED"}
            context.space_data.path.append(sub_tree, node=node)
        elif len(context.space_data.path) > 1:
            context.space_data.path.pop()
            tree = context.space_data.node_tree
            for node in tree.nodes:
                if node.bl_idname != SDNGroup.bl_idname:
                    continue
                node.update()
                node.set_dirty()
        return {'FINISHED'}


class PackGroupTree(bpy.types.Operator):
    bl_idname = "sdn.pack_group_tree"
    bl_label = "Pack group tree"
    action: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context: bpy.types.Context):
        tree = get_default_tree(context)
        return tree and tree.bl_idname == "CFNodeTree"

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
                if any([n.bl_idname == SDNGroup.bl_idname for n in selected]):
                    self.report({"ERROR"}, _T("Node group can't be nested"))
                    return {"CANCELLED"}
                bpy.ops.node.clipboard_copy()
            else:
                return {"CANCELLED"}
        gp: bpy.types.NodeCustomGroup = tree.nodes.new(SDNGroup.bl_idname)
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

    @classmethod
    def poll(cls, context: bpy.types.Context):
        tree = get_default_tree(context)
        return tree and tree.bl_idname == "CFNodeTree"

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
    bpy.utils.register_class(SDNGroup)
    bpy.utils.register_class(SDNGroupEdit)
    bpy.utils.register_class(SDNNewGroup)
    bpy.utils.register_class(PackGroupTree)
    bpy.utils.register_class(UnPackGroupTree)
    add_keymap()


def nodegroup_unreg():
    bpy.utils.unregister_class(SDNGroup)
    bpy.utils.unregister_class(SDNGroupEdit)
    bpy.utils.unregister_class(SDNNewGroup)
    bpy.utils.unregister_class(PackGroupTree)
    bpy.utils.unregister_class(UnPackGroupTree)
