import json
import bpy
from pathlib import Path

ctxt = "SDN"
LOCALE_MAP = {
    "zh_HANS": "zh_CN"
}
# 4.0 zh_HANS -> zh_HANS
# 3.0 zh_HANS -> zh_CN
LOCALE_MAP_INV = {}

def is_zh_HANS_version():
    try:
        bpy.context.preferences.view.language = "XXXXX"
    except TypeError as e:
        # import re
        # find_tuple = re.match(r".*?\('(.*?)\'\).*?", str(e))
        # if find_tuple and "zh_HANS" in find_tuple.group(1):
        #     return True
        return "zh_HANS" in str(e)
    return False

if not is_zh_HANS_version():
    LOCALE_MAP_INV = {
        "zh_HANS": "zh_CN"
    }

def get_locale_inv(locale):
    return LOCALE_MAP_INV.get(locale, locale)

REG_CTXT = {ctxt, }
REPLACE_DICT = {}
PROP_NAME_HEAD = "sdn_"
INTERNAL_NAMES = {
    "bl_description",
    "bl_height_default",
    "bl_height_max",
    "bl_height_min",
    "bl_icon",
    "bl_idname",
    "bl_label",
    "bl_rna",
    "bl_static_type",
    "bl_width_default",
    "bl_width_max",
    "bl_width_min",
    "calc_slot_index",
    "class_type",
    "color",
    "dimensions",
    "draw_buttons",
    "draw_buttons_ext",
    "dump",
    "get_from_link",
    "get_meta",
    "height",
    "hide",
    "id",
    "inp_types",
    "input_template",
    "inputs",
    "internal_links",
    "is_base_type",
    "is_registered_node_type",
    "label",
    "load",
    "location",
    "mute",
    "name",
    "out_types",
    "output_template",
    "outputs",
    "parent",
    "poll",
    "poll_instance",
    "pool",
    "query_stat",
    "rna_type",
    "select",
    "serialize",
    "set_stat",
    "show_options",
    "show_preview",
    "show_texture",
    "socket_value_update",
    "switch_socket",
    "type",
    "unique_id",
    "update",
    "use_custom_color",
    "width",
    "width_hidden"
}


def get_reg_name(inp_name):
    if inp_name.startswith("_"):
        return PROP_NAME_HEAD + inp_name
    if inp_name in INTERNAL_NAMES:
        return PROP_NAME_HEAD + inp_name
    return inp_name


def get_ori_name(inp_name):
    if inp_name.startswith(PROP_NAME_HEAD):
        return inp_name.replace(PROP_NAME_HEAD, "")
    return inp_name


other = {
    # SDNode/manager.py
    "Kill Last ComfyUI Process": "关闭上次打开的ComfyUI",
    "ComfyUI Path Not Found": "ComfyUI路径不存在",
    "Server Launching": "服务启动中...",
    "python interpreter not found": "未找到 python解释器",
    "Ensure that the python_embeded located in the same level as ComfyUI dir": "请确保python_embeded文件夹存放于ComfyUI路径同级目录",
    "Model Path": "当前ComfyUI路径",
    "Error: Out of VRam, try restart blender": "错误:显存不足, 请重启blender",
    "Server Launched": "服务启动成功!",
    "Add Task": "添加任务",
    "Server Not Launched, Add Task Failed": "服务未启动, 任务添加失败",
    "Please Check ComfyUI Directory": "请检查ComfyUI路径",
    "Server Not Launched": "服务未启动",
    "Add Result": "获取结果",
    "Submit Task": "提交任务",
    "Invalid Node Connection": "无效节点连接",
    "Node Connection Error": "节点连接错误",
    "Input Image Error": "输入图像错误",
    "Params Not Changed": "参数未变更",
    "Node Tree Not Executed, May Caused by:": "节点树未被执行, 可能原因:",
    "Proc Result": "处理结果",
    "Ran Node": "运行节点",
    "UnregNode Time:": "卸载节点耗时:",
    "Launch Time:": "启动耗时:",
    "RegNode Time:": "注册节点耗时:",
    "ControlNet Init....": "ControlNet 初始化...",
    "ControlNet Init Finished.": "ControlNet 初始化完毕.",
    "If controlnet still not worked, install manually by double clicked {}": "若ControlNet依然无法正常使用, 请手动双击 {} 安装",
    "Execute Node Cancelled!": "执行被跳过!",
    "Remote Server Connect Failed": "远程服务连接失败",
    "Executing Node": "正在执行节点",
    "Execution Cached": "执行缓存",
    "got response": "获取响应",
    "Remote Server Closed": "远程服务已关闭",
    "Proc Task Thread Exit": "任务处理线程关闭",
    "Poll Result Thread Exit": "响应轮询线程关闭",
    "Poll Task Thread Exit": "任务轮询线程关闭",
    "STDOUT Listen Thread Exit": "输出监听线程关闭",
    # SDNode/node_process.py
    "Executing": "执行中",
    # SDNode/nodes.py
    "icon path load error": "预览图配置解析失败",
    "|IGNORED|": "|已忽略|",
    "Not Found Item": "未找到项",
    "Not Found Node": "未找到节点",
    "Load": "载入",
    "Params not matching with current node": "参数与当前节点不匹配",
    "Params Loading Error": "参数载入错误",
    "Remove Link": "移除连接",
    "Parsing Node Start": "解析节点中...",
    "Server Launch Failed": "服务启动失败, 使用缓存节点信息数据",
    "None Input": "节点输入",
    "Parsing Node Finished!": "解析节点完成!",
    "Parsing Failed": "解析失败",
    "Render": "渲染",
    "ToImage": "到图像",
    "Pre Function": "预处理",
    "Post Function": "后处理",
    "Load Preview Image": "加载预览图",
    "  Select mask Objects": "  选中mask物体(可多选)",
    "  Select mask Collections": "  选中mask集合(可多选)",
    "Set Image Path of Render Result(.png)": "设置摄像机渲染图像的保存位置及文件名(.png)，如已设置请忽略",
    "Saved Title Name -> ": "存储名称",
    "Sync Rand": "统一随机",
    "Render Layer": "渲染层",
    "render_layer": "渲染层",
    "Output Layer": "输出层",
    "out_layers": "输出层",
    "Frames Directory": "序列图文件夹",
    "Image num per line": "每行图片数",
    # SDNode/blueprints.py
    "Non-Standard Enum": "非标准枚举",
    # SDNode/tree.py
    "Invalid Node Type: {}": "检查到无效的节点: {}",
    "ParseNode Time:": "解析节点耗时:",
    "Changed Node": "变更节点",
    # SDNode/utils.py
    "Gen Mask": "遮罩生成",
    # __init__.py
    "Execute Node Tree": "运行节点树",
    "Stop Loop": "终止循环",
    "Node Tree": "节点树",
    "Save": "保存",
    "Delete": "删除",
    "Replace Node Tree": "替换节点树",
    "Node Group": "节点",
    "Append Node Group": "追加节点",
    "Pending / Running": "排队 / 运行",
    "Adjust node tree and try again": "请调整后重新执行节点树",
    "Preset Bookmark": "魔法图鉴",
    "Load from Bookmark": "加载魔法图鉴",
    "Load from ClipBoard": "加载剪切板",
    "Preset": "法典",
    "exists, Click Ok to Overwrite!": "已存在, 确认将覆盖!",
    "Click Outside to Cancel!": "单击空白处取消!",
    "will be removed?": "即将消亡?",
    "Click Folder Icon to Select Bookmark:": "点击文件夹图标选择魔法图鉴:",
    "Preset Not Selected!": "没有选择法典!",
    "Invalid Preset Name!": "无效的法典名!",
    "Removed": "移除成功",
    "Presets": "预设",
    "Open NodeGroup Presets Folder": "打开节点预设文件夹",
    "Open NodeTree Presets Folder": "打开节点树预设文件夹",
    "Groups Directory": "节点文件夹",
    "Presets Directory": "预设文件夹",
    "Open Addon Preference": "打开插件设置",
    "Restart ComfyUI": "重启ComfyUI",
    "Launch ComfyUI": "打开ComfyUI",
    "Random All": "随机所有",
    "Preset Name": "法典烙印",
    # prop.py
    "Frame Mode": "渲染模式",
    "SingleFrame": "单帧",
    "MultiFrame": "多帧",
    "Batch": "批量",
    "Batch Directory": "批量处理文件夹",
    "Disable Render All": "禁用场景树所有渲染行为",
    "Advanced Setting": "显示高级设置",
    "Batch exec num": "批量执行数",
    "Loop exec": "循环执行",
    "Show General Setting": "显示启动设置",
    "Image not found or format error(png/json)": "魔法图鉴不存在或格式不正确(仅png/json)",
    "Load Preset from Image Error -> MetaData Not Found in": "从图鉴加载失败, 元数据为",
    # ops.py
    "No NodeTree Found": "节点树为空",
    "Node Not Found: ": "节点未找到",
    "Input Image Node Not Selected!": "未选择输入节点",
    "Batch Directory Not Set!": "批量处理文件夹 不正确",
    "Selected Node: ": "所选节点: ",
    "Node<{}>Directory is Empty!": "节点<{}>的文件夹路径为空!",
    "Node<{}>Directory Not Exists!": "节点<{}>的文件夹路径不存在!",
    "Frame <{}> Not Found in <{}> Node Path!": "帧<{}> 在节点<{}>路径中未找到对应!",
    "Frame <{}> Add to Task!": "帧任务<{}>添加成功!",
    "Launch/Connect ComfyUI": "启动/连接 ComfyUI服务",
    "Close/Disconnect ComfyUI": "关闭/断开 ComfyUI服务",
    "Restart ComfyUI": "重启ComfyUI",
    "ClipBoard Content Format Error": "剪切板内容格式错误",
    "Submit Task and with Clear Cache if Alt Pressed": "执行节点树, 如果按下了Alt执行 则 强制执行",
    "ComfyUI not Run,To Run?": "ComfyUI未启动,确定启动?",
    "Tree Copied to ClipBoard": "已复制到剪切板",
    "Load Batch Task": "加载批量任务表",
    "Copy Tree to ClipBoard": "复制到剪切板",
    "No Node Tree Found!": "未找到节点树!",
    "Load History": "加载历史",
    "Load History Workflow": "加载历史工作流",
    "Sync Stencil Image": "同步镂板",
    "Stop Sync Stencil Image": "停止同步",
    "Fetch Node Status": "更新节点信息",
    # ui.py
    "ClearTask": "清理任务",
    "Cancel": "取消任务",
    "↓↓ComfyUI Not Launched, Click to Launch↓↓": "↓↓服务未启动, 点击启动↓↓",
    # preference.py
    "Server Type": "服务类型",
    "LocalServer": "本机启动",
    "RemoteServer": "服务直连(含局域网)",
    "Preview Image Size": "预览图尺寸",
    "Enable High Quality Preview Image": "启用高清预览图",
    "ComfyUI Path": "ComfyUI路径",
    "Python Path": "Python解释器路径",
    "Select python dir or python.exe": "选择python所在文件夹或python.exe",
    "With WEBUI Model": "兼容WEBUI模型",
    "With ComfyUI Model": "兼容ComfyUI模型",
    "General": "通用",
    "Common Path": "常用路径",
    "Friendly Links" : "友情链接",
    "VRam Mode": "显存模式",
    "Gpu Only": "极高显存",
    "Store and run everything (text encoders/CLIP models, etc... on the GPU).": "所有数据存储到显存",
    "High VRam": "高显存",
    "By default models will be unloaded to CPU memory after being used. This option keeps them in GPU memory.": "模型常驻显存, 减少加载时间",
    "Normal VRam": "中显存",
    "Used to force normal vram use if lowvram gets automatically enabled.": "自动启用 低显存 模式时强制使用normal vram",
    "Low VRam": "低显存",
    "Split the unet in parts to use less vram.": "拆分UNet来降低显存开销",
    "No VRam": "超低显存",
    "When lowvram isn't enough.": "如果低显存依然不够",
    "Cpu Only": "仅CPU",
    "To use the CPU for everything (slow).": "只使用CPU",
    "Auto Launch Browser": "启动浏览器(启动服务后)",
    "Fixed Preview Image Size": "固定预览图大小",
    "Preview Image Size": "预览图大小",
    "Check Depencies Before Server Launch": "启动服务时检查依赖",
    "Check ComfyUI(some) Depencies Before Server Launch": "启动服务时进行ComfyUI插件(部分)依赖安装检查",
    "Force Log": "强制日志",
    "Force Log, Generally Not Needed": "强制输出日志, 一般不需要开启",
    "Service IP Address": "服务IP地址",
    "Port": "端口",
    "Service Port": "服务端口号",
    "Open CKPT Folder": "打开CKPT模型文件夹",
    "Open LoRA Folder": "打开LoRA模型文件夹",
    "Open ComfyUI Folder": "打开ComfyUI文件夹",
    "Open Cache Folder": "打开输出缓存文件夹",
    "-AIGODLIKE Adventure Community": "-AIGODLIKE冒险社区",
    "AIGODLIKE Open Source Community - Main Site": "AIGODLIKE开源社区-主站",
    "-Good friends exploring in the AI world (alphabetical order)": "-在AI世界探索的好朋友们(首字母排序)",
    "\"Thank you, these adventurers who are exploring and sharing their experience in the AI field, hurry up and follow them\"": "“感谢，这些在AI领域探索并分享经验的冒险者，快去关注啦～”",
    "Stencil Offset Size": "镂板偏移大小",
    "Drag Link Result Count": "拖拽连接显示行列数",
    "Drag Link Result Count Column": "列数",
    "Drag Link Result Count Row": "行数",
    "Drag Link Result Page Next": "下一页",
    "Drag Link Result Page Prev": "上一页",
    "Drag Link Result Page Current": "当前页",
    # MLT
    " Prompts": "提示词",
    "MLT": "多行文本",
    "Enable MLT": "开启多行文本",
    # oooo
    "enable": "开",
    "disable": "关",
    "samples": "采样",
    "sdn_width": "宽",
    "sdn_height": "高",
    "batch_size": "批次大小",
    "images": "图像",
    "IMAGE": "图像",
    # Internal
    "NodeReroute": "转接点",
    "NodeFrame": "框",
    # External/listen/hook
    "Import [{}] as {}?": "导入 [{}] 为{}?",
    "BatchTaskTable": "任务表",
    "NodeTree": "节点树"
}

LANG_TEXT = {
    get_locale_inv("en_US"): {
        # Blender
        "输入图像": "Input Image",
        "存储": "Save",
        "预览": "Preview",
    },
    get_locale_inv("zh_HANS"): {
        **other,
    }
}

def search_recursive(p: Path):
    if p.is_dir():
        for i in p.iterdir():
            yield from search_recursive(i)
    else:
        yield p

def get_json_data(p: Path) -> dict[str,dict[str, dict]]:
    json_files = [i for i in p.iterdir() if i.suffix == ".json"]
    json_data = {}
    for file in json_files:
        for coding in ("utf-8", "gbk"):
            try:
                json_data.update(json.loads(file.read_text(encoding=coding)))
                break
            except UnicodeDecodeError:
                pass
    return json_data

def get_json_data_recursive(p: Path) -> dict[str,dict[str, dict]]:
    json_files = [i for i in search_recursive(p) if i.suffix == ".json"]
    json_data = {}
    for file in json_files:
        for coding in ("utf-8", "gbk"):
            try:
                json_data.update(json.loads(file.read_text(encoding=coding)))
                break
            except UnicodeDecodeError:
                pass
    return json_data

def read_locale(locale):
    mapped_locale = LOCALE_MAP.get(locale, locale)
    p = Path(__file__).parent.joinpath(mapped_locale)
    if not p.exists():
        p = Path(__file__).parent.joinpath(mapped_locale.replace("_", "-"))
    if not p.exists() or p.is_file():
        return {}
    json_data = get_json_data(p)
    data = {}
    for key, value in json_data.items():
        if isinstance(value, str):
            data[key] = value
        elif isinstance(value, dict):
            if "title" in value:
                data[key] = value.pop("title")
            for sk, sv in value.items():
                if isinstance(sv, str):
                    data[sk] = sv
                elif isinstance(sv, dict):
                    data.update(sv)
    return data

def reg_other_translations(translations_dict:dict, replace_dict:dict, locale:str):
    for word, translation in LANG_TEXT[locale].items():
        translations_dict[locale][(ctxt, word)] = translation
        translations_dict[locale][(None, word)] = translation
        replace_dict[locale][word] = translation
        
def reg_node_ctxt(translations_dict:dict, replace_dict:dict, locale:str):
    mapped_locale = LOCALE_MAP.get(locale, locale)
    # 处理节点注册, 每个节点提供一个ctxt
    # 1. 查找locale
    p = Path(__file__).parent.joinpath(mapped_locale, "Nodes")
    if not p.exists():
        p = Path(__file__).parent.joinpath(mapped_locale.replace("_", "-"), "Nodes")
    if not p.exists():
        return {}
    
    json_data = get_json_data_recursive(p)

    if locale not in translations_dict:
        translations_dict[locale] = {}
    if locale not in replace_dict:
        replace_dict[locale] = {}
    td = translations_dict[locale]
    rd = replace_dict[locale]
    # 2. 注册所有Node
    for node_name, node_translation in json_data.items():
        ctxt = node_name
        REG_CTXT.add(ctxt)
        td[(ctxt, node_name)] = node_translation.pop("title", node_name)
        td[(None, node_name)] = td[(ctxt, node_name)]
        rd[node_name] = td[(ctxt, node_name)]
        for part in node_translation.values():
            for wn, wv in part.items():
                wn = get_reg_name(wn)
                td[(ctxt, wn)] = wv
                td[(None, wn)] = wv
                rd[wn] = wv
                # if node_name == "EmptyLatentImage": print(f"{node_name} reg: {wn} -> {wv}")


for locale in LANG_TEXT:
    LANG_TEXT[locale].update(read_locale(locale))

translations_dict = {}
for locale in LANG_TEXT:
    translations_dict[locale] = {}
    REPLACE_DICT[locale] = {}
    reg_node_ctxt(translations_dict, REPLACE_DICT, locale)
    reg_other_translations(translations_dict, REPLACE_DICT, locale)
    
def get_ctxt(msgctxt):
    if msgctxt in REG_CTXT:
        return msgctxt
    return ctxt





cat = {'default_real': None,
       'default': '*',
       'operator_default': 'Operator',
       'ui_events_keymaps': 'UI_Events_KeyMaps',
       'plural': 'Plural',
       'id_action': 'Action',
       'id_armature': 'Armature',
       'id_brush': 'Brush',
       'id_camera': 'Camera',
       'id_cachefile': 'CacheFile',
       'id_collection': 'Collection',
       'id_curve': 'Curve',
       'id_fs_linestyle': 'FreestyleLineStyle',
       'id_gpencil': 'GPencil',
       'id_curves': 'Curves',
       'id_id': 'ID',
       'id_image': 'Image',
       'id_shapekey': 'Key',
       'id_light': 'Light',
       'id_library': 'Library',
       'id_lattice': 'Lattice',
       'id_mask': 'Mask',
       'id_material': 'Material',
       'id_metaball': 'Metaball',
       'id_mesh': 'Mesh',
       'id_movieclip': 'MovieClip',
       'id_nodetree': 'NodeTree',
       'id_object': 'Object',
       'id_paintcurve': 'PaintCurve',
       'id_palette': 'Palette',
       'id_particlesettings': 'ParticleSettings',
       'id_pointcloud': 'PointCloud',
       'id_lightprobe': 'LightProbe',
       'id_scene': 'Scene',
       'id_screen': 'Screen',
       'id_sequence': 'Sequence',
       'id_simulation': 'Simulation',
       'id_speaker': 'Speaker',
       'id_sound': 'Sound',
       'id_texture': 'Texture',
       'id_text': 'Text',
       'id_vfont': 'VFont',
       'id_volume': 'Volume',
       'id_world': 'World',
       'id_workspace': 'WorkSpace',
       'id_windowmanager': 'WindowManager',
       'editor_view3d': 'View3D'
       }