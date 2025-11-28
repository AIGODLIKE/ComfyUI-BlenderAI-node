import bpy
from .renderer import imgui

GLOBAL_SCALE = 1.25

class Const:
    SCALE = GLOBAL_SCALE
    # 通用
    WINDOW_P = (6, 6)  # Padding
    WINDOW_R = 33  # Rounding
    WINDOW_BS = 0  # Border Size
    
    CHILD_P = (8, 8)
    CHILD_R = 15
    CHILD_BS = 0
    CHILD_SB_R = 6
    CHILD_SB_S = 18
    CHILD_SB_P = 6
    CHILD_SB_BG = (0, 0, 0, 0)
    CHILD_SB_GRAB = (40 / 255, 40 / 255, 40 / 255, 1)
    CHILD_SB_GRAB_ACTIVE = (40 / 255, 40 / 255, 40 / 255, 1)
    CHILD_SB_GRAB_HOVERED = (40 / 255, 40 / 255, 40 / 255, 1)
    
    FRAME_R = 27

    POPUP_R = 20  # Rounding
    POPUP_BS = 2

    CELL_P = (6, 6)  # Cell Padding
    GRAB_R = 10  # Grab Rounding

    # COLORS
    WINDOW_BG = (40 / 255, 40 / 255, 40 / 255, 1)
    FRAME_BG = (56 / 255, 56 / 255, 56 / 255, 1)
    POPUP_BG = WINDOW_BG
    TRANSPARENT = (0, 0, 0, 0)
    CLOSE_BUTTON_NORMAL = (196 / 255, 196 / 255, 196 / 255, 1)
    CLOSE_BUTTON_ACTIVE = (255 / 255, 195 / 255, 0, 1)
    CLOSE_BUTTON_HOVERED = (255 / 255, 87 / 255, 51 / 255, 1)
    SLIDER_NORMAL = (42 / 255, 130 / 255, 228 / 255, 1)
    SLIDER_ACTIVE = (0 / 255, 200 / 255, 255 / 255, 1)

    BUTTON = (56 / 255, 56 / 255, 56 / 255, 1)
    BUTTON_ACTIVE = (255 / 255, 195 / 255, 0 / 255, 1)
    BUTTON_HOVERED = (75 / 255, 75 / 255, 75 / 255, 1)
    TEXT = (1, 1, 1, 1)

    # TOP BAR
    TB_WINDOW_R = 33
    TB_FRAME_R = 27

    # LAYER PANEL
    LP_WINDOW_R = 15
    LP_FRAME_R = 33
    LP_WINDOW_P = (26, 26)
    LP_CELL_P = (11 / 2, 11 / 2)

    LP_INDUSTRIAL_BUTTON_ACTIVE = (20 / 255, 20 / 255, 20 / 255, 1)
    LP_INDUSTRIAL_BUTTON_HOVERED = (40 / 255, 40 / 255, 40 / 255, 1)
    LP_INDUSTRIAL_BUTTON_TEXT_ALIGNX = 0.8
    LP_INDUSTRIAL_CELL_P = (6 / 2, 6)

    # LAYER PANEL
    RP_WINDOW_R = 15
    RP_WINDOW_P = (0, 0)
    RP_R_WINDOW_P = (26, 26)
    RP_FRAME_R = 12
    RP_FRAME_INNER_R = 10
    RP_FRAME_P = (12 * GLOBAL_SCALE, 12 * GLOBAL_SCALE)
    RP_CHILD_IS = (10, 10)
    RP_CELL_P = (0, 15 / 2)

    RP_L_BOX_BG = (40 / 255, 40 / 255, 40 / 255, 1)
    RP_R_BOX_BG = (56 / 255, 56 / 255, 56 / 255, 1)
    RP_R_BUTTON = (84 / 255, 84 / 255, 84 / 255, 1)
    RP_R_FRAME_BG_HOVERED = (200 / 255, 66 / 255, 66 / 255, 1)
    RP_R_FRAME_BG_ACTIVE = (200 / 255, 66 / 255, 66 / 255, 1)

    # CANVAS BOX
    CB_WINDOW_P = (16, 16)
    CB_WINDOW_R = 30
    CB_FRAME_BS = 0
    CB_FRAME_R = 27
    CB_POPUP_BS = 0
    CB_FRAME_BG = (65 / 255, 65 / 255, 65 / 255, 1)


class Styler:
    def __init__(self):
        self.num_colors = 0
        self.num_vars = 0

    def push_style_color(self, idx: imgui.Col, col):
        imgui.push_style_color(idx, col)
        self.num_colors += 1

    def push_style_var(self, idx: imgui.StyleVar, val):
        imgui.push_style_var(idx, val)
        self.num_vars += 1

    def push_style_var_x(self, idx: imgui.StyleVar, val_x):
        imgui.push_style_var_x(idx, val_x)
        self.num_vars += 1

    def push_style_var_y(self, idx: imgui.StyleVar, val_x):
        imgui.push_style_var_y(idx, val_x)
        self.num_vars += 1

    def pop_style_color(self, n=1):
        while n > 0:
            imgui.pop_style_color()
            self.num_colors -= 1
            n -= 1

    def pop_style_var(self, n=1):
        while n > 0:
            imgui.pop_style_var()
            self.num_vars -= 1
            n -= 1

    def pop_all(self):
        self.pop_style_color(self.num_colors)
        self.pop_style_var(self.num_vars)

    def __del__(self):
        self.pop_all()


class ImguiStyleBase:
    def __init__(self, name="默认"):
        self.name = name
        self.style_colors = {
            imgui.Col.TITLE_BG_ACTIVE: (0.546, 0.322, 0.730, 0.9),
            imgui.Col.FRAME_BG: (0.512, 0.494, 0.777, 0.573),
            imgui.Col.BUTTON: (0.2, 0.6, 0.9, 1.0),
            imgui.Col.BUTTON_HOVERED: (0.3, 0.7, 1.0, 1.0),
            imgui.Col.BUTTON_ACTIVE: (0.1, 0.5, 0.8, 1.0),
        }

    def apply_others(self):
        style = imgui.get_style()
        style.window_rounding = 5
        style.frame_rounding = 5
        style.frame_border_size = 0
        self.io.font_global_scale = bpy.context.preferences.view.ui_scale


class ImguiStylePurpleGray(ImguiStyleBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "PurpleGray"  # 紫灰
        self.style_colors = {
            imgui.Col.WINDOW_BG: (0.094, 0.094, 0.125, 0.94),  # 深灰蓝底色
            imgui.Col.TITLE_BG: (0.078, 0.078, 0.109, 0.67),  # 标题栏底色
            imgui.Col.TITLE_BG_ACTIVE: (0.546, 0.322, 0.730, 0.9),  # 活动标题栏渐变紫
            imgui.Col.FRAME_BG: (0.512, 0.494, 0.777, 0.573),  # 半透明淡紫色背景
            imgui.Col.FRAME_BG_HOVERED: (0.604, 0.581, 0.940, 0.7),  # 悬停渐变
            imgui.Col.FRAME_BG_ACTIVE: (0.675, 0.655, 0.958, 0.9),  # 激活状态渐变
            imgui.Col.BUTTON: (0.412, 0.380, 0.694, 0.8),  # 主按钮颜色
            imgui.Col.BUTTON_HOVERED: (0.549, 0.510, 0.859, 1.0),  # 按钮悬停渐变
            imgui.Col.BUTTON_ACTIVE: (0.650, 0.620, 0.980, 1.0),  # 按钮点击效果
            imgui.Col.HEADER: (0.546, 0.322, 0.730, 0.4),  # 折叠项头部
            imgui.Col.HEADER_HOVERED: (0.546, 0.322, 0.730, 0.8),
            imgui.Col.HEADER_ACTIVE: (0.630, 0.380, 0.850, 1.0),
            imgui.Col.SCROLLBAR_BG: (0.078, 0.078, 0.109, 0.0),  # 隐藏滚动条背景
            imgui.Col.SCROLLBAR_GRAB: (0.446, 0.337, 0.651, 0.6),  # 滚动条渐变色
            imgui.Col.CHECK_MARK: (0.950, 0.800, 0.980, 1.0),  # 浅紫色勾选标记
            imgui.Col.SLIDER_GRAB_ACTIVE: (0.750, 0.650, 0.980, 1.0),  # 滑块渐变色
            imgui.Col.TEXT: (0.890, 0.870, 0.960, 1.0),  # 浅灰紫文字
        }

    def apply_others(self):
        style = imgui.get_style()
        # 硬核工业造型
        style.window_rounding = 2.0  # 锐利直角
        style.frame_rounding = 1.5
        style.grab_rounding = 0.0  # 直角滑块
        style.scrollbar_size = 6.0  # 纤细滚动条

        # 立体边框系统
        style.window_border_size = 1.5
        style.frame_border_size = 1.2
        style.popup_border_size = 2.0
        style.colors[imgui.Col.BORDER] = (0.45, 0.47, 0.50, 0.25)  # 霜冻边框

        # 高光阴影系统
        style.colors[imgui.Col.BORDER_SHADOW] = (0.30, 0.32, 0.34, 0.15)

        # 精密布局参数
        style.item_spacing = (8.0, 4.0)  # 紧凑军事布局
        style.window_padding = (12.0, 8.0)
        style.cell_padding = (6.0, 3.0)  # 表格紧凑排版


class ImguiStyleBlackMetal(ImguiStyleBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "BlackMetal"
        # region 黑白灰
        self.style_colors = {
            imgui.Col.WINDOW_BG: (0.12, 0.12, 0.12, 0.98),  # 深灰主背景
            imgui.Col.TITLE_BG: (0.18, 0.18, 0.18, 0.85),  # 标题栏基础灰
            imgui.Col.TITLE_BG_ACTIVE: (0.22, 0.22, 0.22, 0.95),  # 强调灰
            imgui.Col.FRAME_BG: (0.15, 0.15, 0.15, 0.65),  # 输入框暗灰
            imgui.Col.FRAME_BG_HOVERED: (0.20, 0.20, 0.20, 0.80),  # 悬停灰
            imgui.Col.FRAME_BG_ACTIVE: (0.25, 0.25, 0.25, 0.90),  # 激活浅灰
            imgui.Col.BUTTON: (0.30, 0.30, 0.30, 0.85),  # 中灰按钮
            imgui.Col.BUTTON_HOVERED: (0.35, 0.35, 0.35, 0.95),  # 浅灰悬停
            imgui.Col.BUTTON_ACTIVE: (0.40, 0.40, 0.40, 1.00),  # 亮灰点击
            imgui.Col.HEADER: (0.25, 0.25, 0.25, 0.50),  # 折叠面板灰
            imgui.Col.HEADER_HOVERED: (0.30, 0.30, 0.30, 0.80),
            imgui.Col.HEADER_ACTIVE: (0.35, 0.35, 0.35, 1.00),
            imgui.Col.SCROLLBAR_BG: (0.10, 0.10, 0.10, 0.00),  # 隐藏滚动背景
            imgui.Col.SCROLLBAR_GRAB: (0.45, 0.45, 0.45, 0.60),  # 亮灰滚动条
            imgui.Col.CHECK_MARK: (0.95, 0.95, 0.95, 1.00),  # 纯白勾选
            imgui.Col.SLIDER_GRAB_ACTIVE: (0.65, 0.65, 0.65, 1.00),  # 金属银滑块
            imgui.Col.TEXT: (0.92, 0.92, 0.95, 1.00),  # 冷白色文字
        }

    def apply_others(self):
        style = imgui.get_style()
        style.window_rounding = 8.0  # 更大的窗口圆角
        style.frame_rounding = 6.0  # 圆角框架
        style.tab_rounding = 6.0  # 选项卡圆角
        style.grab_rounding = 16.0  # 滑块圆形抓柄
        style.scrollbar_rounding = 9.0  # 滚动条圆角
        style.window_border_size = 0.0  # 隐藏窗口边框
        style.frame_border_size = 1.0  # 框架细边框
        style.tab_border_size = 1.5  # 选项卡边框强调

        # 空间布局优化
        style.item_spacing = (8.0, 6.0)  # 紧凑的间距
        style.window_padding = (12.0, 12.0)  # 适中的内边距
        style.scrollbar_size = 10.0  # 更窄的滚动条

        # 动态效果增强
        style.grab_min_size = 20  # 更大的可抓取区域
        style.tab_close_button_min_width_selected = 0.0  # 隐藏默认关闭按钮
