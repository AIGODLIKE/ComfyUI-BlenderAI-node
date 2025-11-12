import bpy
from mathutils import Vector, Matrix
from mathutils.geometry import intersect_line_line
from ..utils import exclude_scale_matrix


def camera_to_board(context, camera, board):
    matrix = exclude_scale_matrix(board.matrix_world.copy())
    camera.matrix_world = matrix

    # board
    bound_box = [board.matrix_world @ Vector(i[:]) for i in board.bound_box[:]]
    top_point = (bound_box[3] + bound_box[7]) / 2
    left_point = (bound_box[0] + bound_box[3]) / 2
    center = (bound_box[3] + bound_box[4]) / 2

    bound_box_offset = [(board.matrix_world @ Matrix.Translation(Vector((0, 0, -1)))) @ Vector(i[:]) for i in
                        board.bound_box[:]]
    top_offset_point = (bound_box_offset[3] + bound_box_offset[7]) / 2
    left_offset_point = (bound_box_offset[0] + bound_box_offset[3]) / 2

    # camera
    view_frame = [camera.matrix_world @ i for i in camera.data.view_frame(scene=context.scene)]
    camera_top_point = (view_frame[0] + view_frame[3]) / 2
    camera_left_point = (view_frame[2] + view_frame[3]) / 2

    itl = intersect_line_line(center, camera_top_point, top_point, top_offset_point)
    ill = intersect_line_line(center, camera_left_point, left_point, left_offset_point)
    intersect_top = itl[0] if itl else None
    intersect_left = ill[0] if ill else None

    offset_top = top_point - intersect_top
    offset_left = left_point - intersect_left
    print(f"bound_box = {bound_box}")
    print(f"top_point = {top_point.__repr__()}")
    print(f"left_point = {left_point.__repr__()}")
    print(f"top_offset_point = {top_offset_point.__repr__()}")
    print(f"left_offset_point = {left_offset_point.__repr__()}")
    print(f"center = {center.__repr__()}")
    print(f"view_frame = {view_frame}")
    print(f"camera_top_point = {camera_top_point.__repr__()}")
    print(f"camera_left_point = {camera_left_point.__repr__()}")
    print(f"intersect_top = {intersect_top.__repr__()}")
    print(f"intersect_left = {intersect_left.__repr__()}")

    if offset_top.length > offset_left.length:
        offset_location = offset_top
    else:
        offset_location = offset_left
    print(f"offset_location = {offset_location.__repr__()}")
    camera.matrix_world.translation = Matrix.Translation(offset_location) @ camera.matrix_world.translation
    print()


class CameraToBoard(bpy.types.Operator):
    bl_idname = "object.camera_to_board"
    bl_label = "Camera to Board"

    def execute(self, context):
        from ..utils import get_active_camera
        camera = get_active_camera(context)
        obj = context.object
        if camera != obj:
            camera_to_board(context, camera, obj)
        return {"FINISHED"}


clss = [
    CameraToBoard,
]

reg, unreg = bpy.utils.register_classes_factory(clss)


def register():
    reg()


def unregister():
    unreg()
