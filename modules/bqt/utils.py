import bpy
import traceback


def try_except(func):
    """
    Prevent blender from crashing on an exception.
    Decorator to wrap a function in try except and print the traceback
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()

    return wrapper


def context_window(func):
    """
    Support running operators from QT (ex. on button click).
    Decorator to override the context window for a function,
    """

    def wrapper(*args, **kwargs):
        with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
            return func(*args, **kwargs)

    return wrapper
