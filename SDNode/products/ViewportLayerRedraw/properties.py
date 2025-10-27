import bpy


class Layer(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Layer", description="Layer name", default="Layer 1")
    data: bpy.props.PointerProperty(type=bpy.types.Image)
    # path: bpy.props.StringProperty(name="Path", description="Path to the node tree", default="")


class SDNodeViewportLayerRedrawProperties(bpy.types.PropertyGroup):
    layers: bpy.props.CollectionProperty(type=Layer)

    def update_active_layer_index(self, context):
        print(self.active_layer_index)

    active_layer_index: bpy.props.IntProperty(name="Active Layer Index", description="Active Layer Index", default=0, update=update_active_layer_index)

    def get_layer_set_py(self) -> set[str]:
        return {layer.data for layer in self.layers}

    def get_active_image(self) -> bpy.types.Image | None:
        if self.active_layer_index < len(self.layers):
            return self.layers[self.active_layer_index].data
        return None

    prompt: bpy.props.StringProperty(name="Prompts",  default="A beautiful girl", )


def search_mat_textures_by_label(nt: bpy.types.NodeTree, label: str) -> set[bpy.types.ShaderNodeTexImage]:
    textures = set()
    for n in nt.nodes:
        if n.type == "TEX_IMAGE" and n.label == label and n.image:
            textures.add(n)
        elif n.type == "GROUP":
            textures.update(search_mat_textures_by_label(n.node_tree, label))
    return textures


def update_layer_list_timer():
    obj = bpy.context.active_object
    mat = obj.active_material if obj else None
    if not obj or not mat:
        return 1 / 30
    default_textures = {t.image for t in search_mat_textures_by_label(mat.node_tree, "")}
    prop: SDNodeViewportLayerRedrawProperties = bpy.context.scene.sdn_viewport_layer_redraw
    current_layer_set = prop.get_layer_set_py()
    if current_layer_set != default_textures:
        prop.layers.clear()
        for tex in sorted(default_textures, key=lambda t: t.name):
            item = prop.layers.add()
            item.name = tex.name
            item.data = tex
            # item.path = tex.path_from_id()
    return 1 / 30


clss = [
    Layer,
    SDNodeViewportLayerRedrawProperties,
]

reg, unreg = bpy.utils.register_classes_factory(clss)


def register():
    reg()
    bpy.types.Scene.sdn_viewport_layer_redraw = bpy.props.PointerProperty(type=SDNodeViewportLayerRedrawProperties)
    bpy.app.timers.register(update_layer_list_timer, persistent=True)


def unregister():
    unreg()
    del bpy.types.Scene.sdn_viewport_layer_redraw
    bpy.app.timers.unregister(update_layer_list_timer)
