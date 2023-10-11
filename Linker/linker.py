import typing
import bpy
from bpy.types import Context
from ..translations.translation import ctxt
from ..SDNode.nodes import NodeBase, calc_hash_type, ctxt
from ..utils import _T2
from VoronoiLinker import VoronoiOpBase, voronoiAnchorName, Prefs, GetNearestNodes, voronoiPreviewResultNdName
from VoronoiLinker import GetNearestSockets, MinFromFgs, DoPreview, GetOpKey, ToolInvokeStencilPrepare, EditTreeIsNoneDrawCallback, VoronoiPreviewerDrawCallback

SEARCH_DICT = {
    "LoaderMenu": [
        'CheckpointLoaderSimple',
    ],
    "ConditioningMenu": [
        'CLIPTextEncode',
    ],
}


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
        lnum = 4
        count = 0
        for sb in NodeBase.__subclasses__():
            if not find_node_by_type(sb):
                continue
            if count % lnum == 0:
                fcol = col.column_flow(columns=lnum, align=True)
                fcol.scale_y = 1.6
            count += 1
            op = fcol.operator(DragLinkOps.bl_idname, text=_T2(sb.class_type), text_ctxt=ctxt)
            op.create_type = sb.class_type


class Comfyui_VoronoiSwaper(bpy.types.Operator, VoronoiOpBase):  # =VP=
    bl_idname = 'comfy.voronoi_previewer'
    bl_label = "Voronoi Previewer"
    bl_options = {'UNDO'}
    isPlaceAnAnchor: bpy.props.BoolProperty()

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'CFNodeTree'
        return context.space_data.tree_type == 'RHS_COMFY_NODETREE'

    def NextAssessment(self, context, isBoth=True):
        isAncohorExist = context.space_data.edit_tree.nodes.get(voronoiAnchorName)
        if isAncohorExist:
            isAncohorExist.label = voronoiAnchorName
        isAncohorExist = not not isAncohorExist
        self.foundGoalSkOut = None
        callPos = context.space_data.cursor_location
        vpRvEeOnlyLinkedTrigger = Prefs().vpRvEeOnlyLinkedTrigger

        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            nd = li.tg
            if nd.type == 'FRAME':
                continue
            if nd.hide and nd.type != 'REROUTE':
                continue
            if Prefs().vpRvEeIsSavePreviewResults:
                if nd.name == voronoiPreviewResultNdName:
                    continue
            if context.space_data.tree_type == 'GeometryNodeTree' and not isAncohorExist:
                if not [sk for sk in nd.outputs if (sk.type == 'GEOMETRY') and (not sk.hide) and (sk.enabled)]:
                    continue
            if not [sk for sk in nd.outputs if (not sk.hide) and (sk.enabled) and (sk.bl_idname != 'NodeSocketVirtual')]:
                continue
            if nd.type == 'REROUTE' and nd.name == voronoiAnchorName:
                continue
            list_fgSksIn, list_fgSksOut = GetNearestSockets(nd, callPos)

            for li in list_fgSksOut:

                if isBoth:
                    fgSkOut, fgSkIn = None, None
                    for li in list_fgSksOut:
                        if li.tg.bl_idname != 'NodeSocketVirtual':
                            fgSkOut = li
                            break
                    for li in list_fgSksIn:
                        if li.tg.bl_idname != 'NodeSocketVirtual':
                            fgSkIn = li
                            break
                    self.foundGoalSkOut = MinFromFgs(fgSkOut, fgSkIn)
                else:
                    if li.tg.bl_idname != 'NodeSocketVirtual' and (context.space_data.tree_type != 'GeometryNodeTree' or li.tg.type == 'GEOMETRY' or isAncohorExist):
                        if not vpRvEeOnlyLinkedTrigger or li.tg.is_linked:
                            self.foundGoalSkOut = li
                            break
            if not vpRvEeOnlyLinkedTrigger or self.foundGoalSkOut:
                break

        if self.foundGoalSkOut:
            if Prefs().vpIsLivePreview:
                self.foundGoalSkOut.tg = DoPreview(context, self.foundGoalSkOut.tg)
            if Prefs().vpRvEeIsColorOnionNodes:
                for nd in context.space_data.edit_tree.nodes:
                    nd.use_custom_color = False
                nd = self.foundGoalSkOut.tg.node
                for sk in nd.inputs:
                    for lk in sk.links:
                        lk.from_socket.node.use_custom_color = True
                        lk.from_socket.node.color = (.55, .188, .188)
                for sk in nd.outputs:
                    for lk in sk.links:
                        lk.to_socket.node.use_custom_color = True
                        lk.to_socket.node.color = (.188, .188, .5)

    def invoke(self, context, event):
        self.keyType = GetOpKey(Comfyui_VoronoiSwaper.bl_idname)
        if not context.space_data.edit_tree:
            if self.isPlaceAnAnchor:
                return {'FINISHED'}
            ToolInvokeStencilPrepare(self, context, EditTreeIsNoneDrawCallback)
            return {'RUNNING_MODAL'}
        if self.isPlaceAnAnchor:
            tree = context.space_data.edit_tree
            for nd in tree.nodes:
                nd.select = False
            ndRr = tree.nodes.get(voronoiAnchorName)
            tgl = not ndRr  # Метка для обработки при первом появлении.
            ndRr = ndRr or tree.nodes.new('NodeReroute')
            tree.nodes.active = ndRr
            ndRr.name = voronoiAnchorName
            ndRr.label = ndRr.name
            ndRr.location = context.space_data.cursor_location
            ndRr.select = True
            if tgl:
                nd = tree.nodes.new('NodeGroupInput')
                tree.links.new(nd.outputs[-1], ndRr.inputs[0])
                tree.nodes.remove(nd)
            return {'FINISHED'}
        else:
            self.foundGoalSkOut = None
            if Prefs().vpRvEeIsColorOnionNodes:
                self.dict_saveRestoreNodeColors = {}
                for nd in context.space_data.edit_tree.nodes:
                    self.dict_saveRestoreNodeColors[nd] = (nd.use_custom_color, nd.color.copy())
                    nd.use_custom_color = False
            Comfyui_VoronoiSwaper.NextAssessment(self, context)
            ToolInvokeStencilPrepare(self, context, VoronoiPreviewerDrawCallback)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        context.area.tag_redraw()
        match event.type:
            case 'MOUSEMOVE':
                if context.space_data.edit_tree:
                    Comfyui_VoronoiSwaper.NextAssessment(self, context)
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
                    if Prefs().vpRvEeIsColorOnionNodes:
                        for nd in context.space_data.edit_tree.nodes:
                            di = self.dict_saveRestoreNodeColors[nd]
                            nd.use_custom_color = di[0]
                            nd.color = di[1]
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
                        print(e)
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
    def f():
        try:
            from VoronoiLinker import globalVars
        except BaseException:
            return 1
        if globalVars.newKeyMapNodeEditor is None:
            return 1
        bpy.utils.register_class(Comfyui_VoronoiSwaper)
        bpy.utils.register_class(DRAG_LINK_MT_NODE_PIE)
        bpy.utils.register_class(DragLinkOps)
        blId, key, shift, ctrl, alt, dict_props = Comfyui_VoronoiSwaper.bl_idname, 'R', False, False, False, {'isPlaceAnAnchor': False}
        kmi = globalVars.newKeyMapNodeEditor.keymap_items.new(idname=blId, type=key, value='PRESS', shift=shift, ctrl=ctrl, alt=alt)
        for ti in dict_props:
            setattr(kmi.properties, ti, dict_props[ti])
        list_addonKeymaps.append(kmi)
    bpy.app.timers.register(f)


def linker_unregister():
    try:
        bpy.utils.unregister_class(Comfyui_VoronoiSwaper)
        bpy.utils.unregister_class(DRAG_LINK_MT_NODE_PIE)
        bpy.utils.unregister_class(DragLinkOps)
        from VoronoiLinker import globalVars
        for li in list_addonKeymaps:
            globalVars.newKeyMapNodeEditor.keymap_items.remove(li)
        list_addonKeymaps.clear()
    except BaseException:
        ...
