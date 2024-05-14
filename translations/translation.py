import json
import bpy
from pathlib import Path

ctxt = "SDN"
LOCALE_MAP = {
    "zh_HANS": "zh_CN"
}
from ..datas import get_bl_version
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
    "switch_socket_widget",
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
    "Time Elapsed": "已耗时",
    "Error when playing sound:": "播放声音出错:",
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
    "None Input: %s": "空节点输入",
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
    "Node Name: %s": "节点名称: %s",
    "Input Name: %s": "输入项名: %s",
    "Input Type: %s": "输入类型: %s",
    "Input Value: %s": "输入项值: %s",
    "Enum Hashable Error: %s": "错误枚举: %s",
    "Skip Reg Node: %s": "跳过解析节点: %s",
    "Warning:": "警告:",
    "Don't link to GroupIn/Out node": "禁止手动连接到组输入/组输出节点",
    "Corresponding link will auto connect after exiting the group editing": "对应连接将在退出组编辑后自动连接",
    "Socket Manage": "Socket管理",
    "Default value is too large: %s.%s -> %s": "默认值过大: %s.%s -> %s",
    "Default value is too small: %s.%s -> %s": "默认值过小: %s.%s -> %s",
    "Text already exists": "词条已存在",
    "Add Tag By Input": "手动输入添加词条(Enter确定)",
    "Adv Text Action": "高级文本编辑",
    "SwitchAdvText": "切换文本编辑",
    "RemoveTag": "删除词条",
    "AddTag": "添加词条",
    "UpTagWeight": "增加权重",
    "DownTagWeight": "降低权重",
    "RemoveTagWeight": "删除权重",
    "socket type not str[IGNORE]: %s.%s -> %s": "Socket类型不是字符串[忽略]: %s.%s -> %s",
    "Add SaveImage node": "添加保存图片节点",
    "Add a SaveImage node and connect it to the image": "添加保存图片节点",
    "Toggle socket": "切换Socket/属性",
    "Toggle socket visibility": "切换Socket显示隐藏",
    "Toggle whether a socket is or isn't used for input": "切换Socket/属性",
    # SDNode/blueprints.py
    "Non-Standard Enum": "非标准枚举",
    "Capture Screen": "截图",
    "Capture Screen Region": "截图区域",
    "Error Capture Screen Region": "截图区域错误",
    "Save Screenshot": "保存截图",
    "No Camera in Scene": "场景像机不存在",
    "Upload Image Success": "图片上传成功",
    "Upload Image Fail": "图片上传失败",
    "ToSeq": "到序列",
    "SeqReplace": "替换",
    "SeqAppend": "追加",
    "SeqStack": "堆叠",
    "frame_final_duration": "帧时长",
    "output_dir": "输出文件夹",
    "Use Current Frame as Start Frame": "使用当前帧作为起始帧",
    "Cut off frames behand insert": "删除当前轨道后续帧",
    # SDNode/tree.py
    "Invalid Node Type: {}": "检查到无效的节点: {}",
    "ParseNode Time:": "解析节点耗时:",
    "Changed Node": "变更节点",
    "SDNGroup": "组",
    "NoCategory": "无分类",
    # SDNode/utils.py
    "AI Node" + get_bl_version() : "无限圣杯 Node" + get_bl_version(),
    "AI Node": "无限圣杯 Node",
    "Gen Mask": "遮罩生成",
    "Relink failed: %s": "重连失败: %s",
    "Composite node not found": "未找到合成节点",
    "Render Layer node not found": "未找到渲染层节点",
    "Mask node not set render cam": "遮照节点未设置渲染相机",
    "GP not set": "蜡笔未设置",
    "GP not found in current scene": "蜡笔物体未存在当前场景中",
    # SDNode/nodegroup.py
    "Depth of group tree is limited to 1": "组最大深度限制为1",
    "Node group can't be nested": "节点组不能被嵌套(最大深度限制为1)",
    # SDNode/custom_support.py
    "CPU Usage: ": "CPU占用:",
    "RAM Usage: ": "内存占用:",
    "HDD Usage: ": "硬盘占用:",
    "GPU Usage: ": "显卡占用:",
    "VRAM Usage:": "显存占用:",
    "CPU Usage": "CPU占用",
    "RAM Usage": "内存占用",
    "HDD Usage": "硬盘占用",
    "GPU Usage": "显卡占用",
    "VRAM Usage": "显存占用",
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
    "Node Cache Cleared!": "节点缓存已清除!",
    "Node Cache Clear Failed!": "节点缓存清除失败!",
    "Clear Node Cache": "清除节点缓存",
    "If node parsing error, you can delete node cache by this button, then restart blender to use it normally": "当节点解析错误时可以通过此按钮删除节点缓存, 删除后重启blender即可正常使用",
    # ui.py
    "ComfyUI": "圣杯节点",
    "ClearTask": "清理任务",
    "Cancel": "取消任务",
    "↓↓ComfyUI Not Launched, Click to Launch↓↓": "↓↓服务未启动, 点击启动↓↓",
    "ComfyUI Launching/Connecting...": "ComfyUI服务启动/连接中...",
    # preference.py
    "Server Type": "服务类型",
    "LocalServer": "本机启动",
    "RemoteServer": "服务直连(含局域网)",
    "Fixed": "固定尺寸",
    "Previews are shown at your chosen resolution": "使用设定分辨率预览",
    "Native": "原始尺寸",
    "Previews are shown at their native resolution": "使用原始尺寸预览",
    "Blender Default": "默认",
    "Default Blender behavior, previews are not automatically resized": "不控制预览图大小",
    "Preview Image Size": "预览图尺寸",
    "Play Finish Sound": "任务完成时播放声音",
    "Play a sound when the ComfyUI queue is empty": "当 ComfyUI 任务队列全部完成时播放声音",
    "Finish Sound Path" : "完成时播放的声音文件路径",
    "Path to the file to play when the ComfyUI queue is empty": "当 ComfyUI 任务队列全部完成时播的声音文件的路径",
    "Sound Volume": "声音音量",
    "Volume of the sound played wwhen the ComfyUI queue is empty": "当 ComfyUI 任务队列全部完成时播放的声音音量",
    "Enable High Quality Preview Image": "启用高清预览图",
    "ComfyUI Path": "ComfyUI路径",
    "Python Path": "Python解释器路径",
    "Select python dir or python.exe.\nOn Linux select your venv /bin/ folder": "选择python所在文件夹或python.exe.\n在Linux上选择您的venv /bin/ 文件夹",
    "With WEBUI Model": "兼容WEBUI模型",
    "With ComfyUI Model": "兼容ComfyUI模型",
    "General": "通用",
    "Common Path": "常用路径",
    "Friendly Links": "友情链接",
    "VRam Mode": "显存模式",
    "Gpu Only": "极高显存",
    "Store and run everything (text encoders/CLIP models, etc... on the GPU).": "全GPU模式：全部都使用GPU显存运行",
    "High VRam": "高显存",
    "By default models will be unloaded to CPU memory after being used. This option keeps them in GPU memory.": "模型常驻GPU模式：模型将常驻在GPU显存中,而不是用完就自动卸载到CPU内存",
    "Normal VRam": "中显存",
    "Used to force normal vram use if lowvram gets automatically enabled.": "默认调配模式：不进行节省GPU显存的处理，但模型等用完即卸载到内存",
    "Low VRam": "低显存",
    "Split the unet in parts to use less vram.": "显存节省模式：通过拆分UNet来降低显存使用",
    "No VRam": "超低显存",
    "When lowvram isn't enough.": "显存超级节省模式：如果低显存依然不够",
    "Cpu Only": "仅CPU",
    "To use the CPU for everything (slow).": "使用CPU运行一切(很慢)",
    "Auto Launch Browser": "启动浏览器(启动服务后)",
    "Fixed Preview Image Size": "固定预览图大小",
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
    "Custom Presets": "自定义预设",
    "Is Enabled?": "是否启用?",
    "Add Custom Presets Dir": "添加自定义预设路径",
    "Custom Preset Path already exists": "自定义预设路径已存在",
    "Init Custom Preset Path": "初始化自定义预设路径",
    "Create presets/groups dir if not exists": "没有presets/groups文件夹则创建",
    "Viewport Track Frequency": "视口实时渲染频率",
    "Use View Context": "使用视口上下文",
    "If enalbed use scene settings, otherwise use the current 3D view for rt rendering.": """如果启用, 使用场景设置, 否则使用当前3D视图进行实时渲染
注意: 禁用时,在多开视口时可能会导致渲染结果不匹配相机视角""",
    "cuda-malloc": "cuda-malloc",
    "Enable cudaMallocAsync (enabled by default for torch 2.0 and up).": "启用cudaMallocAsync(torch 2.0及以上版本已默认启用)",
    "Disable cudaMallocAsync.": "禁用cudaMallocAsync，有的技术不支持统一动态内存分配,禁用它解决问题",
    "dont upcast attention": "禁用upcast attention",
    "Disable upcasting of attention. Can boost speed but increase the chances of black images.": "禁用upcast attention, 可以提高速度, 但会增加黑图的概率",
    "Force fp32 (If this makes your GPU work better please report it).": "强制fp32",
    "Force fp16.": "强制fp16",
    "Run the UNET in bf16. This should only be used for testing stuff.": "在bf16下运行UNET, 仅用于测试",
    "Store unet weights in fp16.": "在fp16下存储UNET权重",
    "Store unet weights in fp8_e4m3fn.": "在fp8_e4m3fn下存储UNET权重",
    "Store unet weights in fp8_e5m2.": "在fp8_e5m2下存储UNET权重",
    "Run the VAE in fp16, might cause black images.": "在fp16下运行VAE, 可能导致黑图",
    "Run the VAE in full precision fp32.": "在fp32下运行VAE",
    "Run the VAE in bf16.": "在bf16下运行VAE",
    "Store text encoder weights in fp8 (e4m3fn variant).": "在fp8_e4m3fn下存储文本编码器权重",
    "Store text encoder weights in fp8 (e5m2 variant).": "在fp8_e5m2下存储文本编码器权重",
    "Store text encoder weights in fp16.": "在fp16下存储文本编码器权重",
    "Store text encoder weights in fp32.": "在fp32下存储文本编码器权重",
    "Default preview method for sampler nodes.": "采样器节点的默认预览方法",
    "disable ipex optimize": "禁用ipex优化",
    "Disables ipex.optimize when loading models with Intel GPUs.": "在使用Intel GPU加载模型时禁用ipex.optimize",
    "Use the split cross attention optimization. Ignored when xformers is used.": "使用split cross attention优化, xformers模式下忽略",
    "Use the sub-quadratic cross attention optimization . Ignored when xformers is used.": "使用sub-quadratic cross attention优化, xformers模式下忽略",
    "Use the new pytorch 2.0 cross attention function.": "使用新的pytorch 2.0 cross attention函数",
    "Disable xformers": "禁用xformers",
    "Disable xformers.": "禁用xformers",
    "disable smart memory": "禁用智能内存",
    "Force ComfyUI to agressively offload to regular ram instead of keeping models in vram when it can.": "强制ComfyUI将模型从显存转移到内存",
    "Make pytorch use slower deterministic algorithms when it can. Note that this might not make images deterministic in all cases.": "使pytorch在可能的情况下使用更慢的确定性算法. 请注意, 这可能不会使图像在所有情况下都具有确定性",
    "dont print server": "屏蔽服务输出",
    "Don't print server output.": "不打印服务输出内容",
    "disable metadata": "禁用元数据",
    "Disable saving prompt metadata in files.": "禁止prompt元数保存到文件",
    "windows standalone build": "Windows独立构建",
    "Windows standalone build: Enable convenient things that most people using the standalone windows build will probably enjoy (like auto opening the page on startup).": "Windows独立构建: 启用大多数人使用独立Windows构建时可能会喜欢的便利功能(例如启动时自动打开页面)",
    "Args Copied To Clipboard": "参数已复制到剪切板",
    "Copy Args": "复制参数",
    "Copy Args To Clipboard": "将参数复制到剪切板",
    # MLT
    " Prompts": "提示词",
    "MLT": "多行文本",
    "Enable MLT": "开启多行文本",
    "Enable multiline text for this textbox": "开启多行文本",
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
    "NodeTree": "节点树",
    # hook
    "Find Drag file": "发现拖拽文件",
    "Screenshot": "截图",
}

LANG_TEXT = {
    get_locale_inv("en_US"): {
        # Blender
        "输入图像": "Input Image",
        "材质图": "Mat Image",
        "截图": "Screenshot",
        "存储": "Save",
        "预览": "Preview",
        "输入": "Input",
        "渲染": "Render",
        "序列图": "Sequence",
        "视口": "Viewport",
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


def get_json_data(p: Path) -> dict[str, dict[str, dict]]:
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


def get_json_data_recursive(p: Path) -> dict[str, dict[str, dict]]:
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


def reg_other_translations(translations_dict: dict, replace_dict: dict, locale: str):
    for word, translation in LANG_TEXT[locale].items():
        translations_dict[locale][(ctxt, word)] = translation
        translations_dict[locale][(None, word)] = translation
        replace_dict[locale][word] = translation


def reg_node_ctxt(translations_dict: dict, replace_dict: dict, locale: str):
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
            if not isinstance(part, dict):
                continue
            for wn, wv in part.items():
                wn = get_reg_name(wn)
                td[(ctxt, wn)] = wv
                td[(None, wn)] = wv
                rd[wn] = wv
                # if node_name == "EmptyLatentImage": print(f"{node_name} reg: {wn} -> {wv}")


for locale, TEXT in LANG_TEXT.items():
    TEXT.update(read_locale(locale))

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
