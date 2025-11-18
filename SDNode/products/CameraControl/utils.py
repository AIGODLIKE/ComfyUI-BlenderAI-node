import bpy
from mathutils import Vector, Matrix
from bpy_extras.view3d_utils import location_3d_to_region_2d


def get_active_camera(context) -> bpy.types.Camera | None:
    """
    bpy.data.screens["Shading"].areas[5].spaces[0].camera 局部相机
    bpy.context.scene.camera.data
    """
    if camera := context.space_data.camera:
        return camera
    return context.scene.camera


def get_3d_camera_border(context) -> list[Vector] | None:
    if camera := get_active_camera(context):
        if camera is not None:
            matrix = exclude_scale_matrix(camera.matrix_world.copy())
            return [matrix @ v for v in camera.data.view_frame(scene=context.scene)]
    return None


def get_2d_camera_border(context, camera_border_3d=None) -> list[Vector] | None:
    """
    3--------------0
    |              |
    |              |
    |              |
    2--------------1
    """
    if camera_border_3d is None:
        camera_border_3d = get_3d_camera_border(context)
    return [location_3d_to_region_2d(context.region, context.space_data.region_3d, v) for v in camera_border_3d]


def exclude_scale_matrix(matrix: Matrix) -> Matrix:
    """排除矩阵的缩放"""
    location = Matrix.Translation(matrix.translation)
    rotation = matrix.to_quaternion().to_matrix().to_4x4()
    return location @ rotation
