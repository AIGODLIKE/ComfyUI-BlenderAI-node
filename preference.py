import typing
import bpy
import os
import sys
import json
import re
from pathlib import Path

from .utils import Icon, _T, FSWatcher
from .External.lupawrapper import toggle_debug
from .translations import ctxt
from .kclogger import logger


def dir_cb_test(path):
    return
    logger.info(f"{path} changed")


class PresetsDirDesc(bpy.types.PropertyGroup):
    def path_set(self, path):
        """检查路径是否合法"""
        if not path or path == self.path:
            return
        if not os.path.exists(path) or not os.path.isdir(path):
            return
        # 路径不能已经存在于pref_dirs中
        pref = get_pref()
        for item in pref.pref_dirs:
            if item.path != path:
                continue

            def error_draw(self, context):
                self.layout.label(text="Custom Preset Path already exists", text_ctxt=ctxt)
            bpy.context.window_manager.popup_menu(error_draw, title=_T("Error"), icon="ERROR")
            return

        self["path"] = path
        if pref.pref_dirs_init:
            # 创建presets/groups目录
            Path(path).joinpath("presets").mkdir(parents=True, exist_ok=True)
            Path(path).joinpath("groups").mkdir(parents=True, exist_ok=True)
        if self.enabled:
            FSWatcher.register(Path(path).joinpath("presets"), dir_cb_test)
            FSWatcher.register(Path(path).joinpath("groups"), dir_cb_test)

    def path_get(self):
        if "path" not in self:
            return ""
        return self["path"]
    path: bpy.props.StringProperty(name="Path", subtype="DIR_PATH", set=path_set, get=path_get)

    def update_enabled(self, context):
        p = Path(self.path)
        if self.enabled:
            FSWatcher.register(p.joinpath("presets"), dir_cb_test)
            FSWatcher.register(p.joinpath("groups"), dir_cb_test)
        else:
            FSWatcher.unregister(p.joinpath("presets"))
            FSWatcher.unregister(p.joinpath("groups"))
        from .prop import Prop
        Prop.mark_dirty()
    enabled: bpy.props.BoolProperty(name="Is Enabled?", default=True, update=update_enabled)


class PresetsDirEdit(bpy.types.Operator):
    bl_idname = "sdn.presets_dir_edit"
    bl_label = "Edit Presets Dir"
    bl_description = "Edit Presets Dir"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(items=[("ADD", "Add", "", "ADD", 0),
                                          ("REMOVE", "Remove", "", "REMOVE", 1)
                                          ],
                                   name="Action", options={"HIDDEN"})
    index: bpy.props.IntProperty(name="Index")

    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    def invoke(self, context, event):
        if self.action == "ADD":
            # 弹出文件夹选择框
            wm = bpy.context.window_manager
            wm.fileselect_add(self)
            return {"RUNNING_MODAL"}
        return self.execute(context)

    def execute(self, context):
        pref = get_pref()
        if self.action == "ADD":
            # 判断路径是否已经存在
            for item in pref.pref_dirs:
                if item.path != self.directory:
                    continue

                def error_draw(self, context):
                    self.layout.label(text="Custom Preset Path already exists", text_ctxt=ctxt)
                # 弹出一个面板
                bpy.context.window_manager.popup_menu(error_draw, title=_T("Error"), icon="ERROR")
                self.report({"ERROR"}, _T("Custom Preset Path already exists"))
                return {"CANCELLED"}
            item = pref.pref_dirs.add()
            item.path = self.directory
            p = Path(item.path)
            if pref.pref_dirs_init:
                # 创建presets/groups目录
                p.joinpath("presets").mkdir(parents=True, exist_ok=True)
                p.joinpath("groups").mkdir(parents=True, exist_ok=True)
            FSWatcher.register(p.joinpath("presets"), dir_cb_test)
            FSWatcher.register(p.joinpath("groups"), dir_cb_test)
        elif self.action == "REMOVE":
            pref.pref_dirs.remove(self.index)
            FSWatcher.unregister(Path(self.directory).joinpath("presets"))
            FSWatcher.unregister(Path(self.directory).joinpath("groups"))
        return {"FINISHED"}


class AddonPreference(bpy.types.AddonPreferences):
    bl_idname = __package__
    bl_translation_context = ctxt

    def update_debug(self, context):
        toggle_debug(self.debug)
    debug: bpy.props.BoolProperty(default=False, name="Debug", update=update_debug)
    popup_scale: bpy.props.IntProperty(default=5, min=1, max=100, name="Preview Image Size")
    enable_hq_preview: bpy.props.BoolProperty(default=True, name="Enable High Quality Preview Image")
    server_type: bpy.props.EnumProperty(items=[("Local", "LocalServer", "", "LOCKVIEW_ON", 0),
                                               ("Remote", "RemoteServer", "", "WORLD_DATA", 1)
                                               ],
                                        name="Server Type")  # --server_type
    model_path: bpy.props.StringProperty(subtype="DIR_PATH", name="ComfyUI Path",
                                         default=str(Path(__file__).parent / "ComfyUI"))
    python_path: bpy.props.StringProperty(subtype="FILE_PATH",
                                          name="Python Path",
                                          description="Select python dir or python.exe")
    page: bpy.props.EnumProperty(items=[("通用", "General", "", "COLLAPSEMENU", 0),
                                        ("常用路径", "Common Path", "", "URL", 1),
                                        ("友情链接", "Friendly Links", "", "URL", 2),
                                        ], default=0)

    cuda_malloc: bpy.props.EnumProperty(name="cuda-malloc",
                                        items=[("default", "Auto", "", 0),
                                               ("--cuda-malloc", "Enable", "Enable cudaMallocAsync (enabled by default for torch 2.0 and up).", 1),
                                               ("--disable-cuda-malloc", "Disable", "Disable cudaMallocAsync.", 2)
                                               ])  # --cuda_malloc
    dont_upcast_attention: bpy.props.BoolProperty(default=False, name="dont upcast attention", description="Disable upcasting of attention. Can boost speed but increase the chances of black images.")  # --dont-upcast-attention

    fp: bpy.props.EnumProperty(name="fp",
                               items=[("default", "Auto", "", 0),
                                      ("--force-fp32", "Force fp32", "Force fp32 (If this makes your GPU work better please report it).", 1),
                                      ("--force-fp16", "Force fp16", "Force fp16.", 2)
                                      ])  # --fp

    fpunet: bpy.props.EnumProperty(name="fpunet",
                                   items=[("default", "Auto", "", 0),
                                          ("--bf16-unet", "bf16", "Run the UNET in bf16. This should only be used for testing stuff.", 1),
                                          ("--fp16-unet", "fp16", "Store unet weights in fp16.", 2),
                                          ("--fp8_e4m3fn-unet", "fp8_e4m3fn", "Store unet weights in fp8_e4m3fn.", 3),
                                          ("--fp8_e5m2-unet", "fp8_e5m2", "Store unet weights in fp8_e5m2.", 4)
                                          ])  # --fpunet
    fpvae: bpy.props.EnumProperty(name="fpvae",
                                  items=[("default", "Auto", "", 0),
                                         ("--fp16-vae", "fp16-vae", "Run the VAE in fp16, might cause black images.", 1),
                                         ("--fp32-vae", "fp32-vae", "Run the VAE in full precision fp32.", 2),
                                         ("--bf16-vae", "bf16-vae", "Run the VAE in bf16.", 3)
                                         ])  # --fpvae
    fpte: bpy.props.EnumProperty(name="fpte",
                                 items=[("default", "Auto", "", 0),
                                        ("--fp8_e4m3fn-text-enc", "fp8_e4m3fn-text-enc", "Store text encoder weights in fp8 (e4m3fn variant).", 1),
                                        ("--fp8_e5m2-text-enc", "fp8_e5m2-text-enc", "Store text encoder weights in fp8 (e5m2 variant).", 2),
                                        ("--fp16-text-enc", "fp16-text-enc", "Store text encoder weights in fp16.", 3),
                                        ("--fp32-text-enc", "fp32-text-enc", "Store text encoder weights in fp32.", 4)
                                        ])  # --fpte
    preview_method: bpy.props.EnumProperty(name="preview-method",
                                           items=[("none", "None", "", 0),
                                                  ("auto", "Auto", "", 1),
                                                  ("latent2rgb", "Latent2RGB", "", 2),
                                                  ("taesd", "TAESD", "", 3)
                                                  ],
                                           description="Default preview method for sampler nodes.")  # --preview-method
    disable_ipex_optimize: bpy.props.BoolProperty(default=False, name="disable ipex optimize", description="Disables ipex.optimize when loading models with Intel GPUs.")  # --disable-ipex-optimize

    attn: bpy.props.EnumProperty(name="attn",
                                 items=[("default", "Auto", "", 0),
                                        ("--use-split-cross-attention", "split-cross-attention", "Use the split cross attention optimization. Ignored when xformers is used.", 1),
                                        ("--use-quad-cross-attention", "quad-cross-attention", "Use the sub-quadratic cross attention optimization . Ignored when xformers is used.", 2),
                                        ("--use-pytorch-cross-attention", "pytorch-cross-attention", "Use the new pytorch 2.0 cross attention function.", 3)
                                        ])  # --attn
    disable_xformers: bpy.props.BoolProperty(default=False, name="Disable xformers", description="Disable xformers.")  # --disable-xformers

    vram: bpy.props.EnumProperty(name="VRam Mode",
                                 items=[("default", "Auto", "", 0),
                                        ("--gpu-only", "Gpu Only", "Store and run everything (text encoders/CLIP models, etc... on the GPU).", 1),
                                        ("--highvram", "High VRam", "By default models will be unloaded to CPU memory after being used. This option keeps them in GPU memory.", 2),
                                        ("--normalvram", "Normal VRam", "Used to force normal vram use if lowvram gets automatically enabled.", 3),
                                        ("--lowvram", "Low VRam", "Split the unet in parts to use less vram.", 4),
                                        ("--novram", "No VRam", "When lowvram isn't enough.", 5),
                                        ("--cpu", "Cpu Only", "To use the CPU for everything (slow).", 6),
                                        ])  # --vram
    disable_smart_memory: bpy.props.BoolProperty(default=False, name="disable smart memory", description="Force ComfyUI to agressively offload to regular ram instead of keeping models in vram when it can.")  # --disable-smart-memory
    deterministic: bpy.props.BoolProperty(default=False, name="deterministic", description="Make pytorch use slower deterministic algorithms when it can. Note that this might not make images deterministic in all cases.")  # --deterministic
    dont_print_server: bpy.props.BoolProperty(default=False, name="dont print server", description="Don't print server output.")  # --dont-print-server
    disable_metadata: bpy.props.BoolProperty(default=False, name="disable metadata", description="Disable saving prompt metadata in files.")  # --disable-metadata
    windows_standalone_build: bpy.props.BoolProperty(
        default=False,
        name="windows standalone build",
        description="Windows standalone build: Enable convenient things that most people using the standalone windows build will probably enjoy (like auto opening the page on startup).")  # --windows-standalone-build
    with_webui_model: bpy.props.StringProperty(default="", name="With WEBUI Model", subtype="DIR_PATH")
    with_comfyui_model: bpy.props.StringProperty(default="", name="With ComfyUI Model", subtype="DIR_PATH")

    def update_copy_args(self, context):
        if self.copy_args:
            self.copy_args = False
            wm = bpy.context.window_manager
            wm.clipboard = " ".join(self.parse_server_args())

            def draw(self, context):
                self.layout.label(text="Args Copied To Clipboard", text_ctxt=ctxt)
            wm.popup_menu(draw, title=_T("Info"), icon="INFO")
    copy_args: bpy.props.BoolProperty(default=False, name="Copy Args", description="Copy Args To Clipboard", update=update_copy_args)
    auto_launch: bpy.props.BoolProperty(default=False, name="Auto Launch Browser")
    install_deps: bpy.props.BoolProperty(default=False, name="Check Depencies Before Server Launch", description="Check ComfyUI(some) Depencies Before Server Launch")
    force_log: bpy.props.BoolProperty(default=False, name="Force Log", description="Force Log, Generally Not Needed")
    fixed_preview_image_size: bpy.props.BoolProperty(default=True, name="Fixed Preview Image Size")
    preview_image_size: bpy.props.IntProperty(default=256, min=64, max=8192, name="Preview Image Size")
    stencil_offset_size_xy: bpy.props.IntVectorProperty(default=(0, 18), size=2, min=-100, max=100, name="Stencil Offset Size")
    drag_link_result_count_col: bpy.props.IntProperty(default=4, min=1, max=10, name="Drag Link Result Count Column")
    drag_link_result_count_row: bpy.props.IntProperty(default=10, min=1, max=100, name="Drag Link Result Count Row")
    count_page_total: bpy.props.IntProperty(default=0, min=0, name="Drag Link Result Page Total")

    count_page_current: bpy.props.IntProperty(default=0, min=0, name="Drag Link Result Page Current")

    def parse_comfyUIStart(self):
        config = []
        try:
            path = Path(sys.argv[sys.argv.index("comfyUIStart") + 1])
            if not path.exists():
                logger.error(_T("Invalid Config File Path"))
                return []
            config = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(config, list):
                return []
            for piece in config:
                # --listen 127.0.0.1 --port 8188
                if ip := re.match(r"--listen\s+([0-9.]+)", piece):
                    ip = ip.group(1)
                    ip = {"0.0.0.0": "127.0.0.1"}.get(ip, ip)
                    self.ip = ip
                if port := re.match(r".*?--port\s+([0-9]+)", piece):
                    self.port = int(port.group(1))
            config = " ".join(config)
            config = re.split(r"\s(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", config)
            # logger.info(f"{_T('Reparse Config')}: {config}")
            # config = " ".join(config).split(" ")  # resplit
            for i, piece in enumerate(config):
                if piece[0] == piece[-1] == "\"":
                    piece = Path(piece.replace("\"", "")).resolve()
                    piece = FSWatcher.to_str(piece)
                    config[i] = piece
            if "--auto-launch" in config:
                config.remove("--auto-launch")
            if "--disable-auto-launch" in config:
                config.remove("--disable-auto-launch")
            if "--windows-standalone-build" in config:
                config.remove("--windows-standalone-build")
            # logger.info(f"{_T('Find Config')}: {config}")
        except IndexError:
            logger.error(_T("No Config File Found"))
        except Exception as e:
            logger.error(_T("Parse Config Error: {e}").format(e))
        return config

    def get_python(self):
        python = Path("python3")
        custom_python = Path(self.python_path)
        if self.python_path and custom_python.exists():
            if custom_python.is_dir():
                if sys.platform == "win32":
                    python = custom_python / "python.exe"
                else:
                    python = custom_python / "python3"
            else:
                python = custom_python
        elif sys.platform == "win32":
            python = Path(self.model_path).parent / "python_embeded/python.exe"
        return python

    def parse_server_args(self, server=None):
        if server is None:
            from .SDNode.manager import FakeServer
            server = FakeServer._instance
        python = self.get_python()
        model_path = Path(self.model_path)
        args = [python.as_posix()]
        # arg = f"-s {str(model_path)}/main.py"
        args.append("-s")

        # 备份main.py 为 main-bak.py
        # 为main-bak.py新增 sys.path代码
        try:
            with open(model_path.joinpath("main.py"), "r", encoding="utf-8") as f:
                sa = f"import sys\nsys.path.append(r\"{model_path.as_posix()}\")\n"
                model_path.joinpath("main-bak.py").write_text(sa + f.read(), encoding="utf-8")
        except BaseException:
            ...
        if self.python_path and Path(self.python_path).exists() and model_path.joinpath("main-bak.py").exists():
            args.append(f"{model_path.joinpath('main-bak.py').resolve().as_posix()}")
        else:
            args.append(f"{model_path.joinpath('main.py').resolve().as_posix()}")
        # 特殊处理
        if self.auto_launch:
            args.append("--auto-launch")
        # [ 'comfyUIStart', 'startConfigureFile.json']
        if "comfyUIStart" in sys.argv:
            args.extend(self.parse_comfyUIStart())
            return args
        # 解析所有参数
        args.append("--listen")
        args.append(server.get_ip())
        args.append("--port")
        args.append(f"{server.get_port()}")
        if self.cuda.isdigit():
            args.append("--cuda-device")
            args.append(self.cuda)
        if self.vram != "default":
            args.append(self.vram)
        yaml = ""
        yamlpath = Path(__file__).parent / "SDNode/yaml"
        if self.with_webui_model and Path(self.with_webui_model).exists():
            wmp = Path(self.with_webui_model).as_posix()
            wmpp = Path(self.with_webui_model).parent.as_posix()
            a111_yaml = yamlpath.joinpath("a111.yaml").read_text()
            yaml += a111_yaml.format(wmp=wmp, wmpp=wmpp)
        if self.with_comfyui_model and Path(self.with_comfyui_model).exists():
            cmp = Path(self.with_comfyui_model).as_posix()  # 指定到 models
            cmpp = Path(self.with_comfyui_model).parent.as_posix()
            custom_comfyui = yamlpath.joinpath("custom.yaml").read_text()
            yaml += custom_comfyui.format(cmp=cmp, cmpp=cmpp)
        if yaml:
            extra_model_paths = yamlpath.joinpath("config.yaml")
            extra_model_paths.write_text(yaml)
            args.append("--extra-model-paths-config")
            args.append(extra_model_paths.as_posix())
        # --cuda-malloc
        if self.cuda_malloc != "default":
            args.append(self.cuda_malloc)
        # --dont-upcast-attention
        if self.dont_upcast_attention:
            args.append("--dont-upcast-attention")
        # --force-fp32/16
        if self.fp != "default":
            args.append(self.fp)
        # -- fpunet
        if self.fpunet != "default":
            args.append(self.fpunet)
        # -- fpvae
        if self.fpvae != "default":
            args.append(self.fpvae)
        # -- fpte
        if self.fpte != "default":
            args.append(self.fpte)
        # --preview-method
        if self.preview_method != "none":
            args.append("--preview-method")
            args.append(self.preview_method)
        # --disable-ipex-optimize
        if self.disable_ipex_optimize:
            args.append("--disable-ipex-optimize")
        # --attn
        if self.attn != "default":
            args.append(self.attn)
        # --disable-xformers
        if self.disable_xformers:
            args.append("--disable-xformers")
        # --disable-smart-memory
        if self.disable_smart_memory:
            args.append("--disable-smart-memory")
        # --deterministic
        if self.deterministic:
            args.append("--deterministic")
        # --dont-print-server
        if self.dont_print_server:
            args.append("--dont-print-server")
        # --disable-metadata
        if self.disable_metadata:
            args.append("--disable-metadata")
        if self.windows_standalone_build:
            args.append("--windows-standalone-build")
        return args

    def update_count_page_next(self, context):
        if self.count_page_next:
            self.count_page_next = False
            self.count_page_current += 1
            self.count_page_current = min(self.count_page_current, self.count_page_total)
            bpy.ops.sdn.mouse_pos_rec("INVOKE_DEFAULT", action="ORI")
            from .Linker.linker import P
            bpy.context.window.cursor_warp(P.x, P.y)
            bpy.ops.comfy.swapper("INVOKE_DEFAULT", action="DRAW")
            bpy.context.window.cursor_warp(P.ori_x, P.ori_y)

    count_page_next: bpy.props.BoolProperty(default=False,
                                            name="Drag Link Result Page Next",
                                            update=update_count_page_next)

    def update_count_page_prev(self, context):
        if self.count_page_prev:
            self.count_page_prev = False
            self.count_page_current -= 1
            bpy.ops.sdn.mouse_pos_rec("INVOKE_DEFAULT", action="ORI")
            from .Linker.linker import P
            bpy.context.window.cursor_warp(P.x, P.y)
            bpy.ops.comfy.swapper("INVOKE_DEFAULT", action="DRAW")
            bpy.context.window.cursor_warp(P.ori_x, P.ori_y)
    count_page_prev: bpy.props.BoolProperty(default=False,
                                            name="Drag Link Result Page Prev",
                                            update=update_count_page_prev)

    def get_cuda_list():
        """
        借助nvidia-smi获取CUDA版本列表
        """
        import subprocess
        import re
        try:
            res = subprocess.check_output("nvidia-smi -L", shell=True).decode("utf-8")
            # GPU 0: NVIDIA GeForce GTX 1060 5GB (UUID: xxxx)
            items = [("default", "Auto", "", 0,)]
            for line in res.split("\n"):
                m = re.search(r"GPU (\d+): NVIDIA GeForce (.*) \(UUID: GPU-.*\)", line)
                if not line.startswith("GPU") or not m:
                    continue
                items.append((m.group(1), m.group(2), "", len(items),))
            return items
        except BaseException:
            return [("default", "Auto", "", 0,)]

    cuda: bpy.props.EnumProperty(name="cuda", items=get_cuda_list())

    def ip_check(self, context):
        """检查IP地址是否合法"""
        ip = self.ip.split(".")
        if len(ip) < 4:
            ip.extend(["0"] * (4 - len(ip)))
        ip = ip[:4]
        for i in range(4):
            if not ip[i].isdigit():
                ip[i] = "0"
            v = int(ip[i])
            ip[i] = str(min(255, max(0, v)))
        self["ip"] = ".".join(ip)

    ip: bpy.props.StringProperty(default="127.0.0.1", name="IP", description="Service IP Address",
                                 update=ip_check)
    port: bpy.props.IntProperty(default=8189, min=1000, max=65535, name="Port", description="Service Port")

    pref_dirs: bpy.props.CollectionProperty(type=PresetsDirDesc, name="Custom Presets", description="Custom Presets")
    pref_dirs_init: bpy.props.BoolProperty(default=True, name="Init Custom Preset Path", description="Create presets/groups dir if not exists")

    rt_track_freq: bpy.props.FloatProperty(default=0.5, min=0.01, name="Viewport Track Frequency")
    view_context: bpy.props.BoolProperty(default=True, name="Use View Context", description="If enalbed use scene settings, otherwise use the current 3D view for rt rendering.")

    def update_open_dir1(self, context):
        if self.open_dir1:
            self.open_dir1 = False
            os.startfile(Path(self.model_path) / "models/checkpoints")

    open_dir1: bpy.props.BoolProperty(default=False, name="Open CKPT Folder", update=update_open_dir1)

    def update_open_dir2(self, context):
        if self.open_dir2:
            self.open_dir2 = False
            os.startfile(Path(self.model_path) / "models/loras")
    open_dir2: bpy.props.BoolProperty(default=False, name="Open LoRA Folder", update=update_open_dir2)

    def update_open_dir3(self, context):
        if self.open_dir3:
            self.open_dir3 = False
            os.startfile(self.model_path)

    open_dir3: bpy.props.BoolProperty(default=False, name="Open ComfyUI Folder", update=update_open_dir3)

    def update_open_dir4(self, context):
        if self.open_dir4:
            self.open_dir4 = False
            os.startfile(Path(self.model_path) / "SDNodeTemp")

    open_dir4: bpy.props.BoolProperty(default=False,
                                      name="Open Cache Folder",
                                      update=update_open_dir4)

    def draw_custom_presets(self, layout: bpy.types.UILayout):
        box = layout.box()
        box.label(text="Custom Presets", text_ctxt=ctxt)
        header = box.row(align=True)
        header.operator(PresetsDirEdit.bl_idname, text="Add Custom Presets Dir", icon="ADD", text_ctxt=ctxt).action = "ADD"
        header.prop(self, "pref_dirs_init", text="", icon="FILE_REFRESH", text_ctxt=ctxt)
        col = box.column(align=True)
        col.scale_y = 1.1
        for i, item in enumerate(self.pref_dirs):
            row = col.row(align=True)
            row.prop(item, "enabled", text="", icon="CHECKBOX_HLT", text_ctxt=ctxt)
            row.prop(item, "path", text="", text_ctxt=ctxt)
            op = row.operator(PresetsDirEdit.bl_idname, icon="REMOVE", text="", text_ctxt=ctxt)
            op.action = "REMOVE"
            op.index = i

    def draw_general(self, layout: bpy.types.UILayout):
        row = layout.row()
        row.prop(self, "server_type", text_ctxt=ctxt)
        if self.server_type == "Local":
            layout.prop(self, "model_path", text_ctxt=ctxt)
            layout.prop(self, "python_path", text_ctxt=ctxt)
            layout.prop(self, "with_webui_model")
            layout.prop(self, "with_comfyui_model")
            layout.prop(self, "cuda")
            layout.prop(self, "vram", text_ctxt=ctxt)
        row = layout.row(align=True)
        row.prop(self, "stencil_offset_size_xy", text_ctxt=ctxt)
        row.prop(self, "popup_scale", text_ctxt=ctxt)
        row.prop(self, "enable_hq_preview", text="", icon="IMAGE_BACKGROUND", text_ctxt=ctxt)
        row = layout.row(align=True)
        row.prop(self, "ip")
        row.prop(self, "port")
        row = layout.row(align=True)
        row.prop(self, "fixed_preview_image_size", toggle=True, text_ctxt=ctxt)
        row.prop(self, "preview_image_size", text_ctxt=ctxt)
        row = layout.row(align=True)
        row.label(text="Drag Link Result Count", text_ctxt=ctxt)
        row.prop(self, "drag_link_result_count_col", text="", text_ctxt=ctxt)
        row.prop(self, "drag_link_result_count_row", text="", text_ctxt=ctxt)
        if self.server_type == "Local":
            row = layout.row(align=True)
            row.prop(self, "auto_launch", toggle=True, text_ctxt=ctxt)
            row.prop(self, "install_deps", toggle=True, text_ctxt=ctxt)
            row.prop(self, "force_log", toggle=True, text_ctxt=ctxt)
        row = layout.row(align=True)
        row.prop(self, "view_context", toggle=True, text_ctxt=ctxt)
        row.prop(self, "rt_track_freq", text_ctxt=ctxt)
        self.draw_custom_presets(layout)
        if self.server_type == "Local":
            box = layout.box()
            box.label(text="Advanced", text_ctxt=ctxt)
            args = self.parse_server_args()
            row = box.row(align=True)
            row.label(text=" ".join(args), text_ctxt=ctxt)
            row.prop(self, "copy_args", toggle=True, text_ctxt=ctxt, text="", icon="COPYDOWN")
            # 新增参数
            box.prop(self, "cuda_malloc", text_ctxt=ctxt)
            box.prop(self, "fp", text_ctxt=ctxt)
            box.prop(self, "fpunet", text_ctxt=ctxt)
            box.prop(self, "fpvae", text_ctxt=ctxt)
            box.prop(self, "fpte", text_ctxt=ctxt)
            box.prop(self, "attn", text_ctxt=ctxt)
            box.prop(self, "preview_method", text_ctxt=ctxt, toggle=True)
            row = box.row(align=True)
            row.prop(self, "dont_upcast_attention", text_ctxt=ctxt, toggle=True)
            row.prop(self, "disable_ipex_optimize", text_ctxt=ctxt, toggle=True)
            row = box.row(align=True)
            row.prop(self, "disable_xformers", text_ctxt=ctxt, toggle=True)
            row.prop(self, "disable_smart_memory", text_ctxt=ctxt, toggle=True)
            row = box.row(align=True)
            row.prop(self, "deterministic", text_ctxt=ctxt, toggle=True)
            row.prop(self, "dont_print_server", text_ctxt=ctxt, toggle=True)
            row = box.row(align=True)
            row.prop(self, "disable_metadata", text_ctxt=ctxt, toggle=True)
            row.prop(self, "windows_standalone_build", text_ctxt=ctxt, toggle=True)
        layout.prop(self, "debug", toggle=True, text_ctxt=ctxt)

    def draw_website(self, layout: bpy.types.UILayout):

        layout.label(text="-AIGODLIKE Adventure Community", text_ctxt=ctxt)
        row = layout.row()
        row.operator("wm.url_open", text="AIGODLIKE Open Source Community - Main Site", icon="URL", text_ctxt=ctxt).url = "https://www.aigodlike.com"
        row.label(text=" ", text_ctxt=ctxt)

        layout.label(text="-Good friends exploring in the AI world (alphabetical order)", text_ctxt=ctxt)
        col = layout.column(align=True)
        col.scale_y = 1.1
        row = col.row(align=True)
        icon_id = Icon().get_icon_id("up")
        row.operator("wm.url_open", text="独立研究员-星空", icon_value=icon_id, text_ctxt=ctxt).url = "https://space.bilibili.com/250989068"
        row.operator("wm.url_open", text="秋葉aaaki", icon_value=icon_id, text_ctxt=ctxt).url = "https://space.bilibili.com/12566101"
        row = col.row(align=True)
        row.operator("wm.url_open", text="小李xiaolxl", icon_value=icon_id, text_ctxt=ctxt).url = "https://space.bilibili.com/34590220"

        row.operator("wm.url_open", text="元素法典制作委员会", icon_value=icon_id, text_ctxt=ctxt).url = "https://space.bilibili.com/1981251194"
        row.operator("wm.url_open", text="只剩一瓶辣椒酱", icon_value=icon_id, text_ctxt=ctxt).url = "https://space.bilibili.com/35723238"

        layout.label(text="\"Thank you, these adventurers who are exploring and sharing their experience in the AI field, hurry up and follow them\"", text_ctxt=ctxt)

    def draw_path(self, layout: bpy.types.UILayout):
        row = layout.row()
        row.prop(self, "open_dir1", toggle=True, text_ctxt=ctxt)
        row.prop(self, "open_dir2", toggle=True, text_ctxt=ctxt)
        row.prop(self, "open_dir3", toggle=True, text_ctxt=ctxt)
        row.prop(self, "open_dir4", toggle=True, text_ctxt=ctxt)

    def draw(self, context):
        self.layout.row(align=True).prop(self, "page", expand=True, text_ctxt=ctxt)
        box = self.layout.box()
        if self.page == "通用":
            self.draw_general(box)
        elif self.page == "常用路径":
            self.draw_path(box)
        elif self.page == "友情链接":
            self.draw_website(box)


def get_pref() -> AddonPreference:
    import bpy
    return bpy.context.preferences.addons[__package__].preferences


@bpy.app.handlers.persistent
def pref_dirs_init(_):
    # 将pref_dirs 添加到 FSWatcher
    pref = get_pref()

    for item in pref.pref_dirs:
        logger.info(f"FS Register -> {item.path}")
        p = Path(item.path)
        if pref.pref_dirs_init:
            # 创建presets/groups目录
            p.joinpath("presets").mkdir(parents=True, exist_ok=True)
            p.joinpath("groups").mkdir(parents=True, exist_ok=True)
        FSWatcher.register(p.joinpath("presets"), dir_cb_test)
        FSWatcher.register(p.joinpath("groups"), dir_cb_test)


clss = [PresetsDirDesc, PresetsDirEdit, AddonPreference]
reg, unreg = bpy.utils.register_classes_factory(clss)


def pref_register():
    bpy.app.handlers.load_post.append(pref_dirs_init)
    reg()
    toggle_debug(get_pref().debug)


def pref_unregister():
    unreg()
    bpy.app.handlers.load_post.remove(pref_dirs_init)
