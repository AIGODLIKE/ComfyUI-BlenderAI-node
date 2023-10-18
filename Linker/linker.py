# reference: https://github.com/ugorek000/VoronoiLinker
import bpy
import blf
import gpu
import gpu_extras
from bpy.app.translations import pgettext_iface
from math import sin, pi, cos, copysign
from mathutils import Vector
from bpy.types import Context
from ..translations.translation import ctxt
from ..SDNode.nodes import NodeBase, calc_hash_type, ctxt
from ..utils import _T2

SEARCH_DICT = {
    "LoaderMenu": [
        'CheckpointLoaderSimple',
    ],
    "ConditioningMenu": [
        'CLIPTextEncode',
    ],
}
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
    ixSkLastUsed = -1  # См. |4|
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
    vec = vec.copy() * UiScale()
    return Vector(bpy.context.region.view2d.view_to_region(vec.x, vec.y, clip=False))


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
    col = (drawCol[0]**pw, drawCol[1]**pw, drawCol[2]**pw, 1.0)
    DrawLine(pos1, (pos2[0], pos1[1]), 1, col, col)
    DrawLine((pos2[0], pos1[1]), pos2, 1, col, col)
    DrawLine(pos2, (pos1[0], pos2[1]), 1, col, col)
    DrawLine((pos1[0], pos2[1]), pos1, 1, col, col)
    # Мягкая дополнительная обвода, придающая красоты:
    col = (col[0], col[1], col[2], .375)
    lineOffset = 2.0
    DrawLine((pos1[0], pos1[1] - lineOffset), (pos2[0], pos1[1] - lineOffset), 1, col, col)
    DrawLine((pos2[0] + lineOffset, pos1[1]), (pos2[0] + lineOffset, pos2[1]), 1, col, col)
    DrawLine((pos2[0], pos2[1] + lineOffset), (pos1[0], pos2[1] + lineOffset), 1, col, col)
    DrawLine((pos1[0] - lineOffset, pos2[1]), (pos1[0] - lineOffset, pos1[1]), 1, col, col)
    # Уголки. Их маленький размер -- маскировка под тру-скругление:
    DrawLine((pos1[0] - lineOffset, pos1[1]), (pos1[0], pos1[1] - lineOffset), 1, col, col)
    DrawLine((pos2[0] + lineOffset, pos1[1]), (pos2[0], pos1[1] - lineOffset), 1, col, col)
    DrawLine((pos2[0] + lineOffset, pos2[1]), (pos2[0], pos2[1] + lineOffset), 1, col, col)
    DrawLine((pos1[0] - lineOffset, pos2[1]), (pos1[0], pos2[1] + lineOffset), 1, col, col)

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


def DrawSkText(pos, ofs, fgSk, fontSizeOverwrite=0):
    skCol = GetSkCol(fgSk.tg)
    txt = fgSk.name if fgSk.tg.bl_idname != 'NodeSocketVirtual' else pgettext_iface('Virtual')
    return DrawText(pos, ofs, txt, skCol, fontSizeOverwrite)


def GetSkCol(sk):  # Про NodeSocketUndefined см. |2|. Сокеты от потерянных деревьев не имеют "draw_color()".
    return sk.draw_color(bpy.context, sk.node) if sk.bl_idname != 'NodeSocketUndefined' else (1.0, 0.2, 0.2, 1.0)


def PowerArr4ToVec(arr, pw):
    return Vector((arr[0]**pw, arr[1]**pw, arr[2]**pw, arr[3]**pw))


def GetUniformColVec():
    return PowerArr4ToVec((0.632, 0.408, 0.174, 0.9), 1 / 2.2)


def DrawRectangle(pos1, pos2, col):
    DrawAreaFan(((pos1[0], pos1[1]), (pos2[0], pos1[1]), (pos2[0], pos2[1]), (pos1[0], pos2[1])), col)


def DrawSocketArea(sk, boxHeiBou, colfac=Vector((1.0, 1.0, 1.0, 1.0))):
    loc = RecrGetNodeFinalLoc(sk.node)
    pos1 = VecWorldToRegScale(Vector((loc.x, boxHeiBou[0])))
    pos2 = VecWorldToRegScale(Vector((loc.x + sk.node.width, boxHeiBou[1])))
    DrawRectangle(pos1, pos2, Vector((1.0, 1.0, 1.0, .075)) * colfac)


def DrawRing(pos, rd, siz=1, col=(1.0, 1.0, 1.0, .75), rotation=0.0, resolution=16):
    vpos = []
    vcol = []
    for cyc in range(resolution + 1):
        vpos.append((rd * cos(cyc * 2 * pi / resolution + rotation) + pos[0], rd * sin(cyc * 2 * pi / resolution + rotation) + pos[1]))
        vcol.append(col)
    DrawWay(vpos, vcol, siz)


def GetSkColPowVec(sk, pw):
    return PowerArr4ToVec(GetSkCol(sk), pw)


def DrawIsLinkedMarker(loc, ofs, skCol):
    ofs[0] += ((20 + 25) * 1.5 + 0) * copysign(1, ofs[0]) + 4
    vec = VecWorldToRegScale(loc)
    grayCol = 0.65
    col1 = (0.0, 0.0, 0.0, 0.5)  # Тень
    col2 = (grayCol, grayCol, grayCol, max(max(skCol[0], skCol[1]), skCol[2]) * .9 / 2)  # Прозрачная белая обводка
    col3 = (skCol[0], skCol[1], skCol[2], .925)  # Цветная основа

    def DrawMarkerBacklight(tgl, res=16):
        rot = pi / res if tgl else 0.0
        DrawRing((vec[0] + ofs[0], vec[1] + 5.0 + ofs[1]), 9.0, 3, col2, rot, res)
        DrawRing((vec[0] + ofs[0] - 5.0, vec[1] - 3.5 + ofs[1]), 9.0, 3, col2, rot, res)
    DrawRing((vec[0] + ofs[0] + 1.5, vec[1] + 3.5 + ofs[1]), 9.0, 3, col1)
    DrawRing((vec[0] + ofs[0] - 3.5, vec[1] - 5.0 + ofs[1]), 9.0, 3, col1)
    DrawMarkerBacklight(True)  # Маркер рисуется с артефактами "дырявых пикселей". Закостылить их дублированной отрисовкой с вращением.
    DrawMarkerBacklight(False)  # Но из-за этого нужно уменьшить альфу белой обводки в два раза.
    DrawRing((vec[0] + ofs[0], vec[1] + 5.0 + ofs[1]), 9.0, 1, col3)
    DrawRing((vec[0] + ofs[0] - 5.0, vec[1] - 3.5 + ofs[1]), 9.0, 1, col3)


def GetVecOffsetFromSk(sk, y=0.0):
    return Vector((20 * ((sk.is_output) * 2 - 1), y))


def DrawToolOftenStencil(cusorPos, list_twoTgSks,
                         isLineToCursor=False,
                         textSideFlip=False,
                         isDrawMarkersMoreTharOne=False,
                         isDrawOnlyArea=False):
    if not isDrawOnlyArea:
        length = len(list_twoTgSks)
        col1 = GetSkCol(list_twoTgSks[0].tg)
        col2 = Vector((1, 1, 1, 1))
        col2 = col2 if (isLineToCursor) or (length == 1) else GetSkCol(list_twoTgSks[1].tg)
        if length > 1:
            DrawStick(list_twoTgSks[0].pos + GetVecOffsetFromSk(list_twoTgSks[0].tg), list_twoTgSks[1].pos + GetVecOffsetFromSk(list_twoTgSks[1].tg), col1, col2)
        if isLineToCursor:
            DrawStick(list_twoTgSks[0].pos + GetVecOffsetFromSk(list_twoTgSks[0].tg), cusorPos, col1, col2)
    for li in list_twoTgSks:
        DrawSocketArea(li.tg, li.boxHeiBou, GetSkColPowVec(li.tg, 1 / 2.2))
        DrawWidePoint(li.pos + GetVecOffsetFromSk(li.tg), GetSkColPowVec(li.tg, 1 / 2.2))
    for li in list_twoTgSks:
        side = (textSideFlip * 2 - 1)
        txtDim = DrawSkText(cusorPos, (25 * (li.tg.is_output * 2 - 1) * side, -.5), li)
        if li.tg.links and not isDrawMarkersMoreTharOne or len(li.tg.links) > 1:
            DrawIsLinkedMarker(cusorPos, [txtDim[0] * (li.tg.is_output * 2 - 1) * side, 0], GetSkCol(li.tg))


def DrawAreaFan(vpos, col):
    gpu.state.blend_set('ALPHA')
    gpuArea.bind()
    gpuArea.uniform_float('color', col)
    gpu_extras.batch.batch_for_shader(gpuArea, 'TRI_FAN', {'pos': vpos}).draw(gpuArea)


def DrawCircle(pos, rd, col=(1.0, 1.0, 1.0, .75), resolution=54):
    vpos = ((pos[0], pos[1]), *((rd * cos(i * 2.0 * pi / resolution) + pos[0], rd * sin(i * 2.0 * pi / resolution) + pos[1]) for i in range(resolution + 1)))
    DrawAreaFan(vpos, col)


def DrawWidePoint(loc, colfac=Vector((1.0, 1.0, 1.0, 1.0)), resolution=54):
    pos = VecWorldToRegScale(loc)
    loc = Vector((loc.x + 6 * 1 * 1000, loc.y))
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


def PreviewerDrawCallback(self, context):
    if StartDrawCallbackStencil(self, context):
        return
    cusorPos = context.space_data.cursor_location
    if not self.foundGoalSkOut:
        return
    DrawToolOftenStencil(cusorPos, [self.foundGoalSkOut], isLineToCursor=True, textSideFlip=True, isDrawMarkersMoreTharOne=True)


def UiScale():
    return bpy.context.preferences.system.dpi / 72


def GetOpKey(txt):
    return bpy.context.window_manager.keyconfigs.user.keymaps['Node Editor'].keymap_items[txt].type


def RecrGetNodeFinalLoc(nd):
    return nd.location + RecrGetNodeFinalLoc(nd.parent) if nd.parent else nd.location


class FoundTarget:
    def __init__(self, tg=None, dist=0.0, pos=Vector((0.0, 0.0)), boxHeiBou=[0.0, 0.0], txt=''):
        self.tg = tg
        self.dist = dist
        self.pos = pos
        self.boxHeiBou = boxHeiBou
        self.name = txt


def GetNearestNodes(nodes, callPos):
    list_listNds = []
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
        list_listNds.append(FoundTarget(nd, field4.length, callPos - field4))
    list_listNds.sort(key=lambda a: a.dist)
    return list_listNds


def GetFromIoPuts(nd, side, callPos):
    list_result = []
    uiScale = UiScale()
    ndLocation = RecrGetNodeFinalLoc(nd).copy()
    ndDim = Vector(nd.dimensions / UiScale())
    pixel_size = bpy.context.preferences.system.pixel_size
    widget_unit = round(18.0 * uiScale + 0.002) + (2.0 * pixel_size)
    NODE_ITEM_SPACING_Y = int(0.1 * widget_unit)
    NODE_DYS = int(widget_unit / 2)
    NODE_DY = widget_unit
    # side == 1 为output socket
    # side == -1 为input socket
    if side == 1:  # 为output socket
        ndLocation.y = round(ndLocation.y - NODE_DY / uiScale)
        skLocCarriage = Vector((ndLocation.x + ndDim.x, ndLocation.y - NODE_DYS * 1.4 / uiScale))
    else:  # 为input socket
        # skLocCarriage = Vector((ndLocation.x, ndLocation.y - ndDim.y + 16))
        skLocCarriage = Vector((ndLocation.x, ndLocation.y - ndDim.y + NODE_DYS * 1.6 / uiScale))
    for sk in nd.outputs if side == 1 else reversed(nd.inputs):
        if not sk.enabled or sk.hide:
            continue
        goalPos = skLocCarriage.copy()
        box = (goalPos.y - 11, goalPos.y + 11)
        list_result.append(FoundTarget(sk,
                                       (callPos - skLocCarriage).length,
                                       goalPos,
                                       box,
                                       pgettext_iface(sk.name)))
        skLocCarriage.y = skLocCarriage.y * uiScale
        skLocCarriage.y -= NODE_DY * side
        skLocCarriage.y -= NODE_ITEM_SPACING_Y * side
        skLocCarriage.y = skLocCarriage.y / uiScale
    return list_result


def GetNearestSockets(nd, callPos):
    list_fgSksIn = []
    list_fgSksOut = []
    if not nd:
        return list_fgSksIn, list_fgSksOut
    if nd.bl_idname == 'NodeReroute':
        ndLocation = RecrGetNodeFinalLoc(nd)
        len = Vector(callPos - ndLocation).length
        list_fgSksIn.append(FoundTarget(nd.inputs[0], len, ndLocation, (-1, -1), pgettext_iface(nd.inputs[0].name)))
        list_fgSksOut.append(FoundTarget(nd.outputs[0], len, ndLocation, (-1, -1), pgettext_iface(nd.outputs[0].name)))
        return list_fgSksIn, list_fgSksOut
    list_fgSksIn = GetFromIoPuts(nd, -1, callPos)
    list_fgSksOut = GetFromIoPuts(nd, 1, callPos)
    list_fgSksIn.sort(key=lambda a: a.dist)
    list_fgSksOut.sort(key=lambda a: a.dist)
    return list_fgSksIn, list_fgSksOut


def ToolInvokeStencilPrepare(self, context, f):
    context.area.tag_redraw()
    self.handle = bpy.types.SpaceNodeEditor.draw_handler_add(f, (self, context), 'WINDOW', 'POST_PIXEL')
    context.window_manager.modal_handler_add(self)


class DRAG_LINK_MT_NODE_PIE(bpy.types.Menu):
    # label is displayed at the center of the pie menu.
    bl_label = ""

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
        box.separator(factor=0.02)
        br = box.row()
        br.scale_y = 0.25
        br.alignment = 'CENTER'
        br.label(text="Linker")
        col = box.column()
        # row.operator('comfy.node_search', text='', icon='VIEWZOOM')

        def find_node_by_type(sb):
            ft = bpy.context.scene.sdn.linker_socket
            is_out = bpy.context.scene.sdn.linker_socket_out
            if is_out:
                for inp_name in sb.inp_types:
                    inp = sb.inp_types[inp_name]
                    if not inp:
                        continue
                    socket = inp[0]
                    if isinstance(inp[0], list):
                        socket = calc_hash_type(inp[0])
                        continue
                    if socket in {"ENUM", "INT", "FLOAT", "STRING", "BOOLEAN"}:
                        continue
                    if socket == ft:
                        return True
            else:
                for out_type, _ in sb.out_types:
                    if out_type == ft:
                        return True
            return False
        sb_list = [sb for sb in NodeBase.__subclasses__() if find_node_by_type(sb)]
        lnum = min(4, len(sb_list))
        for count, sb in enumerate(sb_list):
            if count % lnum == 0:
                fcol = col.column_flow(columns=lnum, align=True)
                fcol.scale_y = 1.6
                fcol.ui_units_x = lnum * 7
            op = fcol.operator(DragLinkOps.bl_idname, text=_T2(sb.class_type), text_ctxt=ctxt)
            op.create_type = sb.class_type


class Comfyui_Swapper(bpy.types.Operator):
    bl_idname = 'comfy.swapper'
    bl_label = "Swapper"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        from ..SDNode.tree import TREE_TYPE
        return context.space_data.tree_type == TREE_TYPE

    def NextAssessment(self, context):
        self.foundGoalSkOut = None
        callPos = context.space_data.cursor_location

        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            nd = li.tg
            if nd.type in {"FRAME", "REROUTE"}:
                continue
            if nd.hide:
                continue
            if not [sk for sk in nd.outputs if not sk.hide and sk.enabled]:
                continue
            list_fgSksIn, list_fgSksOut = GetNearestSockets(nd, callPos)
            fgSkOut = list_fgSksOut[0] if list_fgSksOut else None
            fgSkIn = list_fgSksIn[0] if list_fgSksIn else None
            if not fgSkOut:
                self.foundGoalSkOut = fgSkIn
            elif not fgSkIn:
                self.foundGoalSkOut = fgSkOut
            else:
                self.foundGoalSkOut = fgSkOut if fgSkOut.dist < fgSkIn.dist else fgSkIn
            if self.foundGoalSkOut:
                break

    def invoke(self, context, event):
        self.keyType = GetOpKey(Comfyui_Swapper.bl_idname)
        if not context.space_data.edit_tree:
            return {'FINISHED'}
        Comfyui_Swapper.NextAssessment(self, context)
        ToolInvokeStencilPrepare(self, context, PreviewerDrawCallback)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        context.area.tag_redraw()
        match event.type:
            case 'MOUSEMOVE':
                if context.space_data.edit_tree:
                    Comfyui_Swapper.NextAssessment(self, context)
            case self.keyType | 'ESC':
                if event.value != 'RELEASE':
                    return {'RUNNING_MODAL'}
                bpy.types.SpaceNodeEditor.draw_handler_remove(self.handle, 'WINDOW')
                if not context.space_data.edit_tree:
                    return {'FINISHED'}
                if self.foundGoalSkOut:
                    DoPreview(context, self.foundGoalSkOut.tg)
                    # print(self.foundGoalSkOut.boxHeiBou)
                    # print(self.foundGoalSkOut.dist)
                    # print(self.foundGoalSkOut.name)
                    # print(self.foundGoalSkOut.pos)
                    # print(self.foundGoalSkOut.tg)
                    # print(self.foundGoalSkOut.tg.name)
                    # print(self.foundGoalSkOut.tg.type)
                    # print(self.foundGoalSkOut.tg.bl_idname)
                    # print(type(self.foundGoalSkOut.tg))
                    try:
                        # scene_node_pie = bpy.context.scene.node_pie
                        # scene_node_pie.vo_socket = self.foundGoalSkOut.tg.name
                        tg = self.foundGoalSkOut.tg
                        bpy.context.scene.sdn.linker_node = context.space_data.edit_tree.nodes.active.name
                        bpy.context.scene.sdn.linker_socket = tg.bl_idname
                        bpy.context.scene.sdn.linker_socket_out = tg.is_output
                        bpy.context.scene.sdn.linker_socket_index = tg.index
                        bpy.context.scene.sdn.linker_search_content = ""
                        bpy.ops.wm.call_menu_pie(name="DRAG_LINK_MT_NODE_PIE")
                        # bpy.ops.wm.call_menu_pie(name="COMFY_MT_NODE_PIE")
                        # bpy.ops.wm.call_menu_pie(name="COMFY_MT_NODE_PIE_VO")
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                return {'FINISHED'}
        return {'RUNNING_MODAL'}


class DragLinkOps(bpy.types.Operator):
    bl_idname = "sdn.drag_link"
    bl_description = "Drag Link"
    bl_label = "Drag Link"
    bl_translation_context = ctxt

    create_type: bpy.props.StringProperty()

    def execute(self, context: bpy.types.Context):
        self.select_nodes = []
        self.init_pos = context.space_data.cursor_location.copy()

        n = bpy.context.scene.sdn.linker_node
        socket = bpy.context.scene.sdn.linker_socket
        is_out = bpy.context.scene.sdn.linker_socket_out
        index = bpy.context.scene.sdn.linker_socket_index
        tree = bpy.context.space_data.edit_tree
        if not tree:
            return {"FINISHED"}
        node = tree.nodes.get(n, None)
        if not node:
            return {"FINISHED"}
        new_node = tree.nodes.new(self.create_type)
        self.select_nodes = [new_node]
        self.select_nodes[0].location = self.init_pos
        self.init_node_pos = self.init_pos
        find_socket = None
        if is_out:
            for out in node.outputs:
                if out.bl_idname == socket and out.index == index:
                    find_socket = out
                    break
            for inp in new_node.inputs:
                if inp.bl_idname == socket:
                    tree.links.new(find_socket, inp)
                    break
        else:
            for inp in node.inputs:
                if inp.bl_idname == socket and inp.index == index:
                    find_socket = inp
                    break
            for out in new_node.outputs:
                if out.bl_idname == socket:
                    tree.links.new(out, find_socket)
                    break
        bpy.context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event: bpy.types.Event):
        if not self.select_nodes:
            return {"FINISHED"}
        if event.type == "MOUSEMOVE":
            self.update_nodes_pos(event)

        # exit
        if event.value == "PRESS" and event.type in {"ESC", "LEFTMOUSE", "ENTER"}:
            return {"FINISHED"}
        if event.value == "PRESS" and event.type in {"RIGHTMOUSE"}:
            from ..ops import get_tree
            tree = get_tree()
            if tree:
                tree.safe_remove_nodes(self.select_nodes[:])
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    def update_nodes_pos(self, event):
        for n in self.select_nodes:
            n.location = self.init_node_pos + bpy.context.space_data.cursor_location - self.init_pos


list_addonKeymaps = []


def linker_register():
    bpy.utils.register_class(Comfyui_Swapper)
    bpy.utils.register_class(DRAG_LINK_MT_NODE_PIE)
    bpy.utils.register_class(DragLinkOps)
    blId, key, shift, ctrl, alt = Comfyui_Swapper.bl_idname, 'R', False, False, False
    kmi = newKeyMapNodeEditor.keymap_items.new(idname=blId, type=key, value='PRESS', shift=shift, ctrl=ctrl, alt=alt)
    list_addonKeymaps.append(kmi)


def linker_unregister():
    try:
        bpy.utils.unregister_class(Comfyui_Swapper)
        bpy.utils.unregister_class(DRAG_LINK_MT_NODE_PIE)
        bpy.utils.unregister_class(DragLinkOps)
        for li in list_addonKeymaps:
            newKeyMapNodeEditor.keymap_items.remove(li)
        list_addonKeymaps.clear()
    except BaseException:
        ...
