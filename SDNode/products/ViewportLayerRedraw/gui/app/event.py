import bpy


class Event:
    def __init__(self, e: "bpy.types.Event"):
        self._ref: "bpy.types.Event" = e
        self.alt = e.alt
        self.ascii = e.ascii
        self.ctrl = e.ctrl
        # self.direction = e.direction
        self.is_consecutive = e.is_consecutive
        self.is_mouse_absolute = e.is_mouse_absolute
        self.is_repeat = e.is_repeat
        self.is_tablet = e.is_tablet
        self.mouse_prev_press_x = e.mouse_prev_press_x
        self.mouse_prev_press_y = e.mouse_prev_press_y
        self.mouse_prev_x = e.mouse_prev_x
        self.mouse_prev_y = e.mouse_prev_y
        self.mouse_region_x = e.mouse_region_x
        self.mouse_region_y = e.mouse_region_y
        self.mouse_x = e.mouse_x
        self.mouse_y = e.mouse_y
        self.oskey = e.oskey
        self.pressuse = e.pressure
        self.shift = e.shift
        self.tilt = e.tilt
        self.type = e.type
        self.type_prev = e.type_prev
        self.unicode = e.unicode
        self.value = e.value
        self.value_prev = e.value_prev
