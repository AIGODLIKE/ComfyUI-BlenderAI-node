import bpy
import numpy as np
from mathutils import Vector

from ..utils import (
    get_image,
    resize_move_crop_image_buf,
    blender_image_to_image_buf_with_numpy,
    scale_to_matrix,
    image_buf_to_blender_image,
)


class TextureSpaceLocationRestore(bpy.types.Operator):
    bl_idname = "object.texture_space_location_restore"
    bl_label = "Texture Space Location Restore"
    bl_options = {'UNDO', 'REGISTER'}

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
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def execute(self, context):
        obj = context.object
        self.restore_scale(obj)
        return {"FINISHED"}

    @classmethod
    def restore_scale(cls, obj):
        scale = scale_to_matrix(obj.matrix_world.to_scale())
        dx, dy, dz = scale.inverted() @ obj.dimensions  # 物理尺寸
        obj.data.texspace_size = Vector((dx / 2, dy / 2, 0))


class TextureSpaceApply(bpy.types.Operator):
    bl_idname = "object.texture_space_apply"
    bl_label = "Texture Space Apply"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def execute(self, context):
        obj = context.object
        mesh = obj.data
        images = get_image(obj)
        print(self.bl_idname)
        if len(images) == 1:
            mat, node, image = images[0]
            iw, ih = image.size[:]

            scale = scale_to_matrix(obj.matrix_world.to_scale())
            dx, dy, dz = scale.inverted() @ obj.dimensions  # 物理尺寸
            lx, ly, lz = mesh.texspace_location[:]
            tsx, tsy, tsz = mesh.texspace_size[:]

            sx = tsx / (dx / 2)
            sy = tsy / (dy / 2)
            print("dx", dx, dy, dz)
            print("lx", lx, ly, lz)
            print("sx", sx, sy)
            print("iw ih", iw, ih)

            ox = np.floor(np.multiply(lx, np.divide(iw, dx)))
            oy = np.floor(np.multiply(ly, np.divide(ih, dy)))
            # ox = iw * lx
            # oy = ih * ly
            print("oxoy", ox, oy)

            image_buf = blender_image_to_image_buf_with_numpy(image)
            transformed_image_buf = resize_move_crop_image_buf(
                image_buf,
                position=(int(ox), int(oy)),
                scale_factor=(sx, sy),
                crop=Vector((0, 0, 0, 0)),
                background=(0, 0, 0, 0)
            )
            transformed_image_buf.write(r"C:\Users\32099\Desktop\output_sss.png")

            new_image = image_buf_to_blender_image(transformed_image_buf, f"{image.name}_Transformed")
            print("new_image", new_image)
            node.image = new_image

            TextureSpaceScaleRestore.restore_scale(obj)
            mesh.texspace_location = Vector((0, 0, 0))
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
