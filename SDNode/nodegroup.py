from __future__ import annotations
import bpy
import time
from bpy.types import Context, Event, UILayout, Node, NodeTree, NodeSocket, NodeInputs
from mathutils import Vector
from ..kclogger import logger
from ..utils import _T
from ..timer import Timer
from ..translations import get_reg_name
from .nodes import NodeBase, Ops_Switch_Socket_Widget, Ops_Switch_Socket_Disp
from .utils import get_default_tree, Interface, THelper, VLink

SOCK_TAG = "SDN_LINK_SOCK"
LABEL_TAG = "SDN_LABEL_TAG"
NODE_TAG = "SDN_NODES"
REC_LINKS = "REC_LINKS"


class SDNGroup(bpy.types.NodeCustomGroup, NodeBase):
    bl_idname = "SDNGroup"
    bl_label = "SDNGroup"
    bl_icon = "NODETREE"
    bl_description = "SDNGroup"

    class_type = "SDNGroup"
    inp_types = {}
    out_types = {}

    @property
    def __metadata__(self):
        if self.node_tree:
            return self.node_tree.__metadata__
        return {}

    def node_tree_update(self, context):
        self.update()
    node_tree: bpy.props.PointerProperty(type=NodeTree,
                                         update=node_tree_update)

    def is_group(self) -> bool:
        return True

    def update(self):
        # from ..utils import ScopeTimer
        # t = ScopeTimer(f"G {self.name} Update", prt=logger.error)
        super().update()
        self.recursive_check()
        if not self.node_tree:
            self.clear_sockets()
            return
        self.ensure_inner_nodes()
        interface = Interface(self.node_tree)
        tree_inputs = interface.get_sockets("INPUT")
        tree_outputs = interface.get_sockets("OUTPUT")
        self.validate_sockets(self.inputs, tree_inputs)
        self.validate_sockets(self.outputs, tree_outputs)
        self.inner_links_update()
        self.adjust_sockets_order()
        # hack: update outer socket
        self.name = self.name

    def recursive_check(self):
        if self.node_tree == self.id_data:
            self.node_tree = None

    def ensure_inner_nodes(self):
        """
        检查node_tree是否有变化, 如果有变化则清空sockets
        """
        nodes = {}
        tree = self.node_tree
        for node in self.node_tree.nodes:
            if not node.is_registered_node_type():
                continue
            if node.bl_idname in ("NodeGroupInput", "NodeGroupOutput"):
                continue
            isocks = []
            nodes[node.name] = isocks
            for s in node.inputs:
                isocks.append(s.bl_idname)
        if NODE_TAG not in tree or tree[NODE_TAG].to_dict() != nodes:
            self.clear_interface(tree)
            tree[NODE_TAG] = nodes
        if NODE_TAG not in self or self[NODE_TAG].to_dict() != nodes:
            self.clear_sockets()
            self[NODE_TAG] = nodes

    def get_in_out_node(self) -> list[NodeBase]:
        in_node = None
        out_node = None
        if not self.node_tree:
            return in_node, out_node
        for n in self.node_tree.nodes:
            if n.bl_idname == "NodeGroupInput":
                in_node = n
            elif n.bl_idname == "NodeGroupOutput":
                out_node = n
        return in_node, out_node

    def inner_links_update(self):
        # 将未连接的 socket 全连到 GroupInput 和 GroupOutput
        tree: NodeTree = self.node_tree

        inode, onode = self.get_in_out_node()
        if not inode or not onode:
            return
        inode.update()
        onode.update()

        def ensure_interface(tree: NodeTree, node: Node, s: NodeSocket, in_out):
            sid = f"{node.name}[{s.identifier}]"
            stype = getattr(s, "bl_socket_idname", s.bl_idname)
            if stype == "NodeSocketUndefined":
                return None, False
            interface = Interface(tree)
            for it in interface.get_sockets(in_out):
                if it.sid == sid:
                    return it, False
            it = interface.new_socket(sid, in_out=in_out, socket_type=stype)
            if THelper.is_reroute_node(n):
                if in_out == "INPUT":
                    it.io_type = THelper().find_to_sock(n.outputs[0]).bl_idname
                else:
                    it.io_type = THelper().find_from_sock(n.inputs[0]).bl_idname
            it.sid = sid
            return it, True

        def find_socket(io: Node, node: Node, name, in_out):
            sockets = io.inputs if in_out == "OUTPUT" else io.outputs
            for s in sockets:
                if s.name == f"{node.name}[{name}]":
                    return s
            return None

        old_new = []
        # 构造顺序 ori_socket -> base_type_socket
        inner_nodes = [n for n in self.get_sort_inner_nodes() if n.bl_idname not in {"NodeGroupInput", "NodeGroupOutput"}]
        # 原始socket
        for n in inner_nodes:
            for s in n.inputs:
                if s.links and s.links[0].from_node.bl_idname != "NodeGroupInput":
                    continue
                if not n.is_ori_sock(s.name):
                    continue
                in_out = "INPUT"
                if not n.get_sock_visible(s.name, in_out=in_out):
                    continue
                it, flag = ensure_interface(tree, n, s, in_out)
                old_new.append(flag)
                if s.links:
                    continue
                oo = find_socket(inode, n, s.identifier, in_out)
                if it and oo:
                    tree.links.new(s, oo)
            if n.bl_idname == "PrimitiveNode":
                continue
            for s in n.outputs:
                if s.links and s.links[0].to_node.bl_idname != "NodeGroupOutput":
                    continue
                in_out = "OUTPUT"
                if not n.get_sock_visible(s.name, in_out=in_out):
                    continue
                it, flag = ensure_interface(tree, n, s, in_out)
                old_new.append(flag)
                if s.links:
                    continue
                oi = find_socket(onode, n, s.identifier, in_out)
                if it and oi:
                    tree.links.new(oi, s)
        # widgets
        for n in inner_nodes:
            for s in n.inputs:
                if s.links and s.links[0].from_node.bl_idname != "NodeGroupInput":
                    continue
                if n.is_ori_sock(s.name):
                    continue
                in_out = "INPUT"
                if not n.get_sock_visible(s.name, in_out=in_out):
                    continue
                it, flag = ensure_interface(tree, n, s, in_out)
                old_new.append(flag)
                if s.links:
                    continue
                oo = find_socket(inode, n, s.identifier, in_out)
                if it and oo:
                    tree.links.new(s, oo)
        # 全新增 或 全已存在 则不管
        # 部分新增 部分已存在 则清空接口(保证顺序)
        if not (all(old_new) or not any(old_new)):
            self.clear_interface(tree)
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
        interface = Interface(self.node_tree)
        for it in interface.get_sockets("INPUT"):
            interface_inputs[it.sid] = len(interface_inputs)
        for it in interface.get_sockets("OUTPUT"):
            interface_outputs[it.sid] = len(interface_outputs)
        for i in range(len(self.inputs) - 1):
            for _ in range(len(self.inputs) ** 2):
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
            for _ in range(len(self.outputs) ** 2):
                out = self.outputs[i]
                tindex = interface_outputs.get(out.name, -1)
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

        def get_socket_type(sf: NodeSocket) -> str:
            bl_idname = getattr(sf, "bl_idname", None)
            st = getattr(sf, "bl_socket_idname", bl_idname)
            if st == "NodeSocketColor":
                st = "*"
                if sf.io_type and sf.io_type != "NodeSocketColor":
                    st = sf.io_type
            # logger.debug(f"NodeSocketColor {sf.name} {sf.io_type}")
            return st
        index = 0
        # add new sockets
        for sf in list(sfs):
            if sf.identifier in sti:
                continue
            st = get_socket_type(sf)
            sock = sts.new(st, sf.name, identifier=sf.identifier)
            sock.slot_index = index
            index += 1
            sock[SOCK_TAG] = sf.identifier
            sock[LABEL_TAG] = st

    def clear_interface(self, tree):
        if not tree:
            return
        Interface(tree).clear()

    def clear_sockets(self):
        self.inputs.clear()
        self.outputs.clear()

    def clear_unused_sockets(self, tree: NodeTree, inode: NodeBase, onode: NodeBase):
        rmit = []
        interface = Interface(tree)
        for s in list(inode.outputs) + list(onode.inputs):
            if s.links:
                continue
            for it in list(interface.get_sockets()):
                if it.identifier != s.identifier:
                    continue
                rmit.append(it)
        # hack: post remove avoid crash
        for it in rmit:
            tree.update()
            inode.update()
            onode.update()
            interface.remove(it)

    def get_sort_inner_nodes(self, key=lambda x: int(x.sdn_order)) -> list[NodeBase]:
        nodes = [n for n in self.node_tree.nodes if n.is_registered_node_type()]
        nodes.sort(key=key)
        return nodes

    def draw_buttons_ext(self, context: Context, layout: UILayout):
        row = layout.row(align=True)
        row.label(text=self.name)
        row.prop(self, "sdn_hide", text="", icon="HIDE_ON" if self.sdn_hide else "HIDE_OFF")
        for node in self.get_sort_inner_nodes():
            if not node.is_registered_node_type():
                continue
            # if node.get_widgets_num() == 0:
            #     continue
            if node.bl_idname in ("NodeGroupInput", "NodeGroupOutput", "NodeReroute"):
                continue
            box = layout.box()
            node.draw_buttons_ext(context, box)
            node.draw_socket_io_box(context, box, node, "")
            col = layout.column()
            col.label(text="")

    def draw_buttons(self, context: Context, layout: UILayout):
        layout.template_ID(self, "node_tree", new=SDNNewGroup.bl_idname)
        tree = self.node_tree
        if not tree:
            return
        if self.sdn_hide:
            return
        # 显示tree中的所有未连接属性
        for node in self.get_sort_inner_nodes():
            if not node.is_registered_node_type():
                continue
            if node.get_widgets_num() == 0:
                continue
            if node.bl_idname in ("NodeGroupInput", "NodeGroupOutput", "NodeReroute"):
                continue
            if node.sdn_hide:
                continue
            box = layout.box()
            box.label(text=node.name)
            node.draw_buttons(context, box)

    def draw_socket(_self, self: NodeSocket, context, layout: UILayout, node: SDNGroup, text):
        if not node.node_tree:
            return
        # logger.error(node.name)
        if SOCK_TAG in self:
            inode, onode = node.get_in_out_node()
            link_sock = self[SOCK_TAG]
            if self.is_output and (sock := onode.get_input(link_sock)):
                if not sock.links:
                    return
                link = sock.links[0]
                fsocket: NodeSocket = link.from_socket
                fnode = link.from_node
                text = "SDN_OUTER_OUTPUT"
                if THelper.is_reroute_socket(fsocket):
                    helper = THelper()
                    fnode = helper.find_from_node(link)
                    if fnode.bl_idname == "NodeGroupInput":
                        text = fsocket.node.name
                    fsocket = helper.find_from_sock(fsocket)
                    # layout.label(text=link.from_node.name)
                    # return
                fsocket.draw(context, layout, fnode, text)
            if not self.is_output and (sock := inode.get_output(link_sock)):
                if not sock.links:
                    return
                link = sock.links[0]
                tsocket: NodeSocket = link.to_socket
                tnode = link.to_node
                text = "SDN_OUTER_INPUT"
                if THelper.is_reroute_socket(tsocket):
                    helper = THelper()
                    tnode: NodeBase = helper.find_to_node(link)
                    if tnode.bl_idname == "NodeGroupOutput":
                        text = tsocket.node.name
                    tsocket = helper.find_to_sock(tsocket)
                    # layout.label(text=link.to_node.name)
                    # return
                tsocket.draw(context, layout, tnode, text)
        else:
            layout.label(text=text)

    def free(self):
        pool = self.pool_get()
        pool.discard(self.id)
        bp = self.get_blueprints()
        bp.free(self)
        tree = self.node_tree
        if not self.node_tree:
            return
        if tree.users == 1 or (tree.use_fake_user and tree.users == 2):
            bpy.data.node_groups.remove(self.node_tree, do_unlink=True)


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
    def poll(cls, context: Context):
        tree = get_default_tree(context)
        return tree and tree.bl_idname == "CFNodeTree"

    def store_links(self):
        from .tree import CFNodeTree
        tree: CFNodeTree = get_default_tree(bpy.context)
        if not tree:
            return
        tree.store_toggle_links()

    def relink(self):
        from .tree import CFNodeTree
        tree: CFNodeTree = get_default_tree(bpy.context)
        if not tree:
            return
        tree.restore_toggle_links()

    def enter_tree(self):
        node: NodeBase = bpy.context.active_node
        sub_tree: NodeTree = node.node_tree
        if not sub_tree:
            return {"CANCELLED"}
        self.store_links()
        bpy.context.space_data.path.append(sub_tree, node=node)

    def exit_tree(self):
        from .tree import CFNodeTree
        bpy.context.space_data.path.pop()
        tree: CFNodeTree = bpy.context.space_data.node_tree
        for node in tree.nodes:
            node: NodeBase = node
            if node.bl_idname != SDNGroup.bl_idname:
                continue
            node.update()
            node.set_dirty()
        self.relink()

    def execute(self, context: Context):
        node: NodeBase = context.active_node
        if node and hasattr(node, 'node_tree'):
            self.enter_tree()
        elif len(context.space_data.path) > 1:
            self.exit_tree()
        return {'FINISHED'}


class PackGroupTree(bpy.types.Operator):
    bl_idname = "sdn.pack_group_tree"
    bl_label = "Pack group tree"
    action: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context: Context):
        tree = get_default_tree(context)
        return tree and tree.bl_idname == "CFNodeTree"

    def get_center(self, nodes: list[Node]) -> Vector:
        center = Vector().to_2d()
        for n in nodes:
            center += n.location
        return center / len(nodes)

    def execute(self, context):
        tree: NodeTree = context.space_data.edit_tree
        if len(context.space_data.path) > 1:
            self.report({'ERROR'}, _T("Depth of group tree is limited to 1"))
            return {"CANCELLED"}
        if not tree:
            return {"CANCELLED"}
        selected = [n for n in tree.nodes if n.select]
        rec_links = []
        if self.action == "SELECT":
            if not selected:
                return {"CANCELLED"}
            # 如果选中的节点中有组节点，则报深度错误
            if any([n.bl_idname == SDNGroup.bl_idname for n in selected]):
                self.report({"ERROR"}, _T("Node group can't be nested"))
                return {"CANCELLED"}
            bpy.ops.node.clipboard_copy()
            # 记录选中节点的link 以便后续恢复到 节点组外部
            for n in selected:
                # [from_node, from_socket, to_node, to_socket, in_out]
                for l in [l for sock in (n.inputs[:] + n.outputs[:]) for l in sock.links]:
                    fnode = l.from_node
                    tnode = l.to_node
                    if fnode in selected and tnode in selected:
                        continue
                    in_out = "INPUT"
                    if fnode in selected:
                        in_out = "OUTPUT"
                    link = VLink.dump(l, in_out, "PACK")
                    rec_links.append(link)
        gp: bpy.types.NodeCustomGroup = tree.nodes.new(SDNGroup.bl_idname)
        gp[REC_LINKS] = rec_links
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
    def poll(cls, context: Context):
        tree = get_default_tree(context)
        return tree and tree.bl_idname == "CFNodeTree"

    def get_center(self, nodes: list[Node]) -> Vector:
        center = Vector().to_2d()
        for n in nodes:
            center += n.location
        return center / len(nodes)

    def execute(self, context):
        from .tree import CFNodeTree
        tree: CFNodeTree = context.space_data.edit_tree
        node = context.active_node
        if not tree or not node or not hasattr(node, "node_tree"):
            return {"CANCELLED"}
        bpy.ops.sdn.group_edit()
        tree.clear_store_links()
        tree.store_toggle_links("UNPACK")
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
        with tree.with_freeze():
            bpy.ops.node.clipboard_paste()
            tree.restore_toggle_links(now=True)
        # 将粘贴的节点的中心移动到组节点的位置
        loc = node.location
        selected: list[NodeBase] = [n for n in tree.nodes if n.select]
        center = self.get_center(selected)
        offset = loc - center
        for n in selected:
            n.apply_unique_id()
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
