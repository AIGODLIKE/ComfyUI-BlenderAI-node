import bpy
import typing
import time
import sys
import traceback
from string import ascii_letters
from pathlib import Path
from bpy.app.translations import pgettext
from threading import Thread
from functools import partial
from collections import OrderedDict
from bpy.types import NodeTree
from nodeitems_utils import NodeCategory, NodeItem, register_node_categories, unregister_node_categories, _node_categories
from .nodes import nodes_reg, nodes_unreg, NodeParser, NodeBase, get_tree, clear_nodes_data_cache
from ..utils import logger, Icon, rgb2hex, hex2rgb, _T, FSWatcher
from ..datas import EnumCache
from ..timer import Timer
from ..translations import ctxt

TREE_NAME = "CFNODES_SYS"
TREE_TYPE = "CFNodeTree"


class InvalidNodeType(Exception):
    ...


class NodeItem(NodeItem):
    translation_context = ctxt

    @staticmethod
    def draw(self, layout, context):
        col = layout.column()
        col.enabled = NodeItem.new_btn_enable(self, layout, context)
        props = col.operator("node.add_node", text=pgettext(self.label), text_ctxt=ctxt)
        props.type = self.nodetype
        props.use_transform = True

    @staticmethod
    def new_btn_enable(self, layout, context):
        from .blueprints import get_blueprints
        bp = get_blueprints(self.nodetype)
        return bp.new_btn_enable(self, layout, context)


def serialize_wrapper(func):
    def wrapper(self, *args, **kwargs):
        try:
            res = func(self, *args, **kwargs)
            for k in res:
                if not isinstance(res[k], tuple):
                    continue
                n = res[k][0]
                if n.get("class_type") == "预览":
                    n["class_type"] = "PreviewImage"
            return res
        except BaseException:
            logger.error(traceback.format_exc())
        return {}
    return wrapper


def save_json_wrapper(func):
    def wrapper(self, *args, **kwargs):
        try:
            res = func(self, *args, **kwargs)
            for node in res.get("nodes", []):
                if node.get("type") == "预览":
                    node["type"] = "PreviewImage"
                if "(Blender特供)" in node.get("title", ""):
                    node["title"] = node.get("title", "").replace("(Blender特供)", "")
            return res
        except BaseException:
            logger.error(traceback.format_exc())
        return {}
    return wrapper


def load_json_wrapper(func):
    def wrapper(self, data, *args, **kwargs):
        for node in data.get("nodes", []):
            if node.get("type") == "PreviewImage":
                node["type"] = "预览"
        try:
            return func(self, data, *args, **kwargs)
        except BaseException:
            logger.error(traceback.format_exc())
        return []
    return wrapper


class CFNodeTree(NodeTree):
    bl_idname = TREE_TYPE
    bl_label = "ComfyUI Node"
    bl_icon = "EVENT_T"
    display_shape = {"CIRCLE"}
    outUpdate: bpy.props.BoolProperty(default=False)
    instance = None

    def update(self):
        CFNodeTree.instance = self

    def serialize_pre(self):
        for node in self.get_nodes():
            node.serialize_pre()

    @serialize_wrapper
    def serialize(self):
        """
        get prompts
        """
        self.validation()
        self.serialize_pre()
        return {node.id: node.make_serialze() for node in self.get_nodes() if node.class_type not in {"Reroute", "PrimitiveNode", "Note"}}

    def validation(self, nodes=None):

        if nodes is None:
            nodes = self.nodes
        for n in nodes:
            if not n.is_registered_node_type():
                raise InvalidNodeType(_T("Invalid Node Type: {}").format(n.name))

    def get_node_frame_offset(self, node: bpy.types.Node):
        # x  y  w  h  ox oy
        offset_map = {
            'win32': {
                (3, 0): [68, 69, 70, 71, 73, 74],
                (3, 1): [68, 69, 70, 71, 73, 74],
                (3, 2): [68, 69, 70, 71, 73, 74],
                (3, 3): [66, 67, 68, 69, 71, 72],
                (3, 4): [66, 67, 68, 69, 71, 72],
                (3, 5): [60, 61, 62, 63, 64, 65],
            },
            'darwin': {
                (3, 5): [60, 61, 62, 63, 64, 65],
            }
        }
        import ctypes
        ptr = node.as_pointer()
        ftype = ctypes.POINTER(ctypes.c_float)
        offset = offset_map.get(sys.platform, {}).get(bpy.app.version[:2])
        if not offset:
            return 0, 0
        ox = ctypes.cast(ptr + offset[4] * 4, ftype).contents.value
        oy = ctypes.cast(ptr + offset[5] * 4, ftype).contents.value
        return ox, oy

    def get_node_frame_location(self, node: bpy.types.Node):
        ox, oy = self.get_node_frame_offset(node)
        return node.location.x + ox, node.location.y + oy

    @save_json_wrapper
    def save_json_ex(self, dump_nodes: list[bpy.types.Node], dump_frames=None, selected_only=False):
        self.validation(dump_nodes)
        self.calc_unique_id()
        self.compute_execution_order()
        nodes_info = []
        for node in dump_nodes:
            p = node.parent
            node.parent = None
            node.update()
            info = node.dump(selected_only=selected_only)
            node.parent = p
            nodes_info.append(info)
            {"id": 7,
             "type": "CLIPTextEncode",
             "pos": [413, 389],
             "size": {"0": 425.27801513671875,
                      "1": 180.6060791015625},
             "flags": {},
             "order": 3,
             "mode": 0,
             "inputs": [{"name": "clip", "type": "CLIP", "link": 5}],
             "outputs": [{"name": "CONDITIONING",
                          "type": "CONDITIONING",
                         "links": [6],
                          "slot_index":0}],
             "properties": {},
             "widgets_values": ["bad hands"]
             }

        # pack link info into a non-verbose format
        links = []
        for i, link in enumerate(self.links):
            # links is an OBJECT
            # [id, origin_id, origin_slot, target_id, target_slot, type]
            # 当有 NodeReroute 的时候 情况比较复杂
            # from_node = self.find_from_node(link)
            # to_node = self.find_to_node(link)
            # if (to_node not in dump_nodes) or (from_node not in dump_nodes):
            #     continue
            # from_socket = self.find_from_link(link).from_socket
            # to_socket = self.find_to_link(link).to_socket
            # link_info = [
            #     i,
            #     int(from_socket.node.id),
            #     from_socket.slot_index,
            #     int(to_socket.node.id),
            #     to_socket.slot_index,
            #     from_socket.node.class_type
            # ]
            from_node = link.from_node
            from_socket = link.from_socket
            to_node = link.to_node
            to_socket = link.to_socket
            link_info = [
                i,
                int(from_socket.node.id),
                from_socket.slot_index,
                int(to_socket.node.id),
                to_socket.slot_index,
                to_node.class_type
            ]
            if to_node.class_type == "Reroute":
                link_info[-1] = "*"
            if not selected_only:
                links.append(link_info)
            elif to_node.select and link.from_node.select:
                links.append(link_info)
        if not dump_frames:
            dump_frames = [f for f in self.nodes if f.bl_idname == "NodeFrame"]
        groups = []
        for node in dump_frames:
            if node.bl_idname != "NodeFrame":
                continue
            x, y = self.get_node_frame_location(node)
            # fx = locx - (w - dw)*0.5
            # fy = locy + (h + dh)*0.5
            group_info = {
                "title": node.label,
                "bounding": [x, -y, node.width, node.height],
                "color": rgb2hex(*node.color)
            }
            groups.append(group_info)

        data = {
            "last_node_id": max([*[int(node.id) for node in self.get_nodes()], 0]),
            "last_link_id": len(self.links),
            "nodes": nodes_info,
            "links": links,
            "groups": groups,
            "config": {},
            "extra": {},
            "version": 0.4
        }
        # if onSerialize:
        #     onSerialize(data)

        return data

    def save_json(self):
        """
        get workflow
        """
        dump_nodes = self.get_nodes()

        return self.save_json_ex(dump_nodes)

    def save_json_group(self):
        dump_nodes = [n for n in self.get_nodes() if n.select]
        dump_frames = [f for f in self.nodes if f.bl_idname == "NodeFrame" and f.select]
        return self.save_json_ex(dump_nodes, dump_frames, selected_only=True)

    def load_json(self, data):
        self.clear_nodes()
        Timer.put((self.load_json_ex, data))

    def load_json_group(self, data) -> list[bpy.types.Node]:
        return self.load_json_ex(data, is_group=True)

    @load_json_wrapper
    def load_json_ex(self, data, is_group=False):
        for node in self.get_nodes(False):
            node.select = False
        load_nodes = []
        id_map = {}
        id_node_map = {}
        for node_info in data.get("nodes", []):
            t = node_info["type"]
            if t == "Reroute":
                node = self.nodes.new(type="NodeReroute")
            else:
                try:
                    node = self.nodes.new(type=t)
                except RuntimeError as e:
                    from .manager import TaskManager
                    TaskManager.put_error_msg(str(e))
                    continue
            if is_group:
                node.load(node_info, with_id=False)
            else:
                node.load(node_info)
            old_id = str(node_info["id"])
            id_map[old_id] = old_id
            id_node_map[old_id] = node
            load_nodes.append(node)
            if is_group:
                if old_id in node.pool:
                    id_map[old_id] = node.apply_unique_id()
                else:
                    node.pool.add(old_id)
                    node.id = old_id

        for link in data.get("links", []):
            # logger.debug(link)
            if str(link[1]) not in id_map:
                logger.warn(f"{_T('|IGNORED|')} Link -> {link[0]} -> {_T('Not Found Node')}: {link[1]}")
                continue
            if str(link[3]) not in id_map:
                logger.warn(f"{_T('|IGNORED|')} Link -> {link[0]} -> {_T('Not Found Node')}: {link[3]}")
                continue
            from_node = id_node_map[str(link[1])]
            to_node = id_node_map[str(link[3])]
            if not from_node or not to_node:
                logger.warn(f"Not Found Link:{link}")
                continue
            from_slot = link[2]
            to_slot = link[4]
            find_out = None
            for out in from_node.outputs:
                if from_node.class_type == "Reroute":
                    find_out = out
                    break
                if out.slot_index == from_slot:
                    find_out = out
                    break
            find_in = None
            for inp in to_node.inputs:
                if to_node.class_type == "Reroute":
                    find_in = inp
                    break
                if inp.slot_index == to_slot:
                    find_in = inp
                    break
            if find_in and find_out:
                self.links.new(find_out, find_in)
            else:
                logger.error(link)
        for group in data.get("groups", []):
            label = group.get("title")
            bounding = group.get("bounding")
            color = group.get("color")
            node = self.nodes.new(type="NodeFrame")
            load_nodes.append(node)
            node.shrink = False
            if label:
                node.label = label
            if color:
                node.use_custom_color = True
                try:
                    node.color = hex2rgb(color)
                except BaseException:
                    logger.warn(f"Color: {color} Set Failed!")
            node.location.x = bounding[0]
            node.location.y = -bounding[1]
            node.width = bounding[2]
            node.height = bounding[3]
            node.update()
        return load_nodes

    def get_nodes(self, cmf=True) -> list[NodeBase]:
        if cmf:
            return [n for n in self.nodes if n.bl_idname not in {"NodeFrame", } and n.is_registered_node_type()]
        return [n for n in self.nodes if n.is_registered_node_type()]

    def clear_nodes(self):
        def remove_nodes():
            import time
            time.sleep(0.1)
            self.nodes.clear()
        t = Thread(target=remove_nodes)
        t.start()
        t.join()

    def safe_remove_nodes(self, nodes):
        def remove_nodes(tree: bpy.types.NodeTree, nodes):
            import time
            time.sleep(0.1)
            for n in nodes:
                tree.nodes.remove(n)
        t = Thread(target=partial(remove_nodes, self, nodes))
        t.start()
        t.join()

    def find_from_node(self, link: bpy.types.NodeLink):
        return self.find_node_ex(link, is_from=True, ret_socket=False)

    def find_to_node(self, link: bpy.types.NodeLink):
        return self.find_node_ex(link, is_from=False, ret_socket=False)

    def find_from_link(self, link: bpy.types.NodeLink):
        return self.find_node_ex(link, is_from=True, ret_socket=True)

    def find_to_link(self, link: bpy.types.NodeLink):
        return self.find_node_ex(link, is_from=False, ret_socket=True)

    def find_node_ex(self, link: bpy.types.NodeLink, is_from, ret_socket=False):
        while True:
            if is_from:
                node = link.from_node
            else:
                node = link.to_node
            if node.bl_idname == "NodeReroute":
                if is_from and node.inputs[0].is_linked:
                    link = node.inputs[0].links[0]
                elif not is_from and node.outputs[0].is_linked:
                    link = node.outputs[0].links[0]
                else:
                    return
            else:
                return link if ret_socket else node

    def calc_unique_id(self):
        """
        force unique id
        """
        nodes = self.get_nodes()
        for n in nodes:
            if n.id == "-1":
                n.apply_unique_id()
            for nn in nodes:
                if nn == n:
                    continue
                if nn.id == n.id:
                    n.apply_unique_id()

    def update_tick(self):
        """
        force update
        """
        self.id_clear_update()
        self.primitive_node_update()

    def id_clear_update(self):
        ids = set()
        nodes = self.get_nodes(cmf=True)
        for node in nodes:
            ids.add(node.id)
        NodeBase.pool.clear()
        NodeBase.pool.update(ids)

    def primitive_node_update(self):
        from .nodes import get_reg_name
        for node in self.nodes:
            if node.bl_idname != "PrimitiveNode":
                continue
            # 未连接或link为空则不需要后续操作
            if not node.outputs[0].is_linked or not node.outputs[0].links:
                continue
            prop = getattr(node.outputs[0].links[0].to_node, get_reg_name(node.prop), None)
            if prop is None:
                continue
            for link in node.outputs[0].links[1:]:
                if not link.to_node.is_registered_node_type():
                    continue
                n = get_reg_name(link.to_socket.name)
                old_prop = getattr(link.to_node, n)
                setattr(link.to_node, n, type(old_prop)(prop))

    def compute_execution_order(self):
        """
        Reference from ComfyUI
        """
        L = []
        S = []  # 起始节点
        M = OrderedDict()
        visited_links = {}   # to avoid repeating links
        remaining_links = {}

        # 搜索无inp的节点(起始点)
        for node in self.get_nodes():
            M[node.id] = node  # add to pending nodes
            num = 0  # num of input connections
            for inp in node.inputs:
                if inp.links:
                    num += 1
            if num == 0:
                S.append(node)
            else:
                remaining_links[node.id] = num
        while S:
            node = S.pop()  # get an starting node
            L.append(node)  # add to ordered list
            M.pop(node.id)  # remove from the pending nodes
            for output in node.outputs:
                for olink in output.links:
                    # link_id = output.links[j] # 全局 links 是一个列表,这里的 link_id 用来取link
                    from_node = self.find_from_node(olink)
                    to_node = self.find_to_node(olink)
                    {"id": 1, "type": "MODEL", "origin_id": 4, "origin_slot": 0, "target_id": 3, "target_slot": 0, "_data": None, "_pos": {"0": 607, "1": 335}}
                    if to_node is None:
                        continue
                    # already visited link (ignore it)
                    if to_node.id in visited_links:
                        continue
                    visited_links[from_node.id] = True  # mark as visited
                    remaining_links[to_node.id] -= 1  # reduce the number of links remaining
                    if remaining_links[to_node.id] == 0:
                        S.append(to_node)
        # the remaining ones (loops)
        for i in M:
            L.append(M[i])

        for i, n in enumerate(L):
            n.sdn_order = i
        return L

    def get_node_by_id(self, id):
        for node in self.get_nodes(cmf=True):
            if node.id == id:
                return node
        return None

    @staticmethod
    @bpy.app.handlers.persistent
    def reinit(scene):
        Timer.unreg()
        Icon.clear()
        EnumCache.clear()
        CFNodeTree.force_regen_id()
        CFNodeTree.reset_node()
        Timer.reg()

    @staticmethod
    def reset_node():
        for ng in bpy.data.node_groups:
            if ng.bl_idname != CFNodeTree.bl_idname:
                continue
            for node in ng.get_nodes():
                node.use_custom_color = False
                # node.color = node.dcolor
                node.calc_slot_index()

    @staticmethod
    def force_regen_id():
        for ng in bpy.data.node_groups:
            if ng.bl_idname != CFNodeTree.bl_idname:
                continue
            for node in ng.get_nodes():
                node.pool.clear()
            for node in ng.get_nodes():
                pool = node.pool
                if node.id in pool | {"-1", "0", "1", "2"}:
                    node.apply_unique_id()
                    # logger.debug("Regen: %s", node.id)
                else:
                    pool.add(node.id)
                    # logger.debug("Add: %s", node.id)


class CFNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == TREE_TYPE

    def __init__(self, *args, **kwargs) -> None:
        self.menus = kwargs.pop("menus", [])
        self.draw_fns = kwargs.pop("draw_fns", [])
        super().__init__(*args, **kwargs)


def gen_cat_id(idstr):
    while idstr[0] == "_":
        idstr = idstr[1:]
    return "NODE_MT_%s" % idstr


def reg_nodetree(identifier, cat_list, sub=False):
    if not cat_list:
        return

    def draw_node_item(self, context):
        layout: bpy.types.UILayout = self.layout
        col = layout.column(align=True)
        for menu in self.category.menus:
            col.menu(gen_cat_id(menu.identifier), text_ctxt=ctxt)
        for item in self.category.items(context):
            item.draw(item, col, context)
        for draw_fn in getattr(self.category, "draw_fns", []):
            draw_fn(self)

    menu_types = []
    for cat in cat_list:
        reg_nodetree(cat.identifier, cat.menus, sub=True)
        __data__ = {
            "bl_space_type": 'NODE_EDITOR',
            "bl_label": cat.name,
            "category": cat,
            "poll": cat.poll,
            "draw": draw_node_item,
        }
        menu_type = type(gen_cat_id(cat.identifier), (bpy.types.Menu,), __data__)
        menu_types.append(menu_type)
        bpy.utils.register_class(menu_type)
    if sub:
        return

    def draw_add_menu(self, context):
        layout = self.layout

        for cat in cat_list:
            if cat.poll(context):
                layout.menu(gen_cat_id(cat.identifier))

    _node_categories[identifier] = (cat_list, draw_add_menu, menu_types)


def load_node(nodetree_desc, root=""):
    node_cat = []
    for cat, nodes in nodetree_desc.items():
        ocat = cat
        rep_chars = [" ", "-", "(", ")", "[", "]", "{", "}", ",", ".", ":", ";", "'", '"', "/", "\\", "|", "?", "*", "<", ">", "=", "+", "&", "^", "%", "$", "#", "@", "!", "`", "~"]
        for c in rep_chars:
            cat = cat.replace(c, "_")
        # cat = cat.replace(" ", "_").replace("-", "_")
        if cat and cat[-1] not in ascii_letters:
            cat = cat[:-1] + "z"
        items = []
        menus = []
        for item in nodes["items"]:
            items.append(NodeItem(item))
        menus.extend(load_node(nodes.get("menus", {}), root=cat))
        cat_id = f"{root}_{cat}"
        if len(cat_id) > 50:
            from hashlib import md5
            hash_root = md5(root.encode()).hexdigest()[:5]
            cat_id = f"{cat}_{hash_root}"
        cfn_cat = CFNodeCategory(cat_id, name=ocat, items=items, menus=menus)
        node_cat.append(cfn_cat)
    return node_cat


clss = []

reg, unreg = bpy.utils.register_classes_factory(clss)


def reg_node_reroute():
    from .nodes import NodeBase
    bpy.types.NodeSocketColor.slot_index = bpy.props.IntProperty(default=-1)
    bpy.types.NodeSocketColor.index = bpy.props.IntProperty(default=-1)

    bpy.types.NodeReroute.id = bpy.props.StringProperty(default="-1")
    bpy.types.NodeReroute.sdn_order = bpy.props.IntProperty(default=-1)
    bpy.types.NodeReroute.pool = NodeBase.pool
    bpy.types.NodeReroute.load = NodeBase.load
    bpy.types.NodeReroute.dump = NodeBase.dump
    bpy.types.NodeReroute.update = NodeBase.update
    bpy.types.NodeReroute.serialize_pre = NodeBase.serialize_pre
    bpy.types.NodeReroute.serialize = NodeBase.serialize
    bpy.types.NodeReroute.post_fn = NodeBase.post_fn
    bpy.types.NodeReroute.pre_fn = NodeBase.pre_fn
    bpy.types.NodeReroute.apply_unique_id = NodeBase.apply_unique_id
    bpy.types.NodeReroute.unique_id = NodeBase.unique_id
    bpy.types.NodeReroute.calc_slot_index = NodeBase.calc_slot_index
    bpy.types.NodeReroute.is_base_type = NodeBase.is_base_type
    bpy.types.NodeReroute.get_meta = NodeBase.get_meta
    bpy.types.NodeReroute.query_stat = NodeBase.query_stat
    bpy.types.NodeReroute.set_stat = NodeBase.set_stat
    bpy.types.NodeReroute.switch_socket = NodeBase.switch_socket
    bpy.types.NodeReroute.get_from_link = NodeBase.get_from_link
    bpy.types.NodeReroute.get_ctxt = NodeBase.get_ctxt
    bpy.types.NodeReroute.get_blueprints = NodeBase.get_blueprints
    bpy.types.NodeReroute.get_tree = NodeBase.get_tree

    bpy.types.NodeReroute.class_type = "Reroute"
    bpy.types.NodeReroute.__metadata__ = {}
    bpy.types.NodeReroute.inp_types = []
    bpy.types.NodeReroute.out_types = []
    bpy.types.NodeFrame.class_type = "NodeFrame"

def update_tree_handler():
    try:
        if CFNodeTree.instance:
            CFNodeTree.instance.update_tick()
            CFNodeTree.instance.calc_unique_id()
    except ReferenceError:
        ...
    except Exception as e:
        # logger.warn(str(e))
        traceback.print_exc()
        logger.error(f"{type(e).__name__}: {e}")
    finally:
        return 1


def draw_intern(self, context):
    layout: bpy.types.UILayout = self.layout
    props = layout.operator("node.add_node", text="NodeFrame", text_ctxt=ctxt)
    props.type = "NodeFrame"
    props.use_transform = True
    props = layout.operator("node.add_node", text="NodeReroute", text_ctxt=ctxt)
    props.type = "NodeReroute"
    props.use_transform = True

def draw_intern_node_search(self, context):
    if bpy.app.version <= (3, 6):
        return
    layout: bpy.types.UILayout = self.layout
    if hasattr(bpy.ops.sdn, "node_search"):
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator("sdn.node_search", text="Search", text_ctxt=ctxt, icon="VIEWZOOM")

def set_draw_intern(reg):
    NODE_MT_Utils = getattr(bpy.types, gen_cat_id("Utils"), None)
    if not NODE_MT_Utils:
        return
    # bpy.types.NODE_MT_Utils.draw._draw_funcs
    if reg:
        bpy.types.NODE_MT_add.prepend(draw_intern_node_search)
        NODE_MT_Utils.append(draw_intern)
    else:
        bpy.types.NODE_MT_add.remove(draw_intern_node_search)
        NODE_MT_Utils.remove(draw_intern)


def rtnode_reg_diff():
    t1 = time.time()
    _, node_clss, _ = NodeParser().parse(diff=True)
    if not node_clss:
        return
    logger.debug(f"变更节点: {[c.bl_label for c in node_clss]}")
    clear_nodes_data_cache()
    clss_map = {}
    for c in clss:
        clss_map[c.bl_label] = c
    for c in node_clss:
        old_c = clss_map.pop(c.bl_label, None)
        if old_c:
            bpy.utils.unregister_class(old_c)
            clss.remove(old_c)
        bpy.utils.register_class(c)
        clss.append(c)
    logger.info(_T("RegNodeDiff Time:") + f" {time.time()-t1:.2f}s")


def rtnode_reg():
    reg_node_reroute()
    clss.append(CFNodeTree)
    t1 = time.time()
    # nt_desc = {name: {items:[], menus:[nt_desc...]}}
    nt_desc, node_clss, socket_clss = NodeParser().parse()
    t2 = time.time()
    logger.info(_T("ParseNode Time:") + f" {t2-t1:.2f}s")
    node_cat = load_node(nodetree_desc=nt_desc)
    clss.extend(node_clss)
    clss.extend(socket_clss)
    nodes_reg()
    reg()
    reg_nodetree(TREE_NAME, node_cat)  # register_node_categories(TREE_NAME, node_cat)
    set_draw_intern(reg=True)
    if CFNodeTree.reinit not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(CFNodeTree.reinit)
    if not bpy.app.timers.is_registered(update_tree_handler):
        bpy.app.timers.register(update_tree_handler, persistent=True)


def rtnode_unreg():
    # bpy.app.timers.unregister(update_tree_handler)
    if CFNodeTree.reinit in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(CFNodeTree.reinit)
    set_draw_intern(reg=False)
    if TREE_NAME in _node_categories:
        unregister_node_categories(TREE_NAME)
    unreg()
    nodes_unreg()
    clss.clear()


def cb(path):
    FSWatcher.consume_change(path)
    Timer.put(rtnode_reg_diff)

NodeParser.DIFF_PATH.write_text("{}")
FSWatcher.register(NodeParser.DIFF_PATH, cb)
# def cb():
#     NodeParser.DIFF_PATH.write_text("{}")
#     time_stamp = NodeParser.DIFF_PATH.stat().st_mtime_ns
#     while True:
#         time.sleep(1)
#         ts = NodeParser.DIFF_PATH.stat().st_mtime_ns
#         if ts == time_stamp:
#             continue
#         time_stamp = ts
#         Timer.put(rtnode_reg_diff)
a = 2 * 8 + 4 * 8 + 64 + 4 + (4) + 64 + 2 + 2 + 8 + 8 + 8 + 4 * 2 + 4 * 2
"""
2*8+4*8    +64+4+4 /8+64+2+2+8+8+8+4*2+4*2

typedef struct bNode {
  struct bNode *next, *prev;  2*8
  ListBase inputs, outputs;   4*8
  char name[64];              64
  int32_t identifier;         4
  int flag;                   4 / 8
  char idname[64];            64
  int16_t type;               2
  char _pad1[2];              2
  struct ID *id;              8
  IDProperty *prop;           8
  struct bNode *parent;       8
  float locx, locy;           4*2
  float width, height;        4*2
  float offsetx, offsety;     4*2
}
"""
"""
import bpy
def get_node_frame_offset(node: bpy.types.Node):
    # x  y  w  h  ox oy
    offset_map = {
        'win32': {
            (3, 0): [68, 69, 70, 71, 73, 74],
            (3, 1): [68, 69, 70, 71, 73, 74],
            (3, 2): [68, 69, 70, 71, 73, 74],
            (3, 3): [66, 67, 68, 69, 71, 72],
            (3, 4): [66, 67, 68, 69, 71, 72],
            (3, 5): [60, 61, 62, 63, 64, 65],
        },
        'darwin': {
            (3, 5): [60, 61, 62, 63, 64, 65],
        }
    }
    import sys
    import ctypes
    ptr = node.as_pointer()
    ftype = ctypes.POINTER(ctypes.c_float)
    offset = offset_map.get(sys.platform, {}).get(bpy.app.version[:2])
    if not offset:
        return 0, 0
    ox = ctypes.cast(ptr + offset[4] * 4, ftype).contents.value
    oy = ctypes.cast(ptr + offset[5] * 4, ftype).contents.value
    return ox, oy
node = bpy.data.node_groups[0].nodes[0]
print(get_node_frame_offset(node))
"""
