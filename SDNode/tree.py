from __future__ import annotations
from typing import Any
import bpy
import typing
import time
import sys
import pickle
import traceback
import inspect
import types
from hashlib import md5
from string import ascii_letters
from bpy.app.translations import pgettext
from threading import Thread
from functools import partial
from collections import OrderedDict
from bpy.types import NodeTree
from nodeitems_utils import NodeCategory, NodeItem, unregister_node_categories, _node_categories
from .nodes import nodes_reg, nodes_unreg, NodeParser, NodeBase, clear_nodes_data_cache
from ..utils import logger, Icon, rgb2hex, hex2rgb, _T, FSWatcher
from ..datas import EnumCache
from ..timer import Timer
from ..translations import ctxt, get_ori_name
from .utils import THelper
from contextlib import contextmanager

TREE_NAME = "CFNODES_SYS"
TREE_TYPE = "CFNodeTree"


class InvalidNodeType(Exception):
    ...


class CFNodeItem(NodeItem):
    translation_context = ctxt

    def draw(self, layout, context):
        col = layout.column()
        col.enabled = self.new_btn_enable(layout, context)
        props = col.operator("node.add_node", text=pgettext(self.label), text_ctxt=ctxt)
        props.type = self.nodetype
        props.use_transform = True

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
        except Exception as e:
            logger.error(traceback.format_exc())
            raise e
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
    msgbus_owner = object()
    outUpdate: bpy.props.BoolProperty(default=False)
    root: bpy.props.BoolProperty(default=True)
    freeze: bpy.props.BoolProperty(default=False, description="冻结更新")
    __metadata__ = {}

    class Pool:
        def __init__(self, tree: CFNodeTree) -> None:
            self.tree = tree

        def add(self, id):
            pool = self._get_id_pool()
            pool.add(id)
            self._set_id_pool(pool)

        def discard(self, id):
            pool = self._get_id_pool()
            pool.discard(id)
            self._set_id_pool(pool)

        def update(self, ids):
            pool = self._get_id_pool()
            pool.update(ids)
            self._set_id_pool(pool)

        def clear(self):
            self._set_id_pool(set())

        def __contains__(self, id):
            return id in self._get_id_pool()

        def __or__(self, __value: Any) -> set:
            return self._get_id_pool() | __value

        def __iter__(self) -> typing.Iterator[Any]:
            return iter(self._get_id_pool())

        def __repr__(self) -> str:
            return repr(self._get_id_pool())

        def _get_id_pool(self) -> set:
            if "ID_POOL" not in self.tree:
                self.tree["ID_POOL"] = pickle.dumps(set())
            return pickle.loads(self.tree["ID_POOL"])

        def _set_id_pool(self, value):
            if not isinstance(value, set):
                raise TypeError("ID POOL must be set")
            self.tree["ID_POOL"] = pickle.dumps(value)

    def get_id_pool(self) -> Pool:
        return self.Pool(self)

    @staticmethod
    def refresh_current_tree():
        for tree in bpy.data.node_groups:
            tree: CFNodeTree = tree
            if tree.bl_idname != TREE_TYPE:
                continue
            # 无效的sock需要重新剔除并重新连接
            for node in tree.get_nodes():
                for sock in node.inputs:
                    if sock.bl_idname != "NodeSocketUndefined":
                        continue
                    if node.is_group():
                        ...
                        # tree.interface_update(bpy.context)
                        # tree.update()
                        # bpy.msgbus.publish_rna(key=(bpy.types.SpaceNodeEditor, "node_tree"))
                    else:
                        fsock = None
                        if sock.is_linked and not sock.links:
                            fsock = sock.links[0].from_socket
                        socket_name = get_ori_name(sock.name)
                        node.switch_socket_widget(socket_name, False)
                        inp = node.switch_socket_widget(socket_name, True)
                        if fsock:
                            print("NEW LINK", fsock, inp)
                            tree.links.new(fsock, inp)
        bpy.msgbus.publish_rna(key=(bpy.types.SpaceNodeEditor, "node_tree"))

    def get_in_out_node(self) -> list[NodeBase]:
        in_node = None
        out_node = None
        for n in self.nodes:
            if n.bl_idname == "NodeGroupInput":
                in_node = n
            elif n.bl_idname == "NodeGroupOutput":
                out_node = n
        return in_node, out_node

    def update_editor(self):
        try:
            for area in bpy.context.screen.areas:
                for space in area.spaces:
                    if space.type != "NODE_EDITOR":
                        continue
                    space.node_tree = space.node_tree
                if area.type == "NODE_EDITOR":
                    area.tag_redraw()
        except Exception:
            ...

    def update(self):
        return
        logger.error(f"{self.name} Update {time.time_ns()}")

    @contextmanager
    def with_freeze(self):
        """
        context
        enter时 freeze
        exit时 unfreeze
        """
        self.freeze = True
        try:
            yield
        except BaseException:
            traceback.print_exc()
        self.freeze = False

    def serialize_pre(self):
        for node in self.get_nodes():
            node.serialize_pre()

    @serialize_wrapper
    def serialize(self, parent=None):
        """
        get prompts
        """
        self.validation()
        self.serialize_pre()
        prompt = {}
        for node in self.get_nodes():
            if node.class_type in {"Reroute", "PrimitiveNode", "Note"}:
                continue
            prompt.update(node.make_serialize(parent=parent))
        return prompt

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
    def save_json_ex(self, dump_nodes: list[NodeBase], dump_frames=None, selected_only=False):
        self.validation(dump_nodes)
        self.calc_unique_id()
        self.compute_execution_order()
        dump_nodes.sort(key=lambda x: x.id)
        nodes_info = []
        # extra 需要导出 groupNodes
        groupNodes = {}
        extra = {"groupNodes": groupNodes}
        for node in dump_nodes:
            p = node.parent
            node.parent = None
            node.update()
            info = node.dump(selected_only=selected_only)
            node.parent = p
            nodes_info.append(info)
            if node.is_group():
                if not node.node_tree:
                    continue
                tree: CFNodeTree = node.node_tree
                res = {
                    "nodes": [],
                    "links": [],
                    "external": [],
                    "config": {},
                }
                cfg = res["config"]
                ordered_nodes = tree.compute_execution_order()
                for on in ordered_nodes:
                    if on.bl_idname == "NodeReroute":
                        continue
                    ocfg = {"input": {}, "output": {}}
                    inpv = {oinp.name: {"visible": False} for oinp in on.inputs if not on.get_sock_visible(oinp.name, in_out="INPUT")}
                    # widgets:
                    widv = {w: {"visible": False} for w in on.widgets if not on.get_sock_visible(w, in_out="INPUT")}
                    inpv.update(widv)
                    outv = {i: {"visible": False} for i, oout in enumerate(on.outputs) if not on.get_sock_visible(oout.name, in_out="OUTPUT")}
                    if inpv:
                        ocfg["input"] = inpv
                    if outv:
                        ocfg["output"] = outv
                    if ocfg:
                        cfg[on.id] = ocfg
                res_ = tree.save_json()
                # 只同步 res有的key
                for k in res:
                    res[k] = res_.get(k, [])
                for n in res["nodes"]:
                    n.pop("size")
                    n["index"] = n.pop("id")
                    for nlink in n["inputs"]:
                        nlink["link"] = None
                        nlink.pop("slot_index", None)
                    for nlink in n["outputs"]:
                        nlink["links"] = []
                        # TODO: 判断是否为外部连接
                links = []
                for link in res["links"]:
                    if link[1] == -1 or link[3] == -1:
                        continue
                    # 原始数据: 0: lindex, 1: fnode, 2: fslot, 3: tnode, 4: tslot
                    # 定义已改: 0: fnode,  1: fslot, 2: tnode, 3: tslot, 4: lindex
                    link[:5] = *link[1:5], link[0]
                    links.append(link)
                res["links"] = links
                # nodes按index 排序
                res["nodes"].sort(key=lambda x: x["order"])
                index_map = {n["index"]: i for i, n in enumerate(res["nodes"])}
                for link in res["links"]:
                    link[0] = index_map[link[0]]
                    link[2] = index_map[link[2]]
                for n in res["nodes"]:
                    n["index"] = index_map[n["index"]]
                # cfg的 id 也需要经过index_map转换
                for nid in list(cfg):
                    cfg[str(index_map[int(nid)])] = cfg.pop(nid)
                if cfg:
                    res["config"] = cfg
                # nodes:
                #   1. 多一个index属性 (和id应该作用相同)
                #   2. 少id属性
                #   3. inputs  的 link为null
                #   4. outputs links为null的是输出, 为[] 的是内部连接
                #   5.
                # links:
                #   0. 只记录内部的节点连接关系
                #   1. link 开头为 null代表外部输入
                # 对应的是 node_tree中的 组输出节点的link
                # logger.error(f"GROUP: {res}")
                groupNodes[node.node_tree.name] = res
                continue
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
            from_node = link.from_node
            from_socket = link.from_socket
            to_node = link.to_node
            to_socket = link.to_socket
            if not from_socket.node.is_registered_node_type():
                logger.error(_T("Invalid Node Type: {}").format(from_socket.node.name))
                raise InvalidNodeType(_T("Invalid Node Type: {}").format(from_socket.node.name))
            if not to_socket.node.is_registered_node_type():
                logger.error(_T("Invalid Node Type: {}").format(to_socket.node.name))
                raise InvalidNodeType(_T("Invalid Node Type: {}").format(to_socket.node.name))
            link_info = [
                i,
                int(from_socket.node.id),
                from_socket.slot_index,
                int(to_socket.node.id),
                to_socket.slot_index,
                to_socket.bl_idname
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
            "extra": extra,
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
        Timer.clear() # blueprints中的setwidth 可能崩溃, 因此提前清理
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
        pool = self.get_id_pool()
        groupNodes = data.get("extra", {}).get("groupNodes", {})
        # 先加载groupNodes
        for gname, group in groupNodes.items():
            if old_gp := bpy.data.node_groups.get(gname):
                bpy.data.node_groups.remove(old_gp)
            gtree: CFNodeTree = bpy.data.node_groups.new(gname, "CFNodeTree")
            gtree.use_fake_user = True
            gtree.root = False
            for link in group.get("links", []):
                link[:5] = link[5], *link[0:4]
            gtree.load_json(group)
            gtree.nodes.new("NodeGroupInput").location = (-250, 0)
            gtree.nodes.new("NodeGroupOutput").location = (250, 0)
            gtree.__metadata__ = group

        for node_info in data.get("nodes", []):
            t = node_info["type"]
            if t == "Reroute":
                node: NodeBase = self.nodes.new(type="NodeReroute")
            elif t.startswith("workflow/"):
                from .nodegroup import SDNGroup
                node: bpy.types.NodeCustomGroup = self.nodes.new(SDNGroup.bl_idname)
                gname = t.replace("workflow/", "")
                node.node_tree = bpy.data.node_groups.get(gname)
            else:
                try:
                    node: NodeBase = self.nodes.new(type=t)
                except RuntimeError as e:
                    from .manager import TaskManager
                    TaskManager.put_error_msg(str(e))
                    continue
            if is_group:
                node.load(node_info, with_id=False)
            else:
                node.load(node_info)
            if "index" in node_info:
                old_id = str(node_info["index"])
            else:
                old_id = str(node_info["id"])
            id_map[old_id] = old_id
            id_node_map[old_id] = node
            load_nodes.append(node)
            if is_group:
                if old_id in pool:
                    id_map[old_id] = node.apply_unique_id()
                else:
                    pool.add(old_id)
                    node.id = old_id

        for nid, cfg in data.get("config", {}).items():
            node = id_node_map[nid]
            for iname, inp in cfg.get("input", {}).items():
                node.set_sock_visible(iname, in_out="INPUT", value=inp.get("visible", True))
            for oindex, out in cfg.get("output", {}).items():
                oname = node.outputs[int(oindex)].name
                node.set_sock_visible(oname, in_out="OUTPUT", value=out.get("visible", True))

        self.update_editor()
        nlinks = self.dolink(data.get("links", []), id_map, id_node_map)

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
                    logger.warning("Color: %s Set Failed!", color)
            node.location.x = bounding[0]
            node.location.y = -bounding[1]
            node.width = bounding[2]
            node.height = bounding[3]
            node.update()

        def f(links, id_map, id_node_map):
            # hack: wait for nodegroup sockets update
            time.sleep(0.1)
            Timer.put((self.dolink, links, id_map, id_node_map))
        Thread(target=f, args=(nlinks, id_map, id_node_map)).start()

        return load_nodes

    def dolink(self, links, id_map, id_node_map):
        not_found_links = []
        for link in links:
            # logger.debug(link)
            if str(link[1]) not in id_map:
                logger.warning("%s Link -> %s -> %s: %s", _T('|IGNORED|'), link[0], _T('Not Found Node'), link[1])
                continue
            if str(link[3]) not in id_map:
                logger.warning("%s Link -> %s -> %s: %s", _T('|IGNORED|'), link[0], _T('Not Found Node'), link[3])
                continue
            from_node: NodeBase = id_node_map[str(link[1])]
            to_node: NodeBase = id_node_map[str(link[3])]
            if not from_node or not to_node:
                logger.warning("Not Found Link: %s", link)
                continue
            if from_node.is_group() and len(from_node.outputs) == 0:
                not_found_links.append(link)
                continue
            if to_node.is_group() and len(to_node.inputs) == 0:
                not_found_links.append(link)
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
        return not_found_links

    def get_nodes(self, cmf=True) -> list[NodeBase]:
        if cmf:
            return [n for n in self.nodes if n.bl_idname not in {"NodeFrame", "NodeGroupInput", "NodeGroupOutput"} and n.is_registered_node_type()]
        return [n for n in self.nodes if n.is_registered_node_type()]

    def clear_nodes(self):
        def remove_nodes():
            time.sleep(0.1)
            self.nodes.clear()
        t = Thread(target=remove_nodes)
        t.start()
        t.join()

    def safe_remove_nodes(self, nodes):
        def remove_nodes(tree: bpy.types.NodeTree, nodes):
            time.sleep(0.1)
            for n in nodes:
                tree.nodes.remove(n)
        t = Thread(target=partial(remove_nodes, self, nodes))
        t.start()
        t.join()

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
        # 保证id从0开始
        # ids = sorted([int(n.id) for n in nodes])
        # min_id = min(ids)
        # if min_id == 0:
        #     return
        # pool = self.get_id_pool()
        # for n in nodes:
        #     pool.discard(n.id)
        #     n.id = str(int(n.id) - min_id)
        #     pool.add(n.id)

    def update_tick(self):
        """
        force update
        """
        self.id_clear_update()
        self.compute_execution_order()
        self.calc_unique_id()
        for node in self.nodes:
            if not node.is_registered_node_type():
                continue
            self.primitive_node_update(node)
            self.dirty_nodes_update(node)
            self.group_nodes_update(node)

    def id_clear_update(self):
        ids = set()
        nodes = self.get_nodes(cmf=True)
        for node in nodes:
            if not node.is_registered_node_type():
                continue
            if node.bl_idname in {"NodeGroupInput", "NodeGroupOutput"}:
                continue
            ids.add(node.id)
        pool = self.get_id_pool()
        pool.clear()
        pool.update(ids)

    def primitive_node_update(self, node: NodeBase):
        from .nodes import get_reg_name
        if node.bl_idname != "PrimitiveNode":
            return
        # 未连接或link为空则不需要后续操作
        if not node.outputs[0].is_linked or not node.outputs[0].links:
            return
        prop = getattr(node.outputs[0].links[0].to_node, get_reg_name(node.prop), None)
        if prop is None:
            return
        for link in node.outputs[0].links[1:]:
            if not link.to_node.is_registered_node_type():
                continue
            n = get_reg_name(link.to_socket.name)
            old_prop = getattr(link.to_node, n)
            setattr(link.to_node, n, type(old_prop)(prop))

    def dirty_nodes_update(self, node: NodeBase):
        if not node.is_dirty():
            return
        node.update()
        node.set_dirty(False)

    def group_nodes_update(self, node: NodeBase):
        if not node.is_group():
            return
        # node.update()

    def compute_execution_order(self) -> list[NodeBase]:
        """
        Reference from ComfyUI
        """
        helper = THelper()
        all_links = self.links.values()
        L = []
        S = []  # 起始节点
        M = OrderedDict()
        visited_links = {}   # to avoid repeating links
        remaining_links = {}

        # 搜索无inp的节点(起始点)
        for node in self.get_nodes():
            M[node.id] = node  # add to pending nodes
            # num = sum([bool(inp.links) for inp in node.inputs])  # num of input connections
            num = 0
            for inp in node.inputs:
                if not inp.links:
                    continue
                fnode = inp.links[0].from_node
                if fnode.bl_idname == "NodeGroupInput":
                    continue
                num += 1
            if num == 0:
                node.sdn_level = 1
                S.append(node)
            else:
                node.sdn_level = 0
                remaining_links[node.id] = num
        while S:
            node = S.pop(0)  # get an starting node
            L.append(node)  # add to ordered list
            M.pop(node.id, None)  # remove from the pending nodes
            for output in node.outputs:
                for olink in output.links:
                    # link_id = output.links[j] # 全局 links 是一个列表,这里的 link_id 用来取link
                    from_node = helper.find_from_node(olink)
                    to_node = helper.find_to_node(olink)
                    if not from_node or from_node.bl_idname == "NodeGroupInput":
                        from_node = None
                    if not to_node or to_node.bl_idname == "NodeGroupOutput":
                        to_node = None
                    # _LINK_DEF = {
                    #     "id": 1,
                    #     "origin_id": 4,
                    #     "origin_slot": 0,
                    #     "target_id": 3,
                    #     "target_slot": 0,
                    #     "type": "MODEL",
                    # }
                    if to_node is None:
                        continue
                    if not to_node.sdn_level or to_node.sdn_level <= node.sdn_level:
                        to_node.sdn_level = node.sdn_level + 1
                    # already visited link (ignore it)
                    link_id = all_links.index(olink)
                    if link_id in visited_links:
                        continue
                    visited_links[link_id] = True  # mark as visited
                    remaining_links[to_node.id] -= 1  # reduce the number of links remaining
                    if remaining_links[to_node.id] == 0:
                        S.append(to_node)
        # the remaining ones (loops)
        for i in M:
            L.append(M[i])

        """
        // Note: the priority is null by default
        // javascript sort function
        L = L.sort(function(A, B) {
            var Ap = A.constructor.priority || A.priority || 0;
            var Bp = B.constructor.priority || B.priority || 0;
            if (Ap == Bp) {
                //if same priority, sort by order
                return A.order - B.order;
            }
            return Ap - Bp; //sort by priority
        });
        """
        # L.sort(key=lambda x: x.sdn_order)
        for i, n in enumerate(L):
            n.sdn_order = i
        return L

    def get_node_by_id(self, id):
        for node in self.get_nodes(cmf=True):
            if node.id == id:
                return node
        return None

    def clear_store_links(self):
        from .nodegroup import REC_LINKS
        node = self.nodes.active
        if not node:
            return
        if REC_LINKS in node:
            node.pop(REC_LINKS)

    def store_toggle_links(self, ltype="TOGGLE"):
        from .nodegroup import REC_LINKS
        from .utils import VLink
        node = self.nodes.active
        if not node:
            return
        rec_links = []
        if REC_LINKS in node:
            rec_links = [tuple(l) for l in node[REC_LINKS]]
        # [from_node, from_socket, to_node, to_socket, in_out, type]
        for l in [l for sock in (node.inputs[:] + node.outputs[:]) for l in sock.links]:
            in_out = "INPUT" if l.from_node != node else "OUTPUT"
            link = VLink.dump(l, in_out, ltype)
            rec_links.append(link)
        node[REC_LINKS] = list(set(rec_links))
        # logger.debug(f"{node} store_links {rec_links}")

    def restore_toggle_links(self, now=False):
        from .nodegroup import REC_LINKS
        from .utils import VLink
        # 恢复外部link
        node = self.nodes.active
        if not node:
            return
        rec_links = node.pop(REC_LINKS, None)
        if not rec_links:
            return
        for l in rec_links:
            vlink = VLink(*l)
            if now:
                vlink.relink(node, self)
            else:
                Timer.put((vlink.relink, node, self))
            # logger.debug(f"{node} restore_links {vlink}")

    @staticmethod
    @bpy.app.handlers.persistent
    def reinit(scene):
        Timer.unreg()
        Icon.clear()
        EnumCache.clear()
        CFNodeTree.force_regen_id()
        CFNodeTree.reset_node()
        Timer.reg()
        CFNodeTree.unreg_switch_update()
        CFNodeTree.reg_switch_update()
        CFNodeTree.switch_tree_update()

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
            ng: CFNodeTree = ng
            if ng.bl_idname != CFNodeTree.bl_idname:
                continue
            pool = ng.get_id_pool()
            pool.clear()
            for node in ng.get_nodes():
                if node.id in pool | {"-1", "0", "1", "2"}:
                    node.apply_unique_id()
                    # logger.debug("Regen: %s", node.id)
                else:
                    pool.add(node.id)
                    # logger.debug("Add: %s", node.id)

    @staticmethod
    def switch_tree_update():
        for group in bpy.data.node_groups:
            group: CFNodeTree = group
            if group.bl_idname != TREE_TYPE:
                continue
            for node in group.get_nodes():
                node.update()

    @staticmethod
    def reg_switch_update():
        bpy.msgbus.subscribe_rna(
            key=(bpy.types.SpaceNodeEditor, "node_tree"),
            owner=CFNodeTree,
            args=(),
            notify=CFNodeTree.switch_tree_update,
            options={"PERSISTENT"}
        )

    @staticmethod
    def unreg_switch_update():
        bpy.msgbus.clear_by_owner(CFNodeTree)


class CFNodeCategory(NodeCategory):

    def poll(self, context):
        return context.space_data.tree_type == TREE_TYPE

    def __init__(self, *args, **kwargs) -> None:
        self.menus = kwargs.pop("menus", [])
        self.draw_fns = kwargs.pop("draw_fns", [])
        super().__init__(*args, **kwargs)

    def __repr__(self) -> str:
        info = f"\nCFNodeCategory({self.name})"
        info += f"\n\tdescription: {self.description}"
        info += f"\n\tidentifier: {self.identifier}"
        info += f"\n\tname: {self.name}"
        info += f"\n\titems: {self.items}"
        info += f"\n\tmenus: {self.menus}"
        info += f"\n\tdraw_fns: {self.draw_fns}"
        return info

def gen_cat_id(idstr):
    while idstr[0] == "_":
        idstr = idstr[1:]
    return f"NODE_MT_{idstr}"


def reg_nodetree(identifier, cat_list, sub=False):
    if not cat_list:
        return

    def draw_node_item(self, context):
        layout: bpy.types.UILayout = self.layout
        col = layout.column(align=True)
        for menu in self.category.menus:
            col.menu(gen_cat_id(menu.identifier), text_ctxt=ctxt)
        for item in self.category.items(context):
            item.draw(col, context)
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


def load_node(nodetree_desc, root="", proot=""):
    node_cat = []
    for cat, nodes in nodetree_desc.items():
        ocat = cat
        rep_chars = [" ", "-", "(", ")", "[", "]", "{", "}", ",", ".", ":", ";", "'", '"', "/", "\\", "|", "?", "*", "<", ">", "=", "+", "&", "^", "%", "$", "#", "@", "!", "`", "~"]
        for c in rep_chars:
            cat = cat.replace(c, "_")
        # 替换所有非ascii字符为X
        cat = "".join([c if c in ascii_letters else "X" for c in cat])
        if cat and cat[-1] not in ascii_letters:
            cat = cat[:-1] + "z"
        items = []
        menus = []
        for item in nodes["items"]:
            items.append(CFNodeItem(item))
        menus.extend(load_node(nodes.get("menus", {}), root=cat, proot=f"{proot}/{ocat}"))
        hash_root = md5(proot.encode()).hexdigest()[:5]
        if not root:
            cat_id = cat
        else:
            cat_id = f"{root}_{cat}_{hash_root}"
        if len(cat_id) > 50:
            cat_id = f"{cat}_{hash_root}"
        if not cat_id:
            cat_id = "NoCategory"
        if not ocat:
            ocat = "NoCategory"
        cfn_cat = CFNodeCategory(cat_id, name=ocat, items=items, menus=menus)
        node_cat.append(cfn_cat)
    return node_cat


clss = []

reg, unreg = bpy.utils.register_classes_factory(clss)


def reg_node_reroute():
    from .nodes import NodeBase, SDNConfig
    bpy.types.NodeSocketColor.slot_index = bpy.props.IntProperty(default=0)
    bpy.types.NodeSocketColor.index = bpy.props.IntProperty(default=-1)
    bpy.types.NodeSocketColor.sid = bpy.props.StringProperty(default="")
    bpy.types.NodeSocketColor.io_type = bpy.props.StringProperty(default="")
    if bpy.app.version >= (4, 0):
        bpy.types.NodeTreeInterfaceSocketColor.sid = bpy.props.StringProperty(default="")
        bpy.types.NodeTreeInterfaceSocketColor.io_type = bpy.props.StringProperty(default="")
    else:
        bpy.types.NodeSocketInterfaceColor.sid = bpy.props.StringProperty(default="")
        bpy.types.NodeSocketInterfaceColor.io_type = bpy.props.StringProperty(default="")
    for inode in [bpy.types.NodeReroute, bpy.types.NodeFrame, bpy.types.NodeGroupInput, bpy.types.NodeGroupOutput]:
        inode.id = bpy.props.StringProperty(default="-1")
        inode.sdn_order = bpy.props.IntProperty(default=-1)
        inode.sdn_level = bpy.props.IntProperty(default=0)
        inode.sdn_dirty = bpy.props.BoolProperty(default=False)
        inode.sdn_hide = bpy.props.BoolProperty(default=False)
        inode.sdn_socket_visible_in = bpy.props.CollectionProperty(type=SDNConfig)
        inode.sdn_socket_visible_out = bpy.props.CollectionProperty(type=SDNConfig)
        # inode.is_dirty = NodeBase.is_dirty
        # inode.set_dirty = NodeBase.set_dirty
        # inode.is_group = NodeBase.is_group
        # inode.get_tree = NodeBase.get_tree
        # inode.load = NodeBase.load
        # inode.dump = NodeBase.dump
        # inode.update = NodeBase.update
        # inode.serialize_pre = NodeBase.serialize_pre
        # inode.serialize = NodeBase.serialize
        # inode.post_fn = NodeBase.post_fn
        # inode.pre_fn = NodeBase.pre_fn
        # inode.apply_unique_id = NodeBase.apply_unique_id
        # inode.unique_id = NodeBase.unique_id
        # inode.calc_slot_index = NodeBase.calc_slot_index
        # inode.is_base_type = NodeBase.is_base_type
        inode.get_meta = NodeBase.get_meta
        # inode.query_stats = NodeBase.query_stats
        # inode.query_stat = NodeBase.query_stat
        # inode.set_stat = NodeBase.set_stat
        # inode.switch_socket_widget = NodeBase.switch_socket_widget
        # inode.get_from_link = NodeBase.get_from_link
        # inode.get_ctxt = NodeBase.get_ctxt
        # inode.get_blueprints = NodeBase.get_blueprints
        # inode.draw_socket = NodeBase.draw_socket

        inode.class_type = inode.__name__
        inode.__metadata__ = {}
        inode.builtin__stat__ = pickle.dumps({})
        inode.inp_types = []
        inode.out_types = []
        # funcs = inspect.getmembers(NodeBase, predicate=inspect.isfunction)
        funcs = inspect.getmembers(NodeBase, predicate=lambda o: isinstance(o, (property, types.FunctionType)))
        disable_func = [
            'copy',
            'draw_buttons',
            'draw_label',
            'free',
            'init',
            # 'is_ori_sock',
            'make_serialze',
            # 'pool_get',
            'primitive_check',
            'remove_invalid_link',
            'remove_multi_link'
        ]
        for name, func in funcs:
            if name in disable_func:
                continue
            setattr(inode, name, func)
    bpy.types.NodeReroute.class_type = "Reroute"
    bpy.types.NodeFrame.class_type = "NodeFrame"


def update_tree_handler():
    try:
        for group in bpy.data.node_groups:
            group: CFNodeTree = group
            if group.bl_idname != TREE_TYPE:
                continue
            group.update_tick()
    except ReferenceError:
        ...
    except Exception as e:
        # logger.warn(str(e))
        traceback.print_exc()
        logger.error(f"{type(e).__name__}: {e}")
    return 1


def draw_intern(self, context):
    layout: bpy.types.UILayout = self.layout
    props = layout.operator("node.add_node", text="NodeFrame", text_ctxt=ctxt)
    props.type = "NodeFrame"
    props.use_transform = True
    props = layout.operator("node.add_node", text="NodeReroute", text_ctxt=ctxt)
    props.type = "NodeReroute"
    props.use_transform = True
    row = layout.row()
    row.enabled = len(context.space_data.path) <= 1
    props = row.operator("node.add_node", text="SDNGroup", text_ctxt=ctxt)
    props.type = "SDNGroup"
    props.use_transform = True


def draw_intern_node_search(self, context):
    if bpy.app.version <= (3, 6):
        return
    if context.space_data.tree_type != TREE_TYPE:
        return
    layout: bpy.types.UILayout = self.layout
    if hasattr(bpy.ops.sdn, "node_search"):
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator("sdn.node_search", text="Search", text_ctxt=ctxt, icon="VIEWZOOM")


def set_draw_intern(reg):
    NODE_MT_Utils = getattr(bpy.types, gen_cat_id("utils"), None)
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
    logger.info(f"{_T('Changed Node')}: {[c.bl_label for c in node_clss]}")
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
    nodes_reg()
    reg_node_reroute()
    clss.append(CFNodeTree)
    t1 = time.time()
    # nt_desc = {name: {items:[], menus:[nt_desc...]}}
    try:
        nt_desc, node_clss, socket_clss = NodeParser().parse()
        t2 = time.time()
        logger.info(_T("ParseNode Time:") + f" {t2-t1:.2f}s")
        node_cat = load_node(nodetree_desc=nt_desc)
        clss.extend(node_clss)
        clss.extend(socket_clss)
    except Exception:
        node_cat = []
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
