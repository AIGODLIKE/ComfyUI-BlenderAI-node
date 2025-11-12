import bpy
from mathutils import Vector


class TextureSpaceLocationRestore(bpy.types.Operator):
    bl_idname = "object.texture_space_location_restore"
    bl_label = "Texture Space Location Restore"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def execute(self, context):
        context.object.data.texspace_location = Vector((0, 0, 0))
        return {"FINISHED"}


class TextureSpaceScaleRestore(bpy.types.Operator):
    bl_idname = "object.texture_space_scale_restore"
    bl_label = "Texture Space Scale Restore"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def execute(self, context):
        x, y, z = context.object.dimensions
        context.object.data.texspace_size = Vector((x / 2, y / 2, 0))
        return {"FINISHED"}


class TextureSpaceApply(bpy.types.Operator):
    bl_idname = "object.texture_space_apply"
    bl_label = "Texture Space Apply"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def execute(self, context):
        from ..utils import get_image
        images = get_image(context.object)
        if len(images) == 1:
            mat, node, image = images[0]
        else:
            self.report({"ERROR"}, "物体材质需要单张图像")

        return {"FINISHED"}


clss = [
    TextureSpaceLocationRestore,
    TextureSpaceScaleRestore,
    TextureSpaceApply,
]

reg, unreg = bpy.utils.register_classes_factory(clss)


def register():
    reg()


def unregister():
    unreg()
