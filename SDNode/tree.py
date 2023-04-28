import bpy
import typing
import sys
from threading import Thread
from functools import partial
from collections import OrderedDict
from bpy.types import NodeTree
from nodeitems_utils import NodeCategory, NodeItem, register_node_categories, unregister_node_categories, _node_categories
from .nodes import nodes_reg, nodes_unreg, parse_node
from ..utils import logger, Icon, rgb2hex, hex2rgb
from ..datas import EnumCache
from ..timer import Timer

TREE_NAME = "CFNODES_SYS"

class CFNodeTree(NodeTree):
    bl_idname = "CFNodeTree"
    bl_label = "ComfyUI Node"
    bl_icon = "EVENT_T"
    display_shape = {"CIRCLE"}
    outUpdate: bpy.props.BoolProperty(default=False)

    def update(self):
        ...

    def serialize(self):
        return {node.id: (node.serialize(), node.post_fn) for node in self.get_nodes()}

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

    def save_json_ex(self, dump_nodes: list[bpy.types.Node], dump_frames=None):
        self.calc_unique_id()
        self.compute_execution_order()
        nodes_info = []
        for node in dump_nodes:
            p = node.parent
            node.parent = None
            node.update()
            info = node.dump()
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
            # TODO: 当有 NodeReroute 的时候 情况比较复杂
            from_node = self.find_from_node(link)
            to_node = self.find_to_node(link)
            if (to_node not in dump_nodes) or (from_node not in dump_nodes):
                continue
            from_socket = self.find_from_link(link).from_socket
            to_socket = self.find_to_link(link).to_socket
            link_info = [
                i,
                int(from_socket.node.id),
                from_socket.slot_index,
                int(to_socket.node.id),
                to_socket.slot_index,
                from_socket.node.class_type
            ]
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
        dump_nodes = self.get_nodes()

        return self.save_json_ex(dump_nodes)

    def save_json_group(self):
        dump_nodes = [n for n in self.get_nodes() if n.select]
        dump_frames = [f for f in self.nodes if f.bl_idname == "NodeFrame" and f.select]
        return self.save_json_ex(dump_nodes, dump_frames)

    def load_json(self, data):
        self.clear_nodes()

        def delegate(self: CFNodeTree, data):
            for node_info in data["nodes"]:
                node = self.nodes.new(type=node_info["type"])
                node.load(node_info)

            for link in data["links"]:
                # logger.debug(link)
                from_node = self.get_node_by_id(str(link[1]))
                to_node = self.get_node_by_id(str(link[3]))
                if not from_node or not to_node:
                    logger.warn(f"Not Found Link:{link}")
                    continue
                from_slot = link[2]
                to_slot = link[4]
                find_out = None
                for out in from_node.outputs:
                    if out.slot_index == from_slot:
                        find_out = out
                        break
                find_in = None
                for inp in to_node.inputs:
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
                # finalx = locx - (w - wd)*0.5
                # locx = finalx + (w - wd)*0.5
                # node.location.x = bounding[0] + (bounding[2] - node.bl_width_default)*0.5
                # node.location.y = -bounding[1] - (bounding[3] + node.bl_height_default)*0.5
                # fx = locx - (w - dw)*0.5
                # fy = locy + (h + dh)*0.5
        Timer.put((delegate, self, data))

    def load_json_group(self, data) -> list[bpy.types.Node]:
        for node in self.get_nodes(False):
            node.select = False
        load_nodes = []
        id_map = {}
        for node_info in data.get("nodes",[]):
            node = self.nodes.new(type=node_info["type"])
            load_nodes.append(node)
            node.load(node_info, with_id=False)
            old_id = str(node_info["id"])
            id_map[old_id] = old_id
            if old_id in node.pool:
                id_map[old_id] = node.apply_unique_id()
            else:
                node.pool.add(old_id)
                node.id = old_id

        for link in data.get("links", []):
            # logger.debug(link)
            from_node = self.get_node_by_id(id_map[str(link[1])])
            to_node = self.get_node_by_id(id_map[str(link[3])])
            if not from_node or not to_node:
                logger.warn(f"Not Found Link:{link}")
                continue
            from_slot = link[2]
            to_slot = link[4]
            find_out = None
            for out in from_node.outputs:
                if out.slot_index == from_slot:
                    find_out = out
                    break
            find_in = None
            for inp in to_node.inputs:
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

    def get_nodes(self, cmf=True):
        if cmf:
            return [n for n in self.nodes if n.bl_idname not in {"NodeReroute", "NodeFrame"}]
        return self.nodes[:]

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
            for nn in nodes:
                if nn == n:
                    continue
                if nn.id == n.id:
                    n.apply_unique_id()

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
            n.order = i
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
                if node.id in pool | {"0", "1", "2"}:
                    node.apply_unique_id()
                    # logger.debug("Regen: %s", node.id)
                else:
                    pool.add(node.id)
                    # logger.debug("Add: %s", node.id)


class CFNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'CFNodeTree'

    def __init__(self, *args, **kwargs) -> None:
        self.menus = kwargs.pop("menus", [])
        super().__init__(*args, **kwargs)


def reg_nodetree(identifier, cat_list, sub=False):
    if not cat_list:
        return

    def draw_node_item(self, context):
        layout = self.layout
        col = layout.column(align=True)
        for menu in self.category.menus:
            col.menu("NODE_MT_category%s" % menu.identifier)
        for item in self.category.items(context):
            item.draw(item, col, context)
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
        menu_type = type(f"NODE_MT_category{cat.identifier}", (bpy.types.Menu,), __data__)
        menu_types.append(menu_type)
        bpy.utils.register_class(menu_type)
    if sub:
        return

    def draw_add_menu(self, context):
        layout = self.layout

        for cat in cat_list:
            if cat.poll(context):
                layout.menu(f"NODE_MT_category{cat.identifier}")

    _node_categories[identifier] = (cat_list, draw_add_menu, menu_types)


def load_node(node_desc, root=""):
    node_cat = []
    for cat, nodes in node_desc.items():
        items = []
        menus = []
        for item in nodes["items"]:
            items.append(NodeItem(item))
        menus.extend(load_node(nodes.get("menus", {}), root=cat))
        cfn_cat = CFNodeCategory(f"{root}_{cat}", cat, items=items, menus=menus)
        node_cat.append(cfn_cat)
    return node_cat


clss = []

reg, unreg = bpy.utils.register_classes_factory(clss)


def rtnode_reg():
    clss.append(CFNodeTree)
    node_desc, node_clss, socket = parse_node()
    node_cat = load_node(node_desc=node_desc)
    clss.extend(node_clss)
    clss.extend(socket)
    nodes_reg()
    reg()
    reg_nodetree(TREE_NAME, node_cat)  # register_node_categories(TREE_NAME, node_cat)
    if CFNodeTree.reinit not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(CFNodeTree.reinit)


def rtnode_unreg():
    if CFNodeTree.reinit in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(CFNodeTree.reinit)
    if TREE_NAME in _node_categories:
        unregister_node_categories(TREE_NAME)
    unreg()
    nodes_unreg()
    clss.clear()


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