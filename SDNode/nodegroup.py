import bpy
from bpy.types import Context
from .nodes import NodeBase
from functools import reduce


class SDNCustomGroup(bpy.types.NodeCustomGroup, NodeBase):
    bl_idname = 'SDNCustomGroup'
    bl_label = 'SDNCustomGroup'
    bl_icon = 'NODETREE'
    bl_description = 'SDNCustomGroup'

    class_type = 'SDNCustomGroup'

    def update(self):
        if not self.node_tree:
            return
        tree_inputs = list(self.node_tree.sockets('INPUT'))
        tree_outputs = list(self.node_tree.sockets('OUTPUT'))
        self.validate_sockets(self.inputs, tree_inputs)
        self.validate_sockets(self.outputs, tree_outputs)

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


class SDNGroupEdit(bpy.types.Operator):
    bl_idname = 'sdn.group_edit'
    bl_label = 'Edit node group'
    action: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context: Context):
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


class AddGroupTree(bpy.types.Operator):
    bl_idname = "sdn.add_group_tree"
    bl_label = "Add group tree"
    action: bpy.props.StringProperty()

    def execute(self, context):
        if len(context.space_data.path) > 1:
            self.report({'ERROR'}, 'Depth of group tree is limited to 1')
            return {"CANCELLED"}
        tree: bpy.types.NodeTree = context.space_data.edit_tree
        if not tree:
            self.report({'ERROR'}, 'No tree to group')
            return {"CANCELLED"}
        selected = [n for n in tree.nodes if n.select]
        if self.action == "SELECT" and selected:
            bpy.ops.node.clipboard_copy()

        gp: bpy.types.NodeCustomGroup = tree.nodes.new("SDNCustomGroup")

        sub_tree = bpy.data.node_groups.new('SDN group', 'CFNodeTree')  # creating sub tree
        sub_tree.use_fake_user = True
        gp.node_tree = sub_tree
        # context.node.group_tree = sub_tree  # link sub tree to group node
        sub_tree.nodes.new('NodeGroupInput').location = (-250, 0)
        sub_tree.nodes.new('NodeGroupOutput').location = (250, 0)
        tree.nodes.active = gp
        with context.temp_override(selected=selected):
            bpy.ops.sdn.group_edit("INVOKE_DEFAULT", action=self.action)
        if selected and self.action == "SELECT":
            bpy.ops.node.clipboard_paste()
            for n in selected:
                tree.nodes.remove(n)
        return {"FINISHED"}


class AddGroupTreeFromSelected(bpy.types.Operator):
    bl_idname = "sdn.add_group_tree_from_selected"
    bl_label = "Add group tree from selected"

    def execute(self, context):
        """
        Add group tree from selected:
        01. Deselect group Input and Output nodes
        02. Copy nodes into clipboard
        03. Create group tree and move into one
        04. Past nodes from clipboard
        05. Move nodes into tree center
        06. Add group "input" and "output" outside of bounding box of the nodes
        07. Connect "input" and "output" sockets with group nodes
        08. Add Group tree node in center of selected node in initial tree
        09. Link the node with appropriate sockets
        10. Cleaning
        """
        base_tree = context.space_data.path[-1].node_tree
        if not self.can_be_grouped(base_tree):
            self.report({'WARNING'}, 'Current selection can not be converted to group')
            return {'CANCELLED'}
        sub_tree: bpy.types.NodeTree = bpy.data.node_groups.new('SDN group', 'CFNodeTree')

        # deselect group nodes if selected
        bpy.ops.node.select_all(action='DESELECT')
        for node in base_tree.nodes:
            if node.bl_idname in {'NodeGroupInput', 'NodeGroupOutput'}:
                node.select = False

        # Frames can't be just copied because they does not have absolute location, but they can be recreated
        frame_names = {n.name for n in base_tree.nodes if n.select and n.bl_idname == 'NodeFrame'}
        for n in base_tree.nodes:
            if n.bl_idname == 'NodeFrame':
                n.select = False

        with base_tree.init_tree(), sub_tree.init_tree():
            # copy and past nodes into group tree
            bpy.ops.node.clipboard_copy()
            context.space_data.path.append(sub_tree)
            bpy.ops.node.clipboard_paste()
            context.space_data.path.pop()  # will enter later via operator

            # move nodes in tree center
            sub_tree_nodes = self.filter_selected_nodes(sub_tree)
            center = reduce(lambda v1, v2: v1 + v2, [n.location for n in sub_tree_nodes]) / len(sub_tree_nodes)
            [setattr(n, 'location', n.location - center) for n in sub_tree_nodes]

            # recreate frames
            node_name_mapping = {n.name: n.name for n in sub_tree.nodes}  # all nodes have the same name as in base tree
            self.recreate_frames(base_tree, sub_tree, frame_names, node_name_mapping)

            # add group input and output nodes
            min_x = min(n.location[0] for n in sub_tree_nodes)
            max_x = max(n.location[0] for n in sub_tree_nodes)
            input_node = sub_tree.nodes.new('NodeGroupInput')
            input_node.location = (min_x - 250, 0)
            output_node = sub_tree.nodes.new('NodeGroupOutput')
            output_node.location = (max_x + 250, 0)

            # add group tree node
            initial_nodes = self.filter_selected_nodes(base_tree)
            center = reduce(lambda v1, v2: v1 + v2,
                            [Vector(n.absolute_location) for n in initial_nodes]) / len(initial_nodes)
            group_node = base_tree.nodes.new(SvGroupTreeNode.bl_idname)
            group_node.select = False
            group_node.group_tree = sub_tree
            group_node.location = center
            sub_tree.group_node_name = group_node.name

            # generate new sockets
            py_base_tree = Tree(base_tree)
            [setattr(py_base_tree.nodes[n.name], 'select', n.select) for n in base_tree.nodes]
            from_sockets, to_sockets = dict(set), dict(set)
            for py_node in py_base_tree.nodes:
                if not py_node.select:
                    continue
                for in_s in py_node.inputs:
                    for out_s in in_s.linked_sockets:  # only one link always
                        if not out_s.node.select:
                            from_sockets[out_s.bl_tween].add(in_s.get_bl_socket(sub_tree))
                for out_py_socket in py_node.outputs:
                    for in_py_socket in out_py_socket.linked_sockets:
                        if not in_py_socket.node.select:
                            to_sockets[in_py_socket.bl_tween].add(out_py_socket.get_bl_socket(sub_tree))
            for fs in from_sockets.keys():
                self.new_tree_socket(sub_tree, fs.bl_idname, fs.name, in_out='INPUT')
            for ts in to_sockets.keys():
                self.new_tree_socket(sub_tree, ts.bl_idname, ts.name, in_out='OUTPUT')
            if bpy.app.version >= (3, 5):  # generate also sockets of group nodes
                for fs in sub_tree.sockets('INPUT'):
                    group_node.inputs.new(fs.bl_socket_idname, fs.name, identifier=fs.identifier)
                for ts in sub_tree.sockets('OUTPUT'):
                    group_node.outputs.new(ts.bl_socket_idname, ts.name, identifier=ts.identifier)

            # linking, linking should be ordered from first socket to last (in case like `join list` nodes)
            for i, (from_s, first_ss) in enumerate(from_sockets.items()):
                base_tree.links.new(group_node.inputs[i], from_s)
                for first_s in first_ss:
                    sub_tree.links.new(first_s, input_node.outputs[i])
            for i, (to_s, last_ss) in enumerate(to_sockets.items()):
                base_tree.links.new(to_s, group_node.outputs[i])
                for last_s in last_ss:
                    sub_tree.links.new(output_node.inputs[i], last_s)

            # delete selected nodes and copied frames without children
            [base_tree.nodes.remove(n) for n in self.filter_selected_nodes(base_tree)]
            with_children_frames = {n.parent.name for n in base_tree.nodes if n.parent}
            [base_tree.nodes.remove(n) for n in base_tree.nodes
             if n.name in frame_names and n.name not in with_children_frames]

        with context.temp_override(node=group_node):
            bpy.ops.node.edit_group_tree(is_new_group=True)

        return {'FINISHED'}

    @staticmethod
    def filter_selected_nodes(tree) -> list:
        """Avoiding selecting nodes which should not be copied into sub tree"""
        return [n for n in tree.nodes if n.select and n.bl_idname not in {'NodeGroupInput', 'NodeGroupOutput'}]

    @staticmethod
    def new_tree_socket(tree, bl_idname, name, in_out='INPUT'):
        if bpy.app.version >= (4, 0):
            tree.interface.new_socket(name, in_out=in_out, socket_type=bl_idname)
        else:
            socks = tree.inputs if in_out == 'INPUT' else tree.outputs
            return socks.new(bl_idname, name)


nodeview_keymaps = []


def add_keymap():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='Node Editor', space_type='NODE_EDITOR')

        # ctrl+G
        kmi = km.keymap_items.new(AddGroupTree.bl_idname, 'G', 'PRESS', ctrl=True)
        kmi.properties.action = "SELECT"
        nodeview_keymaps.append((km, kmi))

        # TAB
        kmi = km.keymap_items.new(SDNGroupEdit.bl_idname, 'TAB', 'PRESS')
        nodeview_keymaps.append((km, kmi))


def nodegroup_reg():
    bpy.utils.register_class(SDNCustomGroup)
    bpy.utils.register_class(SDNGroupEdit)
    bpy.utils.register_class(AddGroupTree)
    add_keymap()


def nodegroup_unreg():
    bpy.utils.unregister_class(SDNCustomGroup)
    bpy.utils.unregister_class(SDNGroupEdit)
    bpy.utils.unregister_class(AddGroupTree)
