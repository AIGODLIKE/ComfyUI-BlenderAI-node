import json
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from .style import Const

ASSETS_PATH = Path(__file__).parent.parent / "assets"
LAYERS_ASSETS_PATH = ASSETS_PATH / "layers"


class AssetTabType(Enum):
    MODELS = "models"
    MATERIALS = "materials"
    TEXTURES = "textures"
    SCRIPTS = "scripts"


class RightPanelType(Enum):
    NONE = "none"
    LAYERS = "layers"
    # mesh对应面板
    GENERATION = "generation"
    MESH = "mesh"
    MATERIAL = "material"
    EXTRACT = "extract"
    FILL = "fill"
    SEG = "seg"
    PIXBOOST = "pixboost"


@dataclass
class AssetItem:
    """资产项数据"""

    id: str
    name: str
    type: str
    file_path: str
    thumbnail_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AssetTabData:
    """资产栏分页数据"""

    tab_type: AssetTabType
    items: List[AssetItem] = field(default_factory=list)
    search_filter: str = ""
    selected_item_id: Optional[str] = None
    current_page: int = 1
    items_per_page: int = 20


@dataclass
class RightPanelData:
    """右侧面板数据基类"""

    panel_type: RightPanelType = RightPanelType.NONE


@dataclass
class PropertiesPanelData(RightPanelData):
    """属性面板数据"""

    selected_object_id: Optional[str] = None
    transform_data: Dict[str, Any] = field(default_factory=dict)
    material_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LayersPanelData(RightPanelData):
    """图层面板数据"""

    layers: List[Dict[str, Any]] = field(default_factory=list)
    common_presets: Dict[str, Any] = field(default_factory=dict)
    industrial_presets: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    industrial_preset_id: str = "Media"

    def __post_init__(self):
        layer_config_path = LAYERS_ASSETS_PATH / "layer_config.json"
        self.common_presets = {}
        self.industrial_presets = {}
        if not layer_config_path.exists():
            return
        config = json.loads(layer_config_path.read_text(encoding="utf-8"))
        self.common_presets = config.get("CommonPresets", {})
        self.industrial_presets = config.get("IndustrialPresets", {})

    @property
    def industrial_preset(self):
        return self.industrial_presets.get(self.industrial_preset_id, {})


@dataclass
class CanvasPanelData(RightPanelData):
    """画布面板数据"""

    gen_type: str = "Overwrite"  # Overwrite, NewCanvas


@dataclass
class ScenePanelData(RightPanelData):
    """场景面板数据"""

    scene_objects: List[Dict[str, Any]] = field(default_factory=list)
    selected_objects: List[str] = field(default_factory=list)
    scene_hierarchy: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SettingsPanelData(RightPanelData):
    """设置面板数据"""

    render_settings: Dict[str, Any] = field(default_factory=dict)
    editor_settings: Dict[str, Any] = field(default_factory=dict)
    input_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RightPanelsData:
    """右侧面板数据基类"""

    # 暂时4个子面板
    layer: LayersPanelData = field(default_factory=LayersPanelData)
    canvas: CanvasPanelData = field(default_factory=CanvasPanelData)
    scene: ScenePanelData = field(default_factory=ScenePanelData)
    properties: PropertiesPanelData = field(default_factory=PropertiesPanelData)
    settings: SettingsPanelData = field(default_factory=SettingsPanelData)


@dataclass
class UserData:
    coins: int = 200


@dataclass
class AppState:
    """应用程序全局状态"""

    # 界面状态
    active_right_panel: RightPanelType = RightPanelType.NONE
    active_asset_tab: AssetTabType = AssetTabType.MODELS

    # 一级面板
    asset_tabs_data: Dict[AssetTabType, AssetTabData] = field(default_factory=dict)
    right_panels_data: RightPanelsData = field(default_factory=RightPanelsData)
    user_data: UserData = field(default_factory=UserData)

    def __post_init__(self):
        # 初始化资产栏数据
        for tab_type in AssetTabType:
            self.asset_tabs_data[tab_type] = AssetTabData(tab_type=tab_type)

    # 界面状态操作
    def set_active_right_panel(self, panel_type: RightPanelType):
        self.active_right_panel = panel_type

    def set_active_asset_tab(self, tab_type: AssetTabType):
        self.active_asset_tab = tab_type
