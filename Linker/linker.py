# reference: https://github.com/ugorek000/VoronoiLinker
from __future__ import annotations
import bpy
import blf
import gpu
import gpu_extras
from bpy.app.translations import pgettext_iface
from math import sin, pi, cos
from mathutils import Vector
from bpy.types import Context
from ..translations.translation import ctxt
from ..SDNode.nodes import NodeBase, calc_hash_type, ctxt
from ..utils import _T2
from ..preference import get_pref

gpuLine = gpu.shader.from_builtin('POLYLINE_SMOOTH_COLOR')
gpuArea = gpu.shader.from_builtin('UNIFORM_COLOR')

if "Node Editor" in bpy.context.window_manager.keyconfigs.addon.keymaps:
    newKeyMapNodeEditor = bpy.context.window_manager.keyconfigs.addon.keymaps["Node Editor"]
else:
    newKeyMapNodeEditor = bpy.context.window_manager.keyconfigs.addon.keymaps.new(name="Node Editor", space_type='NODE_EDITOR')


def GetSocketIndex(sk):
    return int(sk.path_from_id().split(".")[-1].split("[")[-1][:-1])


def DoPreview(context, goalSk):
    if not goalSk:
        return None
    context.space_data.edit_tree.nodes.active = goalSk.node

    def GetTrueTreeWay(context, nd):
        list_wayTreeNd = [[ph.node_tree, ph.node_tree.nodes.active] for ph in reversed(context.space_data.path)]
        for cyc in range(1, len(list_wayTreeNd)):
            li = list_wayTreeNd[cyc]
            if not li[1] or li[1].type != 'GROUP' or li[1].node_tree != list_wayTreeNd[cyc - 1][0]:
                li[1] = None
                for nd in li[0].nodes:
                    if nd.type == 'GROUP' and nd.node_tree == list_wayTreeNd[cyc - 1][0]:
                        li[1] = nd
                        break
        return list_wayTreeNd
    if GetSocketIndex(goalSk) == -1:
        return None
    curTree = context.space_data.edit_tree
    list_wayTreeNd = GetTrueTreeWay(context, goalSk.node)
    higWay = len(list_wayTreeNd) - 1
    isZeroPreviewGen = True  # См. |5|
    for cyc in range(higWay + 1):
        ndIn = None
        skOut = None
        skIn = None
        isPrecipice = (list_wayTreeNd[cyc][1] is None) and (cyc > 0)
        if (cyc != higWay) and (not isPrecipice):
            for nd in list_wayTreeNd[cyc][0].nodes:
                if (nd.type == 'GROUP_OUTPUT') and (nd.is_active_output):
                    ndIn = nd
        elif skIn:
            ndIn = skIn.node
        if isPrecipice:
            return goalSk
        # Определить сокет отправляющего нода
        if cyc == 0:
            skOut = goalSk
        for lk in skOut.links:
            if lk.to_node == ndIn:
                skIn = lk.to_socket
                ixSkLastUsed = GetSocketIndex(skIn)
        if skOut.type == 'RGBA' and skIn and len(skIn.links) > 0:
            if isZeroPreviewGen and len(skIn.links[0].from_socket.links) == 1:
                skIn = skIn.links[0].from_node.inputs.get("Color") or skIn.links[0].from_node.inputs.get("Base Color")
        if skOut and skIn:
            list_wayTreeNd[cyc][0].links.new(skOut, skIn)
    for nd in curTree.nodes:
        nd.select = False
    curTree.nodes.active = goalSk.node
    goalSk.node.select = True
    return goalSk


def VecWorldToRegScale(vec):
    vec = vec * UiScale()
    return Vector(bpy.context.region.view2d.view_to_region(vec.x, vec.y, clip=False))

def DrawLineRect(plt, prb, col1=(1.0, 1.0, 1.0, .75), col2=(1.0, 1.0, 1.0, .75), offset=8.0):
    """
        绘制线框矩形
    """
    pos1 = plt
    pos2 = prb
    #      1
    #     ----
    #   |      | 2
    # 4 |      |
    #     ----
    #       3
    DrawLine((pos1[0], pos1[1] + offset), (pos2[0], pos1[1] + offset), 1, col1, col2)
    DrawLine((pos2[0] + offset, pos1[1]), (pos2[0] + offset, pos2[1]), 1, col1, col2)
    DrawLine((pos2[0], pos2[1] - offset), (pos1[0], pos2[1] - offset), 1, col1, col2)
    DrawLine((pos1[0] - offset, pos2[1]), (pos1[0] - offset, pos1[1]), 1, col1, col2)
    # 1 /    \ 2
    #
    # 4 \    / 3
    DrawLine((pos1[0] - offset, pos1[1]), (pos1[0], pos1[1] + offset), 1, col1, col2)
    DrawLine((pos2[0] + offset, pos1[1]), (pos2[0], pos1[1] + offset), 1, col1, col2)
    DrawLine((pos2[0] + offset, pos2[1]), (pos2[0], pos2[1] - offset), 1, col1, col2)
    DrawLine((pos1[0] - offset, pos2[1]), (pos1[0], pos2[1] - offset), 1, col1, col2)

def DrawText(pos, ofs, txt, drawCol, fontSizeOverwrite=0):
    fontId = 1
    blf.enable(fontId, blf.SHADOW)
    muv = (0.0, 0.0, 0.0, 0.5)
    blf.shadow(fontId, 5, *muv)
    blf.shadow_offset(fontId, 2, -2)

    frameOffset = 0
    dsFontSize = 28
    blf.size(fontId, dsFontSize * (not fontSizeOverwrite) + fontSizeOverwrite)
    txtDim = (blf.dimensions(fontId, txt)[0], blf.dimensions(fontId, "█GJKLPgjklp!?")[1])
    pos = VecWorldToRegScale(pos)
    pos = (pos[0] - (txtDim[0] + frameOffset + 10) * (ofs[0] < 0) + (frameOffset + 1) * (ofs[0] > -1), pos[1] + frameOffset)
    pw = 1 / 1.975  # Осветлить текст. Почему 1.975 -- не помню.
    placePosY = round((txtDim[1] + frameOffset * 2) * ofs[1])  # Без округления красивость горизонтальных линий пропадет.
    pos1 = (pos[0] + ofs[0] - frameOffset, pos[1] + placePosY - frameOffset)
    pos2 = (pos[0] + ofs[0] + 10 + txtDim[0] + frameOffset, pos[1] + placePosY + txtDim[1] + frameOffset)
    gradientResolution = 12
    girderHeight = 1 / gradientResolution * (txtDim[1] + frameOffset * 2)
    def Fx(x, a, b): return ((x + b) / (b + 1))**.6 * (1 - a) + a
    for cyc in range(gradientResolution):
        DrawRectangle((pos1[0], pos1[1] + cyc * girderHeight), (pos2[0], pos1[1] + cyc * girderHeight + girderHeight), (drawCol[0] / 2, drawCol[1] / 2, drawCol[2] / 2, Fx(cyc / gradientResolution, .2, .05)))
    # Яркая основная обводка:
    plt = pos1[0], pos2[1]
    prb = pos2[0], pos1[1]
    col = (drawCol[0]**pw, drawCol[1]**pw, drawCol[2]**pw, 1.0)
    DrawLineRect(plt, prb, col, col, offset=1.5)
    col = (col[0], col[1], col[2], .375)
    DrawLineRect(plt, prb, col, col, offset=3)

    # Сам текст:
    blf.position(fontId, pos[0] + ofs[0] + 3.5, pos[1] + placePosY + txtDim[1] * .3, 0)
    blf.color(fontId, drawCol[0]**pw, drawCol[1]**pw, drawCol[2]**pw, 1.0)
    blf.draw(fontId, txt)
    return (txtDim[0] + frameOffset, txtDim[1] + frameOffset * 2)


def DrawWay(vpos, vcol, wid):
    gpu.state.blend_set('ALPHA')
    gpuLine.bind()
    gpuLine.uniform_float('lineWidth', wid * 2)
    gpu_extras.batch.batch_for_shader(gpuLine, 'LINE_STRIP', {'pos': vpos, 'color': vcol}).draw(gpuLine)


def DrawLine(pos1, pos2, siz=1, col1=(1.0, 1.0, 1.0, .75), col2=(1.0, 1.0, 1.0, .75)):
    DrawWay((pos1, pos2), (col1, col2), siz)


def DrawStick(pos1, pos2, col1, col2):
    DrawLine(VecWorldToRegScale(pos1), VecWorldToRegScale(pos2), 1, col1, col2)


def DrawSkText(pos, ofs, fgSk: Socket, fontSizeOverwrite=0):
    socket = fgSk.socket
    skCol = GetSkCol(socket)
    txt = fgSk.name if socket.bl_idname != 'NodeSocketVirtual' else pgettext_iface('Virtual')
    return DrawText(pos, ofs, txt, skCol, fontSizeOverwrite)


def GetSkCol(sk: bpy.types.NodeSocket):  # Про NodeSocketUndefined см. |2|. Сокеты от потерянных деревьев не имеют "draw_color()".
    return sk.draw_color(bpy.context, sk.node) if sk.bl_idname != 'NodeSocketUndefined' else (1.0, 0.2, 0.2, 1.0)


def PowerArr4ToVec(arr, pw):
    return Vector((arr[0]**pw, arr[1]**pw, arr[2]**pw, arr[3]**pw))


def GetUniformColVec():
    return PowerArr4ToVec((0.632, 0.408, 0.174, 0.9), 1 / 2.2)


def DrawRectangle(pos1, pos2, col):
    DrawAreaFan(((pos1[0], pos1[1]), (pos2[0], pos1[1]), (pos2[0], pos2[1]), (pos1[0], pos2[1])), col)


def DrawSocketArea(sk: bpy.types.NodeSocket, boxHeiBou, colfac=Vector((1.0, 1.0, 1.0, 1.0))):
    loc = RecrGetNodeFinalLoc(sk.node)
    pos1 = VecWorldToRegScale(Vector((loc.x, boxHeiBou[0])))
    pos2 = VecWorldToRegScale(Vector((loc.x + sk.node.width, boxHeiBou[1])))
    DrawRectangle(pos1, pos2, Vector((1.0, 1.0, 1.0, .075)) * colfac)


def GetSkColPowVec(sk, pw):
    return PowerArr4ToVec(GetSkCol(sk), pw)


def GetVecOffsetFromSk(sk: bpy.types.NodeSocket, y=0.0):
    return Vector((20 * ((sk.is_output) * 2 - 1), y))


def DrawToolOftenStencil(cusorPos, list_twoTgSks: list[Socket],
                         isLineToCursor=False,
                         textSideFlip=False,
                         isDrawOnlyArea=False):
    if not isDrawOnlyArea:
        length = len(list_twoTgSks)
        col1 = GetSkCol(list_twoTgSks[0].socket)
        col2 = Vector((1, 1, 1, 1))
        col2 = col2 if (isLineToCursor) or (length == 1) else GetSkCol(list_twoTgSks[1].socket)
        if length > 1:
            DrawStick(list_twoTgSks[0].pos + GetVecOffsetFromSk(list_twoTgSks[0].socket), list_twoTgSks[1].pos + GetVecOffsetFromSk(list_twoTgSks[1].socket), col1, col2)
        if isLineToCursor:
            DrawStick(list_twoTgSks[0].pos + GetVecOffsetFromSk(list_twoTgSks[0].socket), cusorPos, col1, col2)
    for li in list_twoTgSks:
        DrawSocketArea(li.socket, li.boxHeiBou, GetSkColPowVec(li.socket, 1 / 2.2))
        DrawWidePoint(li.pos + GetVecOffsetFromSk(li.socket), GetSkColPowVec(li.socket, 1 / 2.2))
    for li in list_twoTgSks:
        side = (textSideFlip * 2 - 1)
        DrawSkText(cusorPos, (25 * (li.socket.is_output * 2 - 1) * side, -.5), li)


def DrawAreaFan(vpos, col):
    gpu.state.blend_set('ALPHA')
    gpuArea.bind()
    gpuArea.uniform_float('color', col)
    gpu_extras.batch.batch_for_shader(gpuArea, 'TRI_FAN', {'pos': vpos}).draw(gpuArea)


def DrawCircle(pos, rd, col=(1.0, 1.0, 1.0, .75), resolution=54):
    vpos = ((pos[0], pos[1]), *((rd * cos(i * 2.0 * pi / resolution) + pos[0], rd * sin(i * 2.0 * pi / resolution) + pos[1]) for i in range(resolution + 1)))
    DrawAreaFan(vpos, col)


def DrawWidePoint(loc, colfac=Vector((1.0, 1.0, 1.0, 1.0)), resolution=54, rd=0):
    pos = VecWorldToRegScale(loc)
    loc = Vector((loc.x + 6 * 1 * 1000, loc.y))
    if rd == 0:
        rd = (VecWorldToRegScale(loc)[0] - pos[0]) / 1000
    col1 = Vector((0.5, 0.5, 0.5, 0.4))
    col2 = col1
    col3 = Vector((1.0, 1.0, 1.0, 1.0))
    rd = (rd * rd + 10)**0.5
    DrawCircle(pos, rd + 3.0, col1 * colfac, resolution)
    DrawCircle(pos, rd, col2 * colfac, resolution)
    DrawCircle(pos, rd / 1.5, col3 * colfac, resolution)


def StartDrawCallbackStencil(self, context):
    gpuLine.uniform_float('viewportSize', gpu.state.viewport_get()[2:4])
    gpuLine.uniform_bool('lineSmooth', True)


def PreviewerDrawCallback(self, context: bpy.types.Context):
    StartDrawCallbackStencil(self, context)
    cusorPos = context.space_data.cursor_location
    if not P.foundSocket:
        return
    DrawToolOftenStencil(cusorPos, [P.foundSocket], isLineToCursor=True, textSideFlip=True)


def UiScale():
    return bpy.context.preferences.system.dpi / 72


def GetOpKey(txt):
    return bpy.context.window_manager.keyconfigs.user.keymaps['Node Editor'].keymap_items[txt].type


def RecrGetNodeFinalLoc(nd: bpy.types.Node):
    return nd.location + RecrGetNodeFinalLoc(nd.parent) if nd.parent else nd.location


class Socket:
    def __init__(self, socket=None, dist=0.0, pos=Vector((0.0, 0.0)), boxHeiBou=[0.0, 0.0], txt=''):
        self.socket: bpy.types.NodeSocket = socket
        self.dist = dist
        self.pos = pos
        self.boxHeiBou = boxHeiBou
        self.name = txt


def GetNearestNodes(nodes: list[bpy.types.Node], callPos):
    all_nodes = []
    for nd in nodes:
        ndLocation = RecrGetNodeFinalLoc(nd)
        ndSize = Vector((4, 4)) if nd.bl_idname == 'NodeReroute' else nd.dimensions / UiScale()
        ndLocation = ndLocation if nd.bl_idname == 'NodeReroute' else ndLocation + ndSize / 2 * Vector((1, -1))
        field0 = callPos - ndLocation
        field1 = Vector(((field0.x > 0) * 2 - 1, (field0.y > 0) * 2 - 1))
        field0 = Vector((abs(field0.x), abs(field0.y))) - ndSize / 2
        field2 = Vector((max(field0.x, 0), max(field0.y, 0)))
        field3 = Vector((abs(field0.x), abs(field0.y)))
        field3 = field3 * Vector((field3.x <= field3.y, field3.x > field3.y))
        field3 = field3 * -((field2.x + field2.y) == 0)
        field4 = (field2 + field3) * field1
        all_nodes.append((nd, field4.length))
    all_nodes.sort(key=lambda a: a[1])
    return all_nodes


def SocketsFromNode(nd: bpy.types.Node, side, callPos) -> list[Socket]:
    """
        从Node获取输入输出的Socket列表
        nd: 节点
        side: 为1代表out, -1代表in
    """
    lstResult = []
    uiScale = UiScale()
    ndLocation = RecrGetNodeFinalLoc(nd).copy()
    ndDim = Vector(nd.dimensions / uiScale)
    pixel_size = bpy.context.preferences.system.pixel_size
    widget_unit = round(18.0 * uiScale + 0.002) + (2.0 * pixel_size)
    NODE_ITEM_SPACING_Y = int(0.1 * widget_unit)
    NODE_DYS = int(widget_unit / 2)
    NODE_DY = widget_unit
    if side == 1:  # out
        ndLocation.y = round(ndLocation.y - NODE_DY / uiScale)
        skLocCarriage = Vector((ndLocation.x + ndDim.x, ndLocation.y - NODE_DYS * 1.4 / uiScale))
    else:  # in
        skLocCarriage = Vector((ndLocation.x, ndLocation.y - ndDim.y + NODE_DYS * 1.6 / uiScale))
    for sk in nd.outputs if side == 1 else reversed(nd.inputs):
        if not sk.enabled or sk.hide:
            continue
        pos = skLocCarriage.copy()
        box = (pos.y - 11, pos.y + 11)
        dist = (callPos - skLocCarriage).length
        lstResult.append(Socket(sk, dist, pos, box, pgettext_iface(sk.name)))
        skLocCarriage.y = skLocCarriage.y * uiScale
        skLocCarriage.y -= NODE_DY * side
        skLocCarriage.y -= NODE_ITEM_SPACING_Y * side
        skLocCarriage.y = skLocCarriage.y / uiScale
    return lstResult

def GetNodeCenterPos(node):
    """
        获取节点正中位置
    """
    ndLocation = RecrGetNodeFinalLoc(node).copy()
    ndDim = Vector(node.dimensions / UiScale())
    ndDim.x *= -1
    cPos = ndLocation - ndDim * 0.5
    return cPos

def GetNodeRBPos(node):
    """
        获取节点右下位置
    """
    ndLocation = RecrGetNodeFinalLoc(node).copy()
    ndDim = Vector(node.dimensions / UiScale())
    ndDim.x *= -1
    pos = ndLocation - ndDim
    return pos

def DistToNodeCenter(node, pos):
    """
        计算pos到节点正中心的距离
    """
    cPos = GetNodeCenterPos(node)
    return (pos - cPos).length

def GetNearestSockets(nd: bpy.types.Node, callPos):
    list_fgSksIn = []
    list_fgSksOut = []
    if not nd:
        return list_fgSksIn, list_fgSksOut
    if nd.bl_idname == "NodeReroute":
        ndLocation = RecrGetNodeFinalLoc(nd)
        len = Vector(callPos - ndLocation).length
        list_fgSksIn.append(Socket(nd.inputs[0], len, ndLocation, (-1, -1), pgettext_iface(nd.inputs[0].name)))
        list_fgSksOut.append(Socket(nd.outputs[0], len, ndLocation, (-1, -1), pgettext_iface(nd.outputs[0].name)))
        return list_fgSksIn, list_fgSksOut
    list_fgSksIn = SocketsFromNode(nd, -1, callPos)
    list_fgSksOut = SocketsFromNode(nd, 1, callPos)
    list_fgSksIn.sort(key=lambda a: a.dist)
    list_fgSksOut.sort(key=lambda a: a.dist)
    return list_fgSksIn, list_fgSksOut


class DRAG_LINK_PT_PANEL(bpy.types.Panel):
    bl_label = ""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context: Context):
        return hasattr(context.space_data, "edit_tree")

    def draw(self, context: Context):
        DRAG_LINK_MT_NODE_PIE.draw(self, context)


class DRAG_LINK_MT_NODE_PIE(bpy.types.Menu):
    # label is displayed at the center of the pie menu.
    bl_label = ""
    sb_list = []

    @classmethod
    def poll(cls, context: Context):
        return hasattr(context.space_data, "edit_tree")

    @staticmethod
    def update_sb_list():
        def find_node_by_type(sb):
            fsocket = P.foundSocket.socket
            if not fsocket:
                return False
            if fsocket.is_output:
                for inp_name in sb.inp_types:
                    inp = sb.inp_types[inp_name]
                    if not inp:
                        continue
                    inp_type = inp[0]
                    if isinstance(inp[0], list):
                        inp_type = calc_hash_type(inp[0])
                        continue
                    if inp_type in {"ENUM", "INT", "FLOAT", "STRING", "BOOLEAN"}:
                        continue
                    if inp_type == fsocket.bl_idname:
                        return True
            else:
                for out_type, _ in sb.out_types:
                    if out_type == fsocket.bl_idname:
                        return True
            return False
        sb_list = [sb for sb in NodeBase.__subclasses__() if find_node_by_type(sb)]
        DRAG_LINK_MT_NODE_PIE.sb_list = sb_list

    @staticmethod
    def draw_prepare():
        bpy.ops.sdn.mouse_pos_rec("INVOKE_DEFAULT")
        DRAG_LINK_MT_NODE_PIE.update_sb_list()
        pref = get_pref()
        pref.count_page_current = 0
        c = pref.drag_link_result_count_col
        r = pref.drag_link_result_count_row
        pref.count_page_total = len(DRAG_LINK_MT_NODE_PIE.sb_list) // (c * r)

    def draw(self, context):
        layout = self.layout
        # Left
        pie = layout.menu_pie()
        col = pie.column()
        box = col.box()
        box.separator(factor=0.02)

        row = box.row()
        row.scale_y = 0.25
        row.alignment = 'CENTER'
        row.label(text="Search")
        col = box.column()
        col.scale_x = 2
        col.scale_y = 4
        col.operator("sdn.node_search", text='', icon='VIEWZOOM')

        # Right
        pie = layout.menu_pie()

        # Down
        pie = layout.menu_pie()

        # up
        pie = layout.menu_pie()
        col = pie.column()
        box = col.box()
        box.column()
        br = box.row()
        br.scale_y = 0.5
        br.alignment = "CENTER"
        br.label(text="Linker")
        box.column()

        pref = get_pref()
        row = box.box().row(align=True)
        r1 = row.split(factor=0.15, align=True)
        r1.scale_y = 1.5
        # 15 70 15
        left = r1.column()
        left.prop(pref, "count_page_prev", text="", icon="TRIA_LEFT")
        left.enabled = pref.count_page_current > 0
        r2 = r1.split(factor=70 / 85, align=True)
        center = r2.row(align=True)
        center.alignment = "CENTER"
        center.alert = True
        center.label(text=f"{_T2('Drag Link Result Page Current')} {pref.count_page_current+1}")
        right = r2.column()
        right.prop(pref, "count_page_next", text="", icon="TRIA_RIGHT")
        right.enabled = pref.count_page_current < pref.count_page_total

        # row = box.row()
        # row.label(text="Drag Link Result Count", text_ctxt=ctxt)
        # row.prop(pref, "drag_link_result_count_col", text="", text_ctxt=ctxt)
        # row.prop(pref, "drag_link_result_count_row", text="", text_ctxt=ctxt)

        col = box.column()
        # row.operator('comfy.node_search', text='', icon='VIEWZOOM')
        c = pref.drag_link_result_count_col
        r = pref.drag_link_result_count_row
        p = pref.count_page_current
        range_start, range_end = p * c * r, (p + 1) * c * r
        sb_list = DRAG_LINK_MT_NODE_PIE.sb_list
        for count, sb in enumerate(sb_list[range_start: range_end]):
            if count % c == 0:
                fcol = col.column_flow(columns=c, align=True)
                fcol.scale_y = 1.6
                fcol.ui_units_x = c * 7
            op = fcol.operator(DragLinkOps.bl_idname, text=_T2(sb.class_type), text_ctxt=ctxt)
            op.create_type = sb.class_type


class P:
    x = 0
    y = 0
    ori_x = 0
    ori_y = 0
    foundSocket: Socket = None


class Comfyui_Swapper(bpy.types.Operator):
    bl_idname = "comfy.swapper"
    bl_label = "Swapper"
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        from ..SDNode.tree import TREE_TYPE
        return context.space_data.tree_type == TREE_TYPE

    def NextAssessment(self, context):
        P.foundSocket = None
        callPos = context.space_data.cursor_location

        for nd, _ in GetNearestNodes(self.tree.nodes, callPos):
            if nd.type in {"FRAME", "REROUTE"}:
                continue
            if nd.hide:
                continue
            list_fgSksIn, list_fgSksOut = GetNearestSockets(nd, callPos)
            fgSkOut = list_fgSksOut[0] if list_fgSksOut else None
            fgSkIn = list_fgSksIn[0] if list_fgSksIn else None
            if not fgSkOut:
                P.foundSocket = fgSkIn
            elif not fgSkIn:
                P.foundSocket = fgSkOut
            else:
                P.foundSocket = fgSkOut if fgSkOut.dist < fgSkIn.dist else fgSkIn
            if P.foundSocket:
                break

    def invoke(self, context, event):
        self.tree: bpy.types.NodeTree = context.space_data.edit_tree
        if self.action == "DRAW":
            bpy.context.window_manager.popup_menu_pie(event, DRAG_LINK_MT_NODE_PIE.draw)
            return {"FINISHED"}
        P.foundSocket = None
        self.keyType = GetOpKey(self.__class__.bl_idname)
        if not self.tree:
            return {'FINISHED'}
        Comfyui_Swapper.NextAssessment(self, context)
        context.area.tag_redraw()
        f = PreviewerDrawCallback
        self.handle = bpy.types.SpaceNodeEditor.draw_handler_add(f, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context: Context):
        return {"FINISHED"}

    def modal(self, context, event):
        context.area.tag_redraw()
        match event.type:
            case 'MOUSEMOVE':
                if self.tree:
                    Comfyui_Swapper.NextAssessment(self, context)
            case "ESC":
                return {"FINISHED"}
            case self.keyType:
                if event.value != 'RELEASE':
                    return {"RUNNING_MODAL"}
                bpy.types.SpaceNodeEditor.draw_handler_remove(self.handle, 'WINDOW')
                if not self.tree:
                    return {"FINISHED"}
                if P.foundSocket:
                    DoPreview(context, P.foundSocket.socket)
                    try:
                        # 计算结果中所有的 符合node
                        DRAG_LINK_MT_NODE_PIE.draw_prepare()
                        bpy.ops.comfy.swapper("INVOKE_DEFAULT", action="DRAW")
                        # res = bpy.context.window_manager.invoke_props_dialog(self, width=400)
                        # print(res)
                        # return res
                        # bpy.context.window_manager.popup_menu_pie(event, DRAG_LINK_MT_NODE_PIE.draw)
                        # bpy.ops.wm.call_panel(name="DRAG_LINK_PT_PANEL", keep_open=False)
                        # bpy.ops.wm.call_menu_pie(name="DRAG_LINK_MT_NODE_PIE", keep_open=False)
                        # bpy.ops.wm.call_menu_pie(name="COMFY_MT_NODE_PIE")
                        # bpy.ops.wm.call_menu_pie(name="COMFY_MT_NODE_PIE_VO")
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                return {"FINISHED"}
        return {'RUNNING_MODAL'}


class Comfyui_Linker(bpy.types.Operator):
    bl_idname = "comfy.linker"
    bl_label = "Linker"
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        from ..SDNode.tree import TREE_TYPE
        return context.space_data.tree_type == TREE_TYPE

    def NextAssessment(self, context):
        callPos = context.space_data.cursor_location
        for nd, _ in GetNearestNodes(self.tree.nodes, callPos):
            if nd.type in {"FRAME", "REROUTE"}:
                continue
            if nd.hide:
                continue
            if nd != self.from_node:
                self.to_node = nd
                length = DistToNodeCenter(nd, callPos)
                if length > 50:
                    self.to_node = None
                break

    def find_link_pairs(self):
        if not self.from_node or not self.to_node:
            return [], []
        callPos = bpy.context.space_data.cursor_location
        find_sockets1 = SocketsFromNode(self.from_node, 1, callPos)
        find_sockets2 = SocketsFromNode(self.to_node, -1, callPos)
        find_sockets2.reverse()
        pair_from = []
        pair_to = []
        si1, si2 = 0, 0
        while si1 < len(find_sockets1) and si2 < len(find_sockets2):
            s1 = find_sockets1[si1]
            for s2 in find_sockets2[si2:]:
                if s2.socket.bl_idname == s1.socket.bl_idname:
                    pair_from.append(s1)
                    pair_to.append(s2)
                    si2 += 1
                    break
            si1 += 1
        return pair_from, pair_to

    def invoke(self, context, event):
        self.tree: bpy.types.NodeTree = context.space_data.edit_tree
        if not self.tree:
            return {'FINISHED'}
        self.from_node = self.tree.nodes.active
        self.to_node = None
        if not self.from_node:
            return {"FINISHED"}
        bpy.ops.node.select_all(action="DESELECT")
        self.from_node.select = True
        self.keyType = GetOpKey(self.__class__.bl_idname)
        self.NextAssessment(context)
        context.area.tag_redraw()

        def f(self: Comfyui_Linker, context: bpy.types.Context):
            StartDrawCallbackStencil(self, context)
            callPos = context.space_data.cursor_location
            pf, pt = self.find_link_pairs()
            length = 99999
            if self.to_node:
                length = DistToNodeCenter(self.to_node, callPos)
                nd = self.to_node
                cPos = GetNodeCenterPos(nd)
                DrawWidePoint(cPos, Vector((0, .7, .7, .75)), rd=40)
                LT = VecWorldToRegScale(nd.location)
                RB = VecWorldToRegScale(GetNodeRBPos(nd))
                col = (0, .7, 0, .75)
                DrawLineRect(LT, RB, col, col, offset=4)
            # 距离 0-20: 吸附到socket
            if pf and pt and length < 20:
                for s1, s2 in zip(pf, pt):
                    DrawToolOftenStencil(s2.pos, [s1], isLineToCursor=True, textSideFlip=True)
                DrawWidePoint(cPos, Vector((.7, .7, 0, 1)), rd=40)
                # DrawCircle(VecWorldToRegScale(cPos), 20 * UiScale(), (.7, .7, 0, .75))
                return
            # 计算中点
            find_sockets1 = SocketsFromNode(self.from_node, 1, callPos)
            mid = Vector((0, 0))
            for socket in find_sockets1:
                mid += socket.pos
            mid /= len(find_sockets1)
            
            # 距离20-50: 不吸附, 但显示匹配变化
            if pf and pt and 20 <= length:
                for socket in pf:
                    DrawToolOftenStencil(callPos + (socket.pos - mid), [socket], isLineToCursor=True, textSideFlip=True)
            else:
                # 没有找到对应的连接:
                # 绘制多个socket -> socket的 圆圈-直线-圆圈
                # 绘制socket的高亮
                # 如果没找到比较近的node
                for socket in find_sockets1:
                    DrawToolOftenStencil(callPos + (socket.pos - mid), [socket], isLineToCursor=True, textSideFlip=True)

        self.handle = bpy.types.SpaceNodeEditor.draw_handler_add(f, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        context.area.tag_redraw()
        if event.type == "LEFTMOUSE":
            for s1, s2 in zip(*self.find_link_pairs()):
                self.tree.links.new(s1.socket, s2.socket)
        match event.type:
            case "MOUSEMOVE":
                self.NextAssessment(context)
            case "ESC" | "LEFTMOUSE" | "RIGHTMOUSE":
                self.clear()
                return {"FINISHED"}
        return {'RUNNING_MODAL'}

    def clear(self):
        bpy.types.SpaceNodeEditor.draw_handler_remove(self.handle, 'WINDOW')


class MousePosRec(bpy.types.Operator):
    bl_idname = "sdn.mouse_pos_rec"
    bl_label = "Mouse Pos Rec"
    bl_options = {'REGISTER', 'UNDO'}
    action: bpy.props.StringProperty()

    def invoke(self, context, event):
        if self.action == "ORI":
            P.ori_x = event.mouse_x
            P.ori_y = event.mouse_y
        else:
            P.x = event.mouse_x
            P.y = event.mouse_y
        self.action = ""
        return {"FINISHED"}


class DragLinkOps(bpy.types.Operator):
    bl_idname = "sdn.drag_link"
    bl_description = "Drag Link"
    bl_label = "Drag Link"
    bl_translation_context = ctxt

    create_type: bpy.props.StringProperty()

    def execute(self, context: bpy.types.Context):
        self.init_pos = context.space_data.cursor_location.copy()
        tree: bpy.types.NodeTree = bpy.context.space_data.edit_tree
        if not tree or not P.foundSocket:
            return {"FINISHED"}
        fsocket = P.foundSocket.socket
        if not fsocket:
            return {"FINISHED"}
        new_node: bpy.types.Node = tree.nodes.new(self.create_type)
        bpy.ops.node.select_all(action='DESELECT')
        new_node.select = True
        self.select_node = new_node
        tree.nodes.active = new_node
        self.select_node.location = self.init_pos
        self.init_node_pos = self.init_pos

        if fsocket.is_output:
            for inp in new_node.inputs:
                if inp.bl_idname == fsocket.bl_idname:
                    tree.links.new(fsocket, inp)
                    break
        else:
            for out in new_node.outputs:
                if out.bl_idname == fsocket.bl_idname:
                    tree.links.new(out, fsocket)
                    break
        bpy.context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event: bpy.types.Event):
        if not self.select_node:
            return {"FINISHED"}
        if event.type == "MOUSEMOVE":
            self.update_node_pos(event)

        # exit
        if event.value == "PRESS" and event.type in {"ESC", "LEFTMOUSE", "ENTER"}:
            return {"FINISHED"}
        if event.value == "PRESS" and event.type in {"RIGHTMOUSE"}:
            from ..ops import get_tree
            tree = get_tree()
            if tree:
                tree.safe_remove_nodes([self.select_node])
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    def update_node_pos(self, event):
        self.select_node.location = self.init_node_pos + bpy.context.space_data.cursor_location - self.init_pos


list_addonKeymaps = []


def linker_register():
    bpy.utils.register_class(Comfyui_Swapper)
    bpy.utils.register_class(Comfyui_Linker)
    bpy.utils.register_class(MousePosRec)
    bpy.utils.register_class(DRAG_LINK_PT_PANEL)
    bpy.utils.register_class(DRAG_LINK_MT_NODE_PIE)
    bpy.utils.register_class(DragLinkOps)
    blId, key, shift, ctrl, alt = Comfyui_Swapper.bl_idname, 'R', False, False, False
    kmi = newKeyMapNodeEditor.keymap_items.new(idname=blId, type=key, value='PRESS', shift=shift, ctrl=ctrl, alt=alt)
    list_addonKeymaps.append(kmi)
    blId, key = Comfyui_Linker.bl_idname, "D"
    kmi = newKeyMapNodeEditor.keymap_items.new(idname=blId, type=key, value='PRESS', shift=shift, ctrl=ctrl, alt=alt)
    list_addonKeymaps.append(kmi)


def linker_unregister():
    try:
        bpy.utils.unregister_class(Comfyui_Swapper)
        bpy.utils.unregister_class(Comfyui_Linker)
        bpy.utils.unregister_class(MousePosRec)
        bpy.utils.unregister_class(DRAG_LINK_PT_PANEL)
        bpy.utils.unregister_class(DRAG_LINK_MT_NODE_PIE)
        bpy.utils.unregister_class(DragLinkOps)
        for li in list_addonKeymaps:
            newKeyMapNodeEditor.keymap_items.remove(li)
        list_addonKeymaps.clear()
    except BaseException:
        ...
