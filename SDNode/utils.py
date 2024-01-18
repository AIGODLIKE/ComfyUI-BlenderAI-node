import bpy
from contextlib import contextmanager
from pathlib import Path
from dataclasses import dataclass
from ..utils import logger, _T
SELECTED_COLLECTIONS = []


@dataclass
class VLink:
    """
    用于恢复组内外节点的连接
    """
    fnode_name: str
    fsock_name: str
    tnode_name: str
    tsock_name: str
    in_out: str
    ltype: str

    @staticmethod
    def dump(link: bpy.types.NodeLink, in_out: str, ltype: str):
        from .nodes import NodeBase
        from .tree import CFNodeTree
        from .nodegroup import SOCK_TAG
        helper = THelper()
        fnode: NodeBase = link.from_node
        tnode: NodeBase = link.to_node
        fsock = link.from_socket
        tsock = link.to_socket
        if in_out == "INPUT" and tnode.is_group():
            tree: CFNodeTree = tnode.node_tree
            # outer <- inner(group)
            # 需要记录 group 的输出节点
            inode, onode = tree.get_in_out_node()
            isock = inode.get_output(tsock[SOCK_TAG])
            gtsock = helper.find_to_sock(isock)
            # logger.critical(f"FIND INPUT: {gtsock}")
            return VLink(fnode.name,
                         fsock.identifier,
                         gtsock.node.name,
                         gtsock.identifier,
                         in_out,
                         ltype).to_tuple()
        if in_out == "OUTPUT" and fnode.is_group():
            tree: CFNodeTree = fnode.node_tree
            # inner(group) -> outer
            # 需要记录 group 的输入节点
            inode, onode = tree.get_in_out_node()
            osock = onode.get_input(fsock[SOCK_TAG])
            gfsock = helper.find_from_sock(osock)
            # logger.critical(f"FIND OUTPUT: {gfsock}")
            return VLink(gfsock.node.name,
                         gfsock.identifier,
                         tnode.name,
                         tsock.identifier,
                         in_out,
                         ltype).to_tuple()
        return VLink(link.from_node.name,
                     link.from_socket.identifier,
                     link.to_node.name,
                     link.to_socket.identifier,
                     in_out,
                     ltype).to_tuple()

    def to_tuple(self):
        return (self.fnode_name,
                self.fsock_name,
                self.tnode_name,
                self.tsock_name,
                self.in_out,
                self.ltype)

    def relink_toggle(self, node: bpy.types.Node, tree: bpy.types.NodeTree):
        from .nodes import NodeBase
        from .tree import CFNodeTree
        from .nodegroup import SOCK_TAG
        helper = THelper()
        # fnode: NodeBase = tree.nodes.get(self.fnode_name)
        # tnode: NodeBase = tree.nodes.get(self.tnode_name)
        # fsock = fnode.get_output(self.fsock_name)
        # tsock = tnode.get_input(self.tsock_name)
        # if fsock and tsock:
        #     tree.links.new(tsock, fsock)
        # return
        inner_tree: CFNodeTree = node.node_tree
        if self.in_out == "INPUT":
            # outer <- inner(group)
            fnode: NodeBase = tree.nodes.get(self.fnode_name)
            fsock = fnode.get_output(self.fsock_name)
            tnode: NodeBase = inner_tree.nodes.get(self.tnode_name)
            tfsock = None
            if tnode:
                tfsock = helper.find_from_sock(tnode.get_input(self.tsock_name))
            if tfsock and tfsock.node.bl_idname == "NodeGroupInput" and fsock:
                tsock = node.get_input(tfsock.identifier)
                tree.links.new(tsock, fsock)
                return
        else:
            # inner(group) -> outer
            fnode: NodeBase = inner_tree.nodes.get(self.fnode_name)
            tnode: NodeBase = tree.nodes.get(self.tnode_name)
            tsock = tnode.get_input(self.tsock_name)
            ftsock = None
            if fnode:
                ftsock = helper.find_to_sock(fnode.get_output(self.fsock_name))
            if ftsock and ftsock.node.bl_idname == "NodeGroupOutput" and tsock:
                fsock = node.get_output(ftsock.identifier)
                tree.links.new(tsock, fsock)
                return
        logger.warn("Relink failed: %s", self.to_tuple())

    def relink_pack(self, node: bpy.types.Node, tree: bpy.types.NodeTree):
        from .nodes import NodeBase
        from .tree import CFNodeTree
        helper = THelper()
        inner_tree: CFNodeTree = node.node_tree
        if self.in_out == "INPUT":
            # outer <- inner(group)
            fnode: NodeBase = tree.nodes.get(self.fnode_name)
            tnode: NodeBase = inner_tree.nodes.get(self.tnode_name)
            fsock = fnode.get_output(self.fsock_name)
            tsock = tnode.get_input(self.tsock_name)
            in_fsock = helper.find_from_sock(tsock)
            ifid = in_fsock.identifier
            ginput = node.get_input(ifid)
            tree.links.new(ginput, fsock)
        else:
            # inner(group) -> outer
            fnode: NodeBase = inner_tree.nodes.get(self.fnode_name)
            tnode: NodeBase = tree.nodes.get(self.tnode_name)
            fsock = fnode.get_output(self.fsock_name)
            tsock = tnode.get_input(self.tsock_name)
            out_tsock = helper.find_to_sock(fsock)
            ofid = out_tsock.identifier
            goutput = node.get_output(ofid)
            tree.links.new(tsock, goutput)

    def relink_unpack(self, node: bpy.types.Node, tree: bpy.types.NodeTree):
        from .nodes import NodeBase
        from .tree import CFNodeTree
        helper = THelper()
        fnode: NodeBase = tree.nodes.get(self.fnode_name)
        tnode: NodeBase = tree.nodes.get(self.tnode_name)
        fsock = fnode.get_output(self.fsock_name)
        tsock = tnode.get_input(self.tsock_name)
        if self.in_out == "INPUT":
            # outer <- inner(group)
            tsock = helper.find_from_sock(tsock)
        else:
            # inner(group) -> outer
            fsock = helper.find_to_sock(fsock)
        if fsock and tsock:
            tree.links.new(tsock, fsock)
            return
        logger.warn("Relink failed: %s", self.to_tuple())

    def relink(self, node: bpy.types.Node, tree: bpy.types.NodeTree):
        if self.ltype == "TOGGLE":
            self.relink_toggle(node, tree)
        elif self.ltype == "PACK":
            self.relink_pack(node, tree)
        elif self.ltype == "UNPACK":
            self.relink_unpack(node, tree)


class Interface:
    # 版本兼容的 interface 操作
    def __init__(self, tree: bpy.types.NodeTree):
        self.tree = tree

    def clear(self):
        if bpy.app.version >= (4, 0):
            self.tree.interface.clear()
        else:
            self.tree.inputs.clear()
            self.tree.outputs.clear()

    def remove(self, item):
        if bpy.app.version >= (4, 0):
            self.tree.interface.remove(item)
        else:
            if item.is_output:
                self.tree.outputs.remove(item)
            else:
                self.tree.inputs.remove(item)

    def new_socket(self, sid, in_out, socket_type):
        if bpy.app.version >= (4, 0):
            return self.tree.interface.new_socket(sid, in_out=in_out, socket_type=socket_type)
        else:
            if in_out == "INPUT":
                return self.tree.inputs.new(socket_type, sid)
            else:
                return self.tree.outputs.new(socket_type, sid)

    def get_sockets(self, in_out=None):
        if bpy.app.version >= (4, 0):
            if not in_out:
                return self.tree.interface.items_tree
            return [item for item in self.tree.interface.items_tree if item.in_out == in_out]
        else:
            if not in_out:
                return self.tree.inputs[:] + self.tree.outputs[:]
            return self.tree.inputs if in_out == "INPUT" else self.tree.outputs


class THelper:
    def __init__(self) -> None:
        ...

    @staticmethod
    def reroute_sock_idname():
        return "NodeSocketColor"

    @staticmethod
    def is_reroute_node(node):
        return node.bl_idname == "NodeReroute"

    @staticmethod
    def is_reroute_socket(sock: bpy.types.NodeSocket):
        return sock.bl_idname == "NodeSocketColor"

    @staticmethod
    def in_out(sock: bpy.types.NodeSocket):
        if bpy.app.version >= (4, 0):
            return sock.in_out
        return "INPUT" if sock.is_output else "OUTPUT"

    def find_from_sock(self, tsocket: bpy.types.NodeSocket, ignore_reroute=True) -> bpy.types.NodeSocket:
        if not tsocket.is_linked:
            return tsocket
        fnode: bpy.types.Node = tsocket.links[0].from_node
        fsocket = tsocket.links[0].from_socket
        if ignore_reroute and fnode.class_type == "Reroute":
            return self.find_from_sock(fnode.inputs[0], ignore_reroute)
        return fsocket

    def find_from_node(self, link: bpy.types.NodeLink, with_end=False):
        while True:
            node = link.from_node
            if node.bl_idname == "NodeReroute":
                if node.inputs[0].is_linked:
                    link = node.inputs[0].links[0]
                elif with_end:
                    break
                else:
                    return None
            else:
                break
        return node

        return self.find_node_ex(link, is_from=True, find_link=False, with_end=with_end)

    def find_from_link(self, link: bpy.types.NodeLink, with_end=False):
        while True:
            node = link.from_node
            if node.bl_idname == "NodeReroute":
                if node.inputs[0].is_linked:
                    link = node.inputs[0].links[0]
                elif with_end:
                    break
                else:
                    return None
            else:
                break
        return link

        return self.find_node_ex(link, is_from=True, find_link=True)

    def find_to_sock(self, fsocket: bpy.types.NodeSocket, ignore_reroute=True) -> bpy.types.NodeSocket:
        if not fsocket.is_linked:
            return fsocket
        tnode: bpy.types.Node = fsocket.links[0].to_node
        tsocket = fsocket.links[0].to_socket
        if ignore_reroute and tnode.class_type == "Reroute":
            return self.find_to_sock(tnode.outputs[0], ignore_reroute)
        return tsocket

    def find_to_node(self, link: bpy.types.NodeLink, with_end=False):
        while True:
            node = link.to_node
            if node.bl_idname == "NodeReroute":
                if node.outputs[0].is_linked:
                    link = node.outputs[0].links[0]
                elif with_end:
                    return node
                else:
                    return None
            else:
                return node
        return self.find_node_ex(link, is_from=False, find_link=False, with_end=with_end)

    def find_to_link(self, link: bpy.types.NodeLink):
        return self.find_node_ex(link, is_from=False, find_link=True)

    def find_node_ex(self, link: bpy.types.NodeLink, is_from, find_link=False, with_end=False):
        while True:
            node = link.from_node if is_from else link.to_node
            if node.bl_idname == "NodeReroute":
                if (node.inputs[0] if is_from else node.outputs[0]).is_linked:
                    link = (node.inputs[0] if is_from else node.outputs[0]).links[0]
                elif with_end:
                    break
                else:
                    return None
            else:
                break
        return link if find_link else node


def get_default_tree(context=None) -> bpy.types.NodeTree:
    if context is None:
        context = bpy.context
    if hasattr(context, "sdn_tree"):
        return context.sdn_tree
    return getattr(context.space_data, "edit_tree", None)


def get_trees_from_screen(screen=None) -> list[bpy.types.NodeTree]:
    if screen is None:
        screen = bpy.context.screen
    trees = []
    for a in screen.areas:
        if a.type != "NODE_EDITOR":
            continue
        for s in a.spaces:
            if s.type != "NODE_EDITOR" or s.tree_type != "CFNodeTree":
                continue
            trees.append(s.edit_tree)
    return trees


def get_tree(current=False, screen=None) -> bpy.types.NodeTree:
    tree = getattr(bpy.context.space_data, "edit_tree", None)
    if tree:
        return tree
    trees = get_trees_from_screen(screen)
    if trees:
        tree = trees[0]
    if current:
        return tree
    # if not tree:
    #     from .tree import CFNodeTree
    #     tree = CFNodeTree.get_current_tree()
    try:
        t = tree.load_json
    except ReferenceError:
        return None
    except AttributeError:
        return tree
    return tree


def get_cmpt(nt: bpy.types.NodeTree):
    for node in nt.nodes:
        if node.type != "COMPOSITE":
            continue
        return node
    return nt.nodes.new("CompositorNodeComposite")


def get_renderlayer(nt: bpy.types.NodeTree):
    for node in nt.nodes:
        if node.type != "R_LAYERS":
            continue
        return node
    return nt.nodes.new("CompositorNodeRLayers")


@contextmanager
def set_composite(nt: bpy.types.NodeTree):
    cmp = get_cmpt(nt)
    old_socket = None
    try:
        old_socket = cmp.inputs["Image"].links[0].from_socket
    except BaseException:
        ...
    yield cmp

    if old_socket:
        nt.links.new(old_socket, cmp.inputs["Image"])


@contextmanager
def set_setting():
    r = bpy.context.scene.render
    oldsetting = (r.filepath, r.image_settings.color_mode, r.image_settings.compression,
                  bpy.context.scene.view_settings.view_transform)
    yield r
    r.filepath, r.image_settings.color_mode, r.image_settings.compression, bpy.context.scene.view_settings.view_transform = oldsetting


def gen_mask(self):
    mode = self.mode
    channel = self.channel.title()
    mask_path = self.image
    if not Path(mask_path).parent.exists():
        return
    logger.debug(_T("Gen Mask"))
    # 设置节点
    bpy.context.scene.use_nodes = True
    nt = bpy.context.scene.node_tree
    with set_setting() as r:

        if mode in {"Collection", "Object"}:
            bpy.context.view_layer.use_pass_cryptomatte_object = True
            if mode == "Collection":
                # 集合遮罩
                area = [area for area in bpy.context.screen.areas if area.type == "OUTLINER"][0]
                with bpy.context.temp_override(area=area, region=area.regions[-1]):
                    bpy.ops.sdn.get_sel_col()

                selected_objects = []
                for colname in SELECTED_COLLECTIONS:
                    selected_objects += bpy.data.collections[colname].all_objects[:]
                selected_objects = set(selected_objects)
            else:
                # 多选物体遮罩
                selected_objects = bpy.context.selected_objects

            with set_composite(nt) as cmp:
                if not cmp:
                    logger.error("Composite node not found")
                    return

                crypt = nt.nodes.new("CompositorNodeCryptomatteV2")
                crypt.matte_id = ",".join([o.name for o in selected_objects])

                inv = nt.nodes.new("CompositorNodeInvert")
                inv.invert_rgb = True
                inv.inputs["Fac"].default_value = 0
                nt.links.new(crypt.outputs["Matte"], inv.inputs["Color"])

                cmb = nt.nodes.new("CompositorNodeCombineColor")
                nt.links.new(inv.outputs["Color"], cmb.inputs[channel])

                nt.links.new(cmb.outputs["Image"], cmp.inputs["Image"])
                # 渲染遮罩
                r.filepath = mask_path

                bpy.ops.render.render(write_still=True)

                # 移除新建节点
                nt.nodes.remove(crypt)
                nt.nodes.remove(inv)
                nt.nodes.remove(cmb)

        elif mode in {"Grease Pencil", "Focus"}:
            gp: bpy.types.Object = None
            if mode == "Grease Pencil":
                gp = self.gp
            elif mode == "Focus":
                if not self.cam:
                    logger.error("Mask node not set render cam")
                    return
                gp = self.cam.get("SD_Mask")
            if isinstance(gp, list):
                gp = gp[0]
            if not gp:
                logger.error("GP not set")
                return
            if gp.name not in bpy.context.scene.objects:
                logger.error("GP not found in current scene")
                return
            gp.hide_render = False
            hide_map = {}
            for o in bpy.context.scene.objects:
                hide_map[o.name] = o.hide_render
                o.hide_render = True
            # 开启透明
            bpy.context.scene.render.film_transparent = True

            r.filepath = mask_path
            r.image_settings.color_mode = "RGBA"
            r.image_settings.compression = 100
            try:
                bpy.context.scene.view_settings.view_transform = "Standard"
            except BaseException:
                pass

            for gpo in [gp]:
                gpo.hide_render = hide_map[gpo.name]
                for l in gpo.data.layers:
                    l.use_lights = False
                    l.opacity = 1
            with set_composite(nt) as cmp:
                if not cmp:
                    logger.error("Composite node not found")
                    return
                if not (rly := get_renderlayer(nt)):
                    logger.error("Render Layer node not found")
                    return
                cmp.use_alpha = True
                cmb = nt.nodes.new("CompositorNodeCombineColor")
                nt.links.new(rly.outputs["Alpha"], cmb.inputs[channel])

                nt.links.new(cmb.outputs["Image"], cmp.inputs["Image"])
                # 渲染遮罩
                r.filepath = mask_path

                old_cam = bpy.context.scene.camera
                bpy.context.scene.camera = self.cam
                bpy.ops.render.render(write_still=True)
                if mode == "Focus":
                    bpy.context.scene.camera = old_cam
                # 移除新建节点
                nt.nodes.remove(cmb)

            for o in bpy.context.scene.objects:
                o.hide_render = hide_map.get(o.name, o.hide_render)
            gp.hide_render = True
