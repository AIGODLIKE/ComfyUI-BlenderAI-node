import bpy
import requests
import uuid
from urllib3.util import Timeout
from tempfile import gettempdir
from contextlib import contextmanager
from pathlib import Path
from dataclasses import dataclass
from ..utils import logger, _T, find_area_by_type
from ..timer import Timer

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
            return VLink(
                fnode.name,
                fsock.identifier,
                gtsock.node.name,
                gtsock.identifier,
                in_out,
                ltype,
            ).to_tuple()
        if in_out == "OUTPUT" and fnode.is_group():
            tree: CFNodeTree = fnode.node_tree
            # inner(group) -> outer
            # 需要记录 group 的输入节点
            inode, onode = tree.get_in_out_node()
            osock = onode.get_input(fsock[SOCK_TAG])
            gfsock = helper.find_from_sock(osock)
            # logger.critical(f"FIND OUTPUT: {gfsock}")
            return VLink(
                gfsock.node.name,
                gfsock.identifier,
                tnode.name,
                tsock.identifier,
                in_out,
                ltype,
            ).to_tuple()
        return VLink(
            link.from_node.name,
            link.from_socket.identifier,
            link.to_node.name,
            link.to_socket.identifier,
            in_out,
            ltype,
        ).to_tuple()

    def to_tuple(self):
        return (
            self.fnode_name,
            self.fsock_name,
            self.tnode_name,
            self.tsock_name,
            self.in_out,
            self.ltype,
        )

    def relink_toggle(self, node: bpy.types.Node, tree: bpy.types.NodeTree):
        from .nodes import NodeBase
        from .tree import CFNodeTree

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
        logger.warning("Relink failed: %s", self.to_tuple())

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
        logger.warning("Relink failed: %s", self.to_tuple())

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
    def __init__(self) -> None: ...

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


class WindowLogger:
    _logs = []
    _window = None

    @classmethod
    def push_log(cls, pattern, *msg):
        s = pattern % msg
        cls._logs.append(s)
        cls.move_cursor_to_last()
        text = cls.get_text()
        text.write(s + "\n")

    @classmethod
    def move_cursor_to_last(cls):
        text = cls.get_text()
        if not text:
            return
        text.cursor_set(len(text.lines), character=2**30)

    @classmethod
    def clear(cls):
        text = cls.get_text()
        text.clear()
        cls._logs.clear()
        cls._window = None

    @classmethod
    def init(cls):
        text = cls.get_text()
        text.clear()

    @classmethod
    def get_text(cls) -> bpy.types.Text:
        if "ComfyUI Log" not in bpy.data.texts:
            bpy.data.texts.new("ComfyUI Log")
        return bpy.data.texts.get("ComfyUI Log")

    @classmethod
    def open_window(cls):
        text = cls.get_text()
        cls.move_cursor_to_last()
        if not text:
            return
        bpy.ops.wm.window_new()
        cls._window = bpy.context.window_manager.windows[-1]
        area = cls._window.screen.areas[0]
        area.type = "TEXT_EDITOR"
        area.spaces[0].text = text
        area.spaces[0].show_word_wrap = True
        bpy.ops.text.jump(line=1)


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
    oldsetting = (
        r.filepath,
        r.image_settings.color_mode,
        r.image_settings.compression,
        bpy.context.scene.view_settings.view_transform,
        r.image_settings.file_format,
    )
    yield r
    r.filepath, r.image_settings.color_mode, r.image_settings.compression, bpy.context.scene.view_settings.view_transform, r.image_settings.file_format = oldsetting


def gen_mask(self):
    mode = self.mode
    channel = self.channel.title()
    mask_path = self.image
    if not Path(mask_path).parent.exists():
        return
    logger.debug(_T("Gen Mask"))
    # 设置节点
    if bpy.context.scene.compositing_node_group is None:
        nt = bpy.data.node_groups.new("Compositing", "CompositorNodeTree")
        bpy.context.scene.compositing_node_group = nt
    else:
        nt = bpy.context.scene.compositing_node_group
    with set_setting() as r:
        bpy.context.scene.render.image_settings.file_format = "PNG"
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


def calc_data_from_blender(request_data: dict) -> dict:
    # {
    #     "unique_id": 27,
    #     "message": {"data_name": "active_model"},
    #     "event": "run",
    # }
    message = request_data.get("message")
    if not message:
        return {}
    # ({"name": "camera_viewport", "type": "IMAGE", "links": None},)
    # ({"name": "render_viewport", "type": "IMAGE", "links": None},)
    # ({"name": "depth_viewport", "type": "IMAGE", "links": None},)
    # ({"name": "mist_viewport", "type": "IMAGE", "links": None},)
    # ({"name": "active_model", "type": "STRING", "links": [18]},)
    # ({"name": "custom_image", "type": "IMAGE", "links": None},)
    data_name = message.get("data_name")
    model_format = str(message.get("format", "glb")).lower()
    clear_transforms = bool(message.get("clear_transforms", True))
    no_animation_transforms = bool(message.get("no_animation_transforms", False))
    uid = uuid.uuid4().hex[:8]
    out_dir = Path(gettempdir()) / f"BlenderAI_Inputs/{data_name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    def set_frame(f):
        bpy.context.scene.frame_set(f)
    
    frame = message.get("frame", -999)
    old_frame = bpy.context.scene.frame_current
    if frame != -999:
        Timer.wait_run(set_frame)(frame)
    res = calc_data_from_blender_do(
        data_name,
        out_dir,
        uid,
        model_format=model_format,
        clear_transforms=clear_transforms,
        no_animation_transforms=no_animation_transforms,
        frame=frame,
    )
    if frame != -999:
        Timer.wait_run(set_frame)(old_frame)
    return res

def calc_data_from_blender_do(data_name, out_dir, uid, model_format="glb", clear_transforms=True, no_animation_transforms=False, frame=-999) -> dict:
    if data_name == "camera_viewport":
        data_path = out_dir / f"render_view_{uid}.png"

        def render():
            logger.warning("%s->%s", _T("Render"), data_path.as_posix())
            old = bpy.context.scene.render.filepath
            old_fmt = bpy.context.scene.render.image_settings.file_format
            bpy.context.scene.render.filepath = data_path.as_posix()
            bpy.context.scene.render.image_settings.file_format = "PNG"

            # 场景相机可能为空
            if not bpy.context.scene.camera:
                err_info = _T("No Camera in Scene") + " -> " + bpy.context.scene.name
                raise Exception(err_info)
            # 如果是cycles 且有3D视口 且 视口中模式为RENDERED时使用bpy.ops.render.render
            if bpy.context.scene.render.engine == "CYCLES":
                area = find_area_by_type(bpy.context.screen, "VIEW_3D", 0)
                spaces = area.spaces if area else []
                for space in spaces:
                    if space.type != "VIEW_3D":
                        continue
                    if space.shading.type == "RENDERED":
                        bpy.ops.render.render(write_still=True)
                        bpy.context.scene.render.filepath = old
                        bpy.context.scene.render.image_settings.file_format = old_fmt
                        return
            bpy.ops.render.opengl(write_still=True, view_context=True)
            bpy.context.scene.render.filepath = old
            bpy.context.scene.render.image_settings.file_format = old_fmt

        Timer.wait_run(render)()
        # 上传图片
        upload_status = upload_data(data_name, data_path)
        return upload_status
    elif data_name == "render_viewport":
        data_path = out_dir / f"cam_view_{uid}.png"

        def render():
            logger.warning("%s->%s", _T("Render"), data_path.as_posix())
            old = bpy.context.scene.render.filepath
            old_fmt = bpy.context.scene.render.image_settings.file_format
            bpy.context.scene.render.filepath = data_path.as_posix()
            bpy.context.scene.render.image_settings.file_format = "PNG"

            # 场景相机可能为空
            if not bpy.context.scene.camera:
                err_info = _T("No Camera in Scene") + " -> " + bpy.context.scene.name
                raise Exception(err_info)
            bpy.ops.render.render(write_still=True)
            bpy.context.scene.render.filepath = old
            bpy.context.scene.render.image_settings.file_format = old_fmt

        Timer.wait_run(render)()
        # 上传图片
        upload_status = upload_data(data_name, data_path)
        return upload_status
    elif data_name == "depth_viewport":
        # 渲染深度图
        # 上传图片
        data_path = out_dir / f"depth_view_{uid}.png"

        def render():
            logger.warning("%s->%s", _T("Render"), data_path.as_posix())
            old = bpy.context.scene.render.filepath
            old_z = bpy.context.view_layer.use_pass_z
            old_fmt = bpy.context.scene.render.image_settings.file_format
            bpy.context.view_layer.use_pass_z = True
            bpy.context.scene.render.filepath = data_path.as_posix()
            bpy.context.scene.render.image_settings.file_format = "PNG"
            if bpy.context.scene.compositing_node_group is None:
                nt = bpy.data.node_groups.new("Compositing", "CompositorNodeTree")
                bpy.context.scene.compositing_node_group = nt
            else:
                nt = bpy.context.scene.compositing_node_group
            out_layer_name = "Depth"
            with set_composite(nt) as cmp:
                render_layer: bpy.types.CompositorNodeRLayers = nt.nodes.new("CompositorNodeRLayers")
                render_layer.scene = bpy.context.scene
                render_layer.layer = bpy.context.view_layer.name
                if out := render_layer.outputs.get(out_layer_name):
                    nt.links.new(cmp.inputs["Image"], out)
                bpy.ops.render.render(write_still=True)
                nt.nodes.remove(render_layer)
            bpy.context.scene.render.filepath = old
            bpy.context.view_layer.use_pass_z = old_z
            bpy.context.scene.render.image_settings.file_format = old_fmt

        Timer.wait_run(render)()
        upload_status = upload_data(data_name, data_path)
        return upload_status
    elif data_name == "mist_viewport":
        data_path = out_dir / f"mist_view_{uid}.png"

        def render():
            logger.warning("%s->%s", _T("Render"), data_path.as_posix())
            old = bpy.context.scene.render.filepath
            old_mist = bpy.context.view_layer.use_pass_mist
            old_fmt = bpy.context.scene.render.image_settings.file_format
            bpy.context.view_layer.use_pass_mist = True
            bpy.context.scene.render.filepath = data_path.as_posix()
            bpy.context.scene.render.image_settings.file_format = "PNG"
            if bpy.context.scene.compositing_node_group is None:
                nt = bpy.data.node_groups.new("Compositing", "CompositorNodeTree")
                bpy.context.scene.compositing_node_group = nt
            else:
                nt = bpy.context.scene.compositing_node_group
            out_layer_name = "Mist"
            with set_composite(nt) as cmp:
                render_layer: bpy.types.CompositorNodeRLayers = nt.nodes.new("CompositorNodeRLayers")
                render_layer.scene = bpy.context.scene
                render_layer.layer = bpy.context.view_layer.name
                if out := render_layer.outputs.get(out_layer_name):
                    nt.links.new(cmp.inputs["Image"], out)
                bpy.ops.render.render(write_still=True)
                nt.nodes.remove(render_layer)
            bpy.context.scene.render.filepath = old
            bpy.context.view_layer.use_pass_mist = old_mist
            bpy.context.scene.render.image_settings.file_format = old_fmt

        Timer.wait_run(render)()
        upload_status = upload_data(data_name, data_path)
        return upload_status
    elif data_name == "active_model":
        # 保存当前激活模型
        # 上传模型
        export_format = str(model_format or "glb").lower()
        if export_format == "fbx":
            data_path = out_dir / f"active_model_{uid}.fbx"
        else:
            data_path = out_dir / f"active_model_{uid}.glb"

        def run():
            active_obj = bpy.context.view_layer.objects.active
            obj_state = None
            pose_state = None
            stored_action = None
            stored_nla_tracks = None
            old_mode = None
            mode_changed = False
            old_frame = None
            scene = bpy.context.scene

            def store_object_state(obj):
                state = {
                    "location": obj.location.copy(),
                    "scale": obj.scale.copy(),
                    "rotation_mode": obj.rotation_mode,
                    "rotation_euler": obj.rotation_euler.copy(),
                    "rotation_quaternion": obj.rotation_quaternion.copy(),
                    "rotation_axis_angle": tuple(obj.rotation_axis_angle),
                }
                return state

            def restore_object_state(obj, state):
                obj.location = state["location"]
                obj.scale = state["scale"]
                obj.rotation_mode = state["rotation_mode"]
                if obj.rotation_mode == "QUATERNION":
                    obj.rotation_quaternion = state["rotation_quaternion"]
                elif obj.rotation_mode == "AXIS_ANGLE":
                    obj.rotation_axis_angle = state["rotation_axis_angle"]
                else:
                    obj.rotation_euler = state["rotation_euler"]

            def clear_object_transforms(obj):
                obj.location = (0.0, 0.0, 0.0)
                obj.scale = (1.0, 1.0, 1.0)
                if obj.rotation_mode == "QUATERNION":
                    obj.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
                elif obj.rotation_mode == "AXIS_ANGLE":
                    obj.rotation_axis_angle = (0.0, 1.0, 0.0, 0.0)
                else:
                    obj.rotation_euler = (0.0, 0.0, 0.0)

            def store_pose_state(armature_obj):
                state = {}
                for pb in armature_obj.pose.bones:
                    state[pb.name] = {
                        "location": pb.location.copy(),
                        "scale": pb.scale.copy(),
                        "rotation_mode": pb.rotation_mode,
                        "rotation_euler": pb.rotation_euler.copy(),
                        "rotation_quaternion": pb.rotation_quaternion.copy(),
                        "rotation_axis_angle": tuple(pb.rotation_axis_angle),
                    }
                return state

            def restore_pose_state(armature_obj, state):
                for name, pb_state in state.items():
                    pb = armature_obj.pose.bones.get(name)
                    if not pb:
                        continue
                    pb.location = pb_state["location"]
                    pb.scale = pb_state["scale"]
                    pb.rotation_mode = pb_state["rotation_mode"]
                    if pb.rotation_mode == "QUATERNION":
                        pb.rotation_quaternion = pb_state["rotation_quaternion"]
                    elif pb.rotation_mode == "AXIS_ANGLE":
                        pb.rotation_axis_angle = pb_state["rotation_axis_angle"]
                    else:
                        pb.rotation_euler = pb_state["rotation_euler"]

            def clear_pose_transforms(armature_obj):
                for pb in armature_obj.pose.bones:
                    pb.location = (0.0, 0.0, 0.0)
                    pb.scale = (1.0, 1.0, 1.0)
                    if pb.rotation_mode == "QUATERNION":
                        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
                    elif pb.rotation_mode == "AXIS_ANGLE":
                        pb.rotation_axis_angle = (0.0, 1.0, 0.0, 0.0)
                    else:
                        pb.rotation_euler = (0.0, 0.0, 0.0)

            try:
                if clear_transforms:
                    old_frame = scene.frame_current
                    if old_frame != frame:
                        scene.frame_set(frame)
                    if active_obj:
                        old_mode = active_obj.mode
                        if old_mode != "OBJECT":
                            try:
                                bpy.ops.object.mode_set(mode="OBJECT")
                                mode_changed = True
                            except Exception as err:
                                logger.warning("Skip mode_set during export: %s", err)
                                old_mode = None
                        obj_state = store_object_state(active_obj)
                        clear_object_transforms(active_obj)
                        if active_obj.type == "ARMATURE":
                            pose_state = store_pose_state(active_obj)
                            clear_pose_transforms(active_obj)
                            if no_animation_transforms and active_obj.animation_data:
                                anim = active_obj.animation_data
                                stored_action = anim.action
                                stored_nla_tracks = []
                                for tr in anim.nla_tracks:
                                    tr_data = {
                                        "name": tr.name,
                                        "mute": getattr(tr, "mute", False),
                                        "lock": getattr(tr, "lock", False),
                                        "is_solo": getattr(tr, "is_solo", False),
                                        "strips": [],
                                    }
                                    for st in tr.strips:
                                        tr_data["strips"].append(
                                            {
                                                "name": st.name,
                                                "action": st.action,
                                                "frame_start": st.frame_start,
                                                "frame_end": st.frame_end,
                                                "action_frame_start": st.action_frame_start,
                                                "action_frame_end": st.action_frame_end,
                                                "blend_type": st.blend_type,
                                                "extrapolation": st.extrapolation,
                                                "mute": st.mute,
                                                "use_reverse": getattr(st, "use_reverse", False),
                                                "use_auto_blend": getattr(st, "use_auto_blend", False),
                                            }
                                        )
                                    stored_nla_tracks.append(tr_data)
                                anim.action = None
                                for tr in list(anim.nla_tracks):
                                    anim.nla_tracks.remove(tr)

                if export_format == "fbx":
                    bpy.ops.export_scene.fbx(
                        filepath=data_path.as_posix(),
                        use_selection=True,
                    )
                else:
                    bpy.ops.export_scene.gltf(
                        filepath=data_path.as_posix(),
                        use_selection=True,
                    )
            finally:
                if clear_transforms:
                    if old_frame is not None and scene.frame_current != old_frame:
                        scene.frame_set(old_frame)
                    if active_obj and pose_state is not None:
                        restore_pose_state(active_obj, pose_state)
                    if active_obj and obj_state is not None:
                        restore_object_state(active_obj, obj_state)
                    if active_obj and (stored_action is not None or stored_nla_tracks):
                        anim = active_obj.animation_data_create()
                        if stored_action is not None:
                            anim.action = stored_action
                        if stored_nla_tracks:
                            for tr_data in stored_nla_tracks:
                                tr = anim.nla_tracks.new()
                                tr.name = tr_data["name"]
                                if hasattr(tr, "mute"):
                                    tr.mute = tr_data.get("mute", False)
                                if hasattr(tr, "lock"):
                                    tr.lock = tr_data.get("lock", False)
                                if hasattr(tr, "is_solo"):
                                    tr.is_solo = tr_data.get("is_solo", False)
                                for st_data in tr_data["strips"]:
                                    st = tr.strips.new(
                                        st_data["name"], int(st_data["frame_start"]), st_data["action"]
                                    )
                                    st.frame_start = st_data["frame_start"]
                                    st.frame_end = st_data["frame_end"]
                                    st.action_frame_start = st_data["action_frame_start"]
                                    st.action_frame_end = st_data["action_frame_end"]
                                    st.blend_type = st_data["blend_type"]
                                    st.extrapolation = st_data["extrapolation"]
                                    st.mute = st_data["mute"]
                                    if hasattr(st, "use_reverse"):
                                        st.use_reverse = st_data["use_reverse"]
                                    if hasattr(st, "use_auto_blend"):
                                        st.use_auto_blend = st_data["use_auto_blend"]
                    if active_obj and mode_changed and old_mode and active_obj.mode != old_mode:
                        try:
                            bpy.ops.object.mode_set(mode=old_mode)
                        except Exception:
                            pass

        Timer.wait_run(run)()
        upload_status = upload_data(data_name, data_path)
        return upload_status
    elif data_name == "custom_image":
        data_path = out_dir / f"custom_image_{uid}.png"
        data_path.touch()
        upload_status = upload_data(data_name, data_path)
        return upload_status
    return {}


def upload_data(data_name, data_path):
    from .manager import TaskManager

    url = f"{TaskManager.server.get_url()}/upload/blender_inputs"
    data_path = Path(data_path)
    if data_path.is_dir() or not data_path.exists():
        return {}

    # 准备文件数据
    try:
        data = {
            "overwrite": "true",
            "subfolder": f"blender_inputs/{data_name}",
            "type": "output",
            "data_type": data_name,
        }
        data_type = f"input_data/{data_name}"
        files = {"input_data": (data_path.name, data_path.read_bytes(), data_type)}
        timeout = Timeout(connect=5, read=5)
        url = url.replace("0.0.0.0", "127.0.0.1")
        response = requests.post(url, data=data, files=files, timeout=timeout)
        # 检查响应
        if response.status_code == 200:
            logger.info("Upload Success")
            # {'name': 'icon.png', 'subfolder': 'SDN', 'type': 'input'}
            return response.json()
        else:
            logger.error(f"{_T('Upload Fail')}: [{response.status_code}] {response.text}")
    except Exception as e:
        logger.error(f"{_T('Upload Fail')}: {e}")
    return {}


def load_data_from_comfyui(data: dict[str]):
    from .blueprints import cache_to_local

    {
        "images": [{"filename": "ComfyUI_temp_ifmhd_00001_.png", "subfolder": "", "type": "temp"}],
        "models": "blender_inputs/active_model/active_model_b195d6c8.glb",
        "videos": [{"filename": "ComfyUI_temp_ifmhd_00001_.mp4", "subfolder": "video", "type": "temp"}],
        "audios": [{"filename": "ComfyUI_temp_ifmhd_00002_.flac", "subfolder": "", "type": "temp"}],
        "texts": "blender_inputs/active_model/active_model_b195d6c8.glb",
    }
    out_dir = Path(gettempdir(), "BlenderAI_Outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    images = data.get("images", [])
    models = data.get("models", "")
    videos = data.get("videos", [])
    audios = data.get("audios", [])
    texts = data.get("texts", "")
    if images:
        out_images_path = out_dir.joinpath("images")
        out_images_path.mkdir(parents=True, exist_ok=True)
        for image in images:
            save_path = out_images_path.joinpath(image["filename"])
            data_path = cache_to_local(image, save_path=save_path)
            if data_path.exists():
                logger.critical(f"Load Image: {data_path}")
    if models:
        save_path = out_dir.joinpath(models)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fetch_data = {"filename": Path(models).name, "subfolder": Path(models).parent.as_posix(), "type": "output"}
        data_path = cache_to_local(fetch_data, save_path=save_path)
        if data_path.exists() and data_path.suffix in {".gltf", ".glb"}:
            bpy.ops.import_scene.gltf(filepath=data_path.as_posix())
    if videos:
        out_videos_path = out_dir.joinpath("videos")
        out_videos_path.mkdir(parents=True, exist_ok=True)
        for video in videos:
            save_path = out_videos_path.joinpath(video["filename"])
            data_path = cache_to_local(video, save_path=save_path)
            if data_path.exists():
                logger.critical(f"Received Video: {data_path}")
    if audios:
        out_audios_path = out_dir.joinpath("audios")
        out_audios_path.mkdir(parents=True, exist_ok=True)
        for audio in audios:
            save_path = out_dir.joinpath(audio["filename"])
            data_path = cache_to_local(audio, save_path=save_path)
            if data_path.exists():
                logger.critical(f"Received Audio: {data_path}")
    if texts:
        logger.critical(f"Received Text: {texts}")

    logger.critical(f"Load Data from ComfyUI: {data}")
