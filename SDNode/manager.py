from __future__ import annotations
import os
import re
import shutil
import sys
import json
import time
import atexit
import signal
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from mathutils import Color
from functools import lru_cache
from copy import deepcopy
from shutil import rmtree
from urllib import request
from urllib.error import URLError
from threading import Thread
from subprocess import Popen, PIPE
from pathlib import Path
from queue import Queue
from ..utils import rmtree as rt, logger, _T, PkgInstaller, FSWatcher
from ..timer import Timer
from ..preference import get_pref
from .history import History
from .websocket import WebSocketApp

def get_ip():
    return TaskManager.server.get_ip()


def get_port():
    return TaskManager.server.get_port()


def get_url():
    return TaskManager.server.get_url()


WITH_PROXY = False
if not WITH_PROXY:
    request.install_opener(request.build_opener(request.ProxyHandler({})))
# wmpp 指定到WebUI路径
# wmp 指定到 WebUI/models 路径
a111_yaml = """
a111:
    base_path: {wmpp}

    checkpoints: {wmp}/Stable-diffusion
    configs: {wmp}/Stable-diffusion
    vae: {wmp}/VAE
    loras: {wmp}/Lora
    upscale_models: |
                  {wmp}/ESRGAN
                  {wmp}/SwinIR
    embeddings: {wmpp}/embeddings
    controlnet: {wmp}/ControlNet
            """
# cmpp 指定到ComfyUI路径
# cmp 指定到 ComfyUI/models 路径
custom_comfyui = """
mycomfyui:
    base_path: {cmpp}
    checkpoints: {cmp}/checkpoints
    configs: {cmp}/configs
    loras: {cmp}/loras
    vae: {cmp}/vae
    clip: {cmp}/clip
    clip_vision: {cmp}/clip_vision
    style_models: {cmp}/style_models
    embeddings: {cmp}/embeddings
    diffusers: {cmp}/diffusers
    controlnet: {cmp}/controlnet
    gligen: {cmp}/gligen
    upscale_models: {cmp}/upscale_models
    hypernetworks: {cmp}/hypernetworks
    #custom_nodes: {cmpp}/custom_nodes
            """


class Task:
    def __init__(self, task=None, pre=None, post=None, tree=None) -> None:
        self.task = task
        self.res = Queue()
        self._pre = pre
        self._post = post
        from .tree import CFNodeTree
        self.tree: CFNodeTree = tree
        self.executing_node_id = ""
        self.executing_node = None
        self.is_finished = False
        self.process = {}
        # 记录node的类型 防止节点树变更
        self.node_ref_map = {}
        if not tree:
            return
        self.node_ref_map = {n.id: n.bl_idname for n in tree.nodes if hasattr(n, "id")}

    def submit_pre(self):
        if not self._pre:
            return
        self._pre()

    def post(self):
        if not self._post:
            return
        self._post()

    def is_tree_valid(self):
        if not self.tree:
            return False
        try:
            if self.tree.id_data != self.tree:
                raise ReferenceError
        except ReferenceError:
            return False
        except Exception:
            import traceback
            traceback.print_exc()
            return False
        return True

    def set_finished(self):
        self.is_finished = True
        def f(self: Task):
            if not self.is_tree_valid():
                return
            for n in self.tree.nodes:
                if not n.label.endswith("-EXEC"):
                    continue
                n.use_custom_color = False
                n.label = ""
        Timer.put((f, self))

    def set_executing_node_id(self, node_id):
        self.executing_node_id = node_id

        def f(self: Task):
            if not self.is_tree_valid():
                return
            self.process = {}
            if self.executing_node:
                self.executing_node.use_custom_color = False
                self.executing_node.label = ""
            self.executing_node = None
            for n in self.tree.nodes:
                if not hasattr(n, "id"):
                    continue
                if n.id == node_id and n.bl_idname == self.node_ref_map.get(node_id, ""):
                    self.executing_node = n
                    break
            n = self.executing_node
            n.use_custom_color = True
            n.color = (0, 0, 0)
            n.label = n.name + "-EXEC"
        Timer.put((f, self))

    def set_process(self, process, node_id=""):
        """
        process: {'value': 20, 'max': 20}
        """
        # if not node_id:
        #     node_id = self.executing_node_id
        def f(self: Task):
            if not self.is_tree_valid():
                return
            if not self.executing_node:
                return
            self.process = process
        Timer.put((f, self))
        # self.tree.display_process()


class TaskErrPaser:
    class ErrType:
        WITH_ORI = True
        WITH_INFO = True
        WITH_PRINT = True

        def get_print(self, info):
            etype = info["type"]
            func = getattr(self, etype, self.unknown)
            return func(info)

        def unknown(self, info):
            if self.WITH_PRINT:
                print(info)
            return []

        def __print__(self, info):
            msg = _T(info["message"]).strip()
            dt = _T(info["details"]).strip()
            if self.WITH_ORI:
                if msg:
                    msg += " --> " + info["message"]
                if dt:
                    dt += " --> " + info["details"]
            if self.WITH_PRINT:
                print(msg)
                print(dt)
            if self.WITH_INFO and self.WITH_PRINT:
                print(info)
            info_list = []
            if msg:
                info_list.append(msg)
            if dt:
                info_list.append(dt)
            return info_list

        def required_input_missing(self, info):
            required_input_missing = 0
            error0 = {
                "type": "required_input_missing",
                "message": "Required input is missing",
                "details": "{x}",
                "extra_info": {
                    "input_name": "{x}"
                }
            }
            return self.__print__(info)

        def bad_linked_input(self, info):
            bad_linked_input = 1
            error1 = {
                "type": "bad_linked_input",
                "message": "Bad linked input, must be a length-2 list of [node_id, slot_index]",
                "details": "{x}",
                "extra_info": {
                    "input_name": "{x}",
                    "input_config": "{info}",
                    "received_value": "{val}"
                }
            }
            return self.__print__(info)

        def return_type_mismatch(self, info):
            return_type_mismatch = 2
            error2 = {
                "type": "return_type_mismatch",
                "message": "Return type mismatch between linked nodes",
                "details": "{details}",
                "extra_info": {
                    "input_name": "{x}",
                    "input_config": "{info}",
                    "received_type": "{received_type}",
                    "linked_node": "{val}"
                }
            }
            return self.__print__(info)

        def invalid_input_type(self, info):
            invalid_input_type = 3
            error3 = {
                "type": "invalid_input_type",
                "message": "Failed to convert an input value to a {type_input} value",
                "details": "{x}, {val}, {ex}",
                "extra_info": {
                    "input_name": "{x}",
                    "input_config": "{info}",
                    "received_value": "{val}",
                    "exception_message": "{str(ex)}"
                }
            }
            # 匹配message
            type_input = re.match(r"Failed to convert an input value to a (.+) value", info["message"]).groups()
            msg = _T("Failed to convert an input value to a {type_input} value").format(type_input)
            self.__print__(info)
            return (msg,)

        def value_smaller_than_min(self, info):
            value_smaller_than_min = 4
            error4 = {
                "type": "value_smaller_than_min",
                "message": "Value {val} smaller than min of {min}",
                "details": "{x}",
                "extra_info": {
                    "input_name": "{x}",
                    "input_config": "{info}",
                    "received_value": "{val}",
                }
            }
            self.__print__(info)
            # 匹配message
            val, min = re.match(r"Value (.+) smaller than min of (.+)", info["message"]).groups()
            msg = _T("Value {val} smaller than min of {min}").format(val, min)
            return (msg,)

        def value_bigger_than_max(self, info):
            value_bigger_than_max = 5
            error5 = {
                "type": "value_bigger_than_max",
                "message": "Value {val} bigger than max of {max}",
                "details": "{x}",
                "extra_info": {
                    "input_name": "{x}",
                    "input_config": "{info}",
                    "received_value": "{val}",
                }
            }
            self.__print__(info)
            val, max = re.match(r"Value (.+) bigger than max of (.+)", info["message"]).groups()
            msg = _T("Value {val} bigger than max of {max}").format(val, max)
            return (msg,)

        def custom_validation_failed(self, info):
            custom_validation_failed = 6
            error6 = {
                "type": "custom_validation_failed",
                "message": "Custom validation failed for node",
                "details": "{details}",
                "extra_info": {
                    "input_name": "{x}",
                    "input_config": "{info}",
                    "received_value": "{val}",
                }
            }
            return self.__print__(info)

        def value_not_in_list(self, info):
            value_not_in_list = 7
            error7 = {
                "type": "value_not_in_list",
                "message": "Value not in list",
                "details": "{x}: '{val}' not in {list_info}",
                "extra_info": {
                    "input_name": "{x}",
                    "input_config": "{input_config}",
                    "received_value": "{val}",
                }
            }
            return self.__print__(info)

        def prompt_no_outputs(self, info):
            prompt_no_outputs = 8
            error8 = {
                "type": "prompt_no_outputs",
                "message": "Prompt has no outputs",
                "details": "",
                "extra_info": {}
            }
            return self.__print__(info)

        def exception_during_validation(self, info):
            exception_during_validation = 9
            error9 = {
                "type": "exception_during_validation",
                "message": "Exception when validating node",
                "details": "{str(ex)}",
                "extra_info": {
                    "exception_type": "{exception_type}",
                    "traceback": "{traceback.format_tb(tb)}"
                }
            }
            return self.__print__(info)

        def prompt_outputs_failed_validation(self, info):
            prompt_outputs_failed_validation = 10
            error10 = {
                "type": "prompt_outputs_failed_validation",
                "message": "Prompt outputs failed validation",
                "details": "{errors_list}",
                "extra_info": {}
            }
            return self.__print__(info)

        def exception_during_inner_validation(self, info):
            exception_during_inner_validation = 11
            error11 = {
                "type": "exception_during_inner_validation",
                "message": "Exception when validating inner node",
                "details": "{str(ex)}",
                "extra_info": {
                    "input_name": "{x}",
                    "input_config": "{info}",
                    "exception_message": "{str(ex)}",
                    "exception_type": "{exception_type}",
                    "traceback": "{traceback.format_tb(tb)}",
                    "linked_node": "{val}"
                }
            }
            return self.__print__(info)

    def decode_info(self, e: request.HTTPError):
        try:
            self.error_info = json.loads(e.read().decode())
        except BaseException:
            self.error_info = {}

    def parse(self, e: request.HTTPError):
        self.decode_info(e)
        if not self.error_info:
            return
        print(self.error_info)
        self.error_parse()
        self.node_error_parse()

    def error_parse(self):
        if "error" not in self.error_info:
            return
        info_list = TaskErrPaser.ErrType().get_print(self.error_info["error"])
        logger.error(info_list)
        for ei in info_list:
            TaskManager.put_error_msg(ei)
        return
        error = self.error_info["error"]
        err_type = error.get("type", "")
        msg = error.get("message", "")
        details = error.get("details", "")
        extra_info = error.get("extra_info", "")
        print(f"Error Type: {err_type}")
        print(f"Message: {msg}")
        print(f"Details: {details}")
        print(f"Extra Info: {extra_info}")
        # type message details extra_info

    def node_error_parse(self):
        if "node_errors" not in self.error_info:
            return
        template = {"10": {"errors": [{"type": "value_not_in_list",
                                       "message": "Value not in list",
                                       "details": "vae_name: '' not in []",
                                       "extra_info": {"input_name": "vae_name",
                                                      "input_config": [[]],
                                                      "received_value": ""}}
                                      ],
                           "dependent_outputs": ["9"],
                           "class_type": "VAELoader"}}
        node_errors = self.error_info["node_errors"]
        import bpy
        from .tree import get_tree
        logger.error("Node Error Parse")
        for sc in bpy.data.screens:
            try:
                tree = get_tree(screen=sc)
                if tree:
                    break
            except Exception as e:
                print(e)
        try:
            for node in node_errors:
                print(f"Node:{node}")
                for n in tree.nodes:
                    if n.id == str(node):
                        n.use_custom_color = True
                        n.color = (1, 0, 0)
                        n.label = n.name + "-ERROR"
                        TaskManager.put_error_msg(n.name)
                for err in node_errors[node]["errors"]:
                    for ei in TaskErrPaser.ErrType().get_print(err):
                        TaskManager.put_error_msg("    -- " + ei)
                    # print(f"\t->", err)
        except Exception as e:
            print(e)


class Server:
    _instance: Server = None
    stdout_listen_exited = False
    uid = 0

    def __new__(cls, *args, **kw):
        if cls._instance is None:
            cls._instance = object.__new__(cls, *args, **kw)
        return cls._instance

    def __init__(self) -> None:
        self.launch_ip = "127.0.0.1"
        self.launch_port = 8188
        self.launch_url = "http://127.0.0.1:8188"

    def run(self) -> bool:
        self.uid = time.time_ns()
        TaskManager.clear_error_msg()
        return True

    def close(self):
        ...

    def exit_track(self):
        ...

    def wait_connect(self) -> bool:
        return True

    def is_launched(self) -> bool:
        return False

    def get_ip(self):
        if self.is_launched():
            return self.launch_ip
        ip = get_pref().ip
        return ip

    def get_port(self):
        if self.is_launched():
            return self.launch_port
        port = get_pref().port
        return port

    def get_url(self):
        if self.is_launched():
            return self.launch_url
        return f"http://{get_ip()}:{get_port()}"


class FakeServer(Server):
    ...


class RemoteServer(Server):

    def __init__(self) -> None:
        self.server_connected = False
        super().__init__()

    def run(self) -> bool:
        self.server_connected = False
        TaskManager.clear_error_msg()
        self.uid = time.time_ns()
        self.launch_ip = get_ip()
        self.launch_port = get_port()
        self.launch_url = f"http://{self.launch_ip}:{self.launch_port}"
        return self.wait_connect()

    def wait_connect(self) -> bool:
        import requests
        try:
            if requests.get(f"{self.get_url()}/object_info", proxies={"http": None, "https": None}).status_code == 200:
                self.server_connected = True
                return True
        except requests.exceptions.ConnectionError as e:
            TaskManager.put_error_msg(str(e))
        except Exception as e:
            logger.error(e)
        TaskManager.put_error_msg(_T("Remote Server Connect Failed") + f": {self.get_url()}")
        return False

    def is_launched(self) -> bool:
        return self.server_connected
    
    def close(self):
        self.server_connected = False
        logger.warn(_T("Remote Server Closed"))

class LocalServer(Server):
    def __init__(self) -> None:
        self.pid = -1
        self.child: Popen = None
        self.stdout_listen_exited = False
        super().__init__()

    def run(self) -> bool:
        TaskManager.clear_error_msg()
        self.uid = time.time_ns()
        pidpath = Path(__file__).parent / "pid"
        if pidpath.exists():
            self.force_kill(pidpath.read_text())
            pidpath.unlink()

        pref = get_pref()
        model_path = pref.model_path
        if not model_path or not Path(model_path).exists():
            logger.error(_T("ComfyUI Path Not Found"))
            TaskManager.put_error_msg(_T("ComfyUI Path Not Found"))
            return
        logger.debug(f"{_T('Model Path')}: {model_path}")
        python = self.get_python()
        if pref.install_deps:
            self.run_pre(model_path)

        logger.warn(_T("Server Launching"))
        if sys.platform == "win32" and not python.exists():
            logger.error(f"{_T('python interpreter not found')}:")
            logger.error(f"   ↳{_T('Ensure that the python_embeded located in the same level as ComfyUI dir')}:")
            logger.error("      SomeDirectory")
            logger.error("      ├─ ComfyUI")
            logger.error("      ├─ python_embeded")
            logger.error("      │ ├─ python.exe")
            logger.error("      │ └─ ...")
            logger.error("      └─ ...")
            return

        # custom_nodes
        for file in (Path(__file__).parent / "custom_nodes").iterdir():
            if file.is_dir():
                dst = Path(model_path) / "custom_nodes" / file.name
                if dst.exists():
                    rt(dst)
                shutil.copytree(file, Path(model_path) / "custom_nodes" / file.name, dirs_exist_ok=True)
                continue
            if not file.suffix == ".py":
                continue
            if file.name == "cup.py":
                t = file.read_text(encoding="utf-8")
                t = t.replace("XXXHOST-PATHXXX", Path(__file__).parent.as_posix())
                t = t.replace("FORCE_LOG = False", f"FORCE_LOG = {get_pref().force_log}")
                (Path(model_path) / "custom_nodes" / file.name).write_text(t, encoding="utf-8")
                continue
            shutil.copyfile(file, Path(model_path) / "custom_nodes" / file.name)
        args = self.create_args(python, Path(model_path))
        self.launch_ip = get_ip()
        self.launch_port = get_port()
        self.launch_url = f"http://{self.launch_ip}:{self.launch_port}"
        # cmd = " ".join([str(python), arg])
        # 加了 stderr后 无法获取 进度?
        # logger.debug(" ".join(args))
        import bpy
        if bpy.app.version >= (3, 6):
            p = Popen(args, stdout=PIPE, cwd=Path(model_path).resolve().as_posix())
        else:
            p = Popen(args, stdout=PIPE, cwd=Path(model_path).resolve().as_posix())
        self.child = p
        self.pid = p.pid
        pidpath.write_text(str(p.pid))
        atexit.register(self.child.kill)
        Thread(target=self.stdout_listen, daemon=True).start()
        return self.wait_connect()

    def close(self):
        pidpath = Path(__file__).parent / "pid"
        if pidpath.exists():
            self.force_kill(pidpath.read_text())
            pidpath.unlink()

        if self.child:
            self.child.kill()
        self.child = None
        self.pid = -1

    def wait_connect(self) -> bool:
        while True:
            import requests
            try:
                if requests.get(f"{self.get_url()}/object_info", proxies={"http": None, "https": None}, timeout=1).status_code == 200:
                    return True
            except requests.exceptions.ConnectionError:
                ...
            except Exception as e:
                logger.error(e)
            if self.stdout_listen_exited:
                break
            time.sleep(0.1)
        return False

    def is_launched(self) -> bool:
        return self.pid != -1

    def force_kill(self, pid):
        if not pid:
            return

        if not PkgInstaller.try_install("psutil"):
            logger.error("psutil not installed please disable proxy and try again!")
            return
        if not PkgInstaller.is_installed("psutil"):
            logger.error("psutil not installed please disable proxy and try again!")
            return
        import psutil
        pid = int(pid)
        if sys.platform == "win32":
            try:
                process = psutil.Process(pid)
                if "python" not in process.name():
                    return
                process.kill()
                # os.system(f'taskkill /F /IM {process.name()}')
                os.system(f'taskkill /pid {pid} -t -f')
            except psutil.NoSuchProcess:
                return
        elif sys.platform == "darwin":
            try:
                process = psutil.Process(pid)
                if "python" in process.name().lower():
                    # process.kill()
                    os.system(f"kill -9 {pid}")
            except psutil.NoSuchProcess:
                return
        else:
            ...
            # os.kill(pid, signal.SIGKILL)
        logger.error(f"{_T('Kill Last ComfyUI Process')} id -> {pid}")

    def get_python(self):
        python = Path("python3")
        custom_python = Path(get_pref().python_path)
        if get_pref().python_path and custom_python.exists():
            if custom_python.is_dir():
                if sys.platform == "win32":
                    python = custom_python / "python.exe"
                else:
                    python = custom_python / "python3"
            else:
                python = custom_python
        elif sys.platform == "win32":
            model_path = get_pref().model_path
            python = Path(model_path).parent / "python_embeded/python.exe"
        return python

    def run_pre(self, model_path):
        """
        Check pre install
        """
        # controlnet check
        logger.warn(_T("ControlNet Init...."))
        python = self.get_python()

        controlnet = Path(model_path) / "custom_nodes/comfy_controlnet_preprocessors"
        if controlnet.exists():
            fvcore = python.parent / "Lib/site-packages/fvcore"
            if not fvcore.exists():
                command = [python.as_posix()]
                command.append("-s")
                command.append("-m")
                command.append("pip")
                command.append("install")
                command.append("-r")
                command.append((controlnet / "requirements.txt").as_posix())
                command.append("--extra-index-url")
                command.append("https://download.pytorch.org/whl/cu117")
                command.append("--no-warn-script-location")
                if fast_url := PkgInstaller.select_pip_source():
                    site = urlparse(fast_url)
                    command.append("-i")
                    command.append(fast_url)
                    command.append("--trusted-host")
                    command.append(site.netloc)
                proc = Popen(command, cwd=model_path)
                proc.wait()

        logger.warn(_T("ControlNet Init Finished."))
        logger.warn(_T("If controlnet still not worked, install manually by double clicked {}").format((controlnet / "install.bat").as_posix()))

    def create_args(self, python: Path, model_path: Path):
        pref = get_pref()
        args = [python.as_posix()]
        # arg = f"-s {str(model_path)}/main.py"
        args.append("-s")

        # 备份main.py 为 main-bak.py
        # 为main-bak.py新增 sys.path代码
        try:
            with open(model_path.joinpath("main.py"), "r", encoding="utf-8") as f:
                mainpy = f.read()
                mainpy = "sys.path.append(r\"{}\")\n".format(model_path.as_posix()) + mainpy
                mainpy = "import sys\n" + mainpy
                Path(model_path.joinpath("main-bak.py")).write_text(mainpy, encoding="utf-8")
        except BaseException:
            ...
        if get_pref().python_path and Path(get_pref().python_path).exists() and Path(model_path.joinpath("main-bak.py")).exists():
            args.append(f"{model_path.joinpath('main-bak.py').resolve().as_posix()}")
        else:
            args.append(f"{model_path.joinpath('main.py').resolve().as_posix()}")

        def parse_comfyUIStart():
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
                        get_pref().ip = ip
                    if port := re.match(r".*?--port\s+([0-9]+)", piece):
                        get_pref().port = int(port.group(1))
                config = " ".join(config)
                config = re.split(r"\s(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", config)
                logger.info(f"{_T('Reparse Config')}: {config}")
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
                logger.info(f"{_T('Find Config')}: {config}")
            except IndexError:
                logger.error(_T("No Config File Found"))
            except Exception as e:
                logger.error(_T("Parse Config Error: {e}").format(e))
            return config
        # [ 'comfyUIStart', 'startConfigureFile.json']
        if "comfyUIStart" in sys.argv:
            args.extend(parse_comfyUIStart())
        else:
            args.append("--listen")
            args.append(get_ip())
            args.append("--port")
            args.append(f"{get_port()}")
            if pref.cuda.isdigit():
                args.append("--cuda-device")
                args.append(pref.cuda)
            if pref.cpu_only:
                # arg += " --cpu"
                args.append("--cpu")
            else:
                # arg += f" {pref.mem_level}"
                args.append(f"{pref.mem_level}")
            yaml = ""
            if pref.with_webui_model and Path(pref.with_webui_model).exists():
                wmp = Path(pref.with_webui_model).as_posix()
                wmpp = Path(pref.with_webui_model).parent.as_posix()
                yaml += a111_yaml.format(wmp=wmp, wmpp=wmpp)
            if pref.with_comfyui_model and Path(pref.with_comfyui_model).exists():
                cmp = Path(pref.with_comfyui_model).as_posix()  # 指定到 models
                cmpp = Path(pref.with_comfyui_model).parent.as_posix()
                yaml += custom_comfyui.format(cmp=cmp, cmpp=cmpp)
            if yaml:
                extra_model_paths = Path(__file__).parent / "config.yaml"
                extra_model_paths.write_text(yaml)
                args.append("--extra-model-paths-config")
                args.append(extra_model_paths.as_posix())
        # 特殊处理
        if pref.auto_launch:
            args.append("--auto-launch")
        return args

    def stdout_listen(self):
        p = self.child
        while p.poll() is None and self.child == p:
            line = p.stdout.readline().strip()
            if not line:
                continue
            # logger.info(line)
            # print(re.findall("\|(.*?)[", line.decode("gbk")))
            if b"CUDA out of memory" in line or b"not enough memory" in line:
                TaskManager.put_error_msg(f"{_T('Error: Out of VRam, try restart blender')}")
            proc = ""
            for coding in ["gbk", "utf8"]:
                try:
                    line = line.decode(coding)
                    proc = re.findall("[█ ]\\| (.*?) \\[", line)
                    break
                except UnicodeDecodeError:
                    ...
            if not proc:
                logger.info(line)
        self.stdout_listen_exited = True
        logger.debug(_T("STDOUT Listen Thread Exit"))


class TaskManager:
    _instance = None
    server: Server = FakeServer()
    task_queue = Queue()
    res_queue = Queue()
    SessionId = {"SessionId": "ComfyUICUP" + str(time.time_ns())}
    status = {}
    progress = {}
    executing = {}
    cur_task: Task = None
    execute_status_record = []
    error_msg = []
    progress_bar = 0
    executer = ThreadPoolExecutor(max_workers=1)
    ws:WebSocketApp = None

    def __new__(cls, *args, **kw):
        if cls._instance is None:
            cls._instance = object.__new__(cls, *args, **kw)
        return cls._instance

    def put_error_msg(error):
        TaskManager.error_msg.append(str(error))

    def clear_error_msg():
        TaskManager.error_msg.clear()

    def get_error_msg(copy=False):
        if copy:
            return deepcopy(TaskManager.error_msg)
        return TaskManager.error_msg

    def get_progress():
        return TaskManager.progress

    def get_task_num():
        return TaskManager.task_queue.qsize()

    def is_launched() -> bool:
        if TaskManager.server:
            return TaskManager.server.is_launched()
        return False
        if TaskManager.connect_existing:
            return True
        return TaskManager.pid != -1

    def run_server(fake=False):
        import time
        from .tree import rtnode_reg, rtnode_unreg
        t1 = time.time()
        rtnode_unreg()
        t2 = time.time()
        logger.info(_T("UnregNode Time:") + f" {t2-t1:.2f}s")
        run_success = TaskManager.init_server(fake=fake)
        if not fake and not run_success:
            TaskManager.init_server(fake=True)
        t3 = time.time()
        logger.info(_T("Launch Time:") + f" {t3-t2:.2f}s")
        t3 = time.time()
        rtnode_reg()
        t4 = time.time()
        logger.info(_T("RegNode Time:") + f" {t4-t3:.2f}s")

    def init_server(fake=False):
        if fake:
            TaskManager.server = FakeServer()
            return
        if get_pref().server_type == "Local":
            TaskManager.server = LocalServer()
        else:
            TaskManager.server = RemoteServer()
        running = TaskManager.server.run()
        if not TaskManager.server.stdout_listen_exited and running:
            logger.warn(_T("Server Launched"))
            TaskManager.start_polling()
            Timer.clear()  # timer may cause crash
        else:
            logger.error(_T("Server Launch Failed"))
            TaskManager.server.close()
        return running

    def start_polling():
        Thread(target=TaskManager.poll_res, daemon=True).start()
        Thread(target=TaskManager.poll_task, daemon=True).start()
        Thread(target=TaskManager.proc_res, daemon=True).start()

    def restart_server(fake=False):
        TaskManager.clear_all()
        TaskManager.server.close()
        TaskManager.run_server(fake=fake)

    def close_server():
        if TaskManager.ws:
            TaskManager.ws.close()
            TaskManager.ws = None
        TaskManager.cur_task = None
        TaskManager.restart_server(fake=True)
        
    def push_task(task, pre=None, post=None, tree=None):
        logger.debug(_T('Add Task'))
        if not TaskManager.is_launched():
            TaskManager.put_error_msg(_T("Server Not Launched, Add Task Failed"))
            TaskManager.put_error_msg(_T("Please Check ComfyUI Directory"))
            logger.error(_T("Server Not Launched"))
            return
        TaskManager.task_queue.put(Task(task, pre=pre, post=post, tree=tree))

    def push_res(res):
        logger.debug(_T("Add Result"))
        TaskManager.cur_task.res.put(res)
        TaskManager.res_queue.put(TaskManager.cur_task)

    def clear_cache():
        req = request.Request(f"{TaskManager.server.get_url()}/cup/clear_cache", method="POST")
        try:
            request.urlopen(req)
        except URLError:
            ...

    # def get_temp_directory():
    #     req = request.Request(f"{TaskManager.server.get_url()}/cup/get_temp_directory", method="POST")
    #     try:
    #         res = request.urlopen(req)
    #         return res.read().decode()
    #     except Exception as e:
    #         ...
    #     return ""

    def interrupt():
        req = request.Request(f"{TaskManager.server.get_url()}/interrupt", method="POST")
        try:
            request.urlopen(req)
        except URLError:
            ...

    def clear_all():
        TaskManager.interrupt()
        while not TaskManager.task_queue.empty():
            TaskManager.task_queue.get()
        TaskManager.progress = {}

    @staticmethod
    def poll_task():
        uid = TaskManager.server.uid
        while uid == TaskManager.server.uid:
            time.sleep(0.1)
            if TaskManager.progress:
                continue
            if TaskManager.task_queue.empty():
                continue
            task = TaskManager.task_queue.get()
            TaskManager.progress = {'value': 0, 'max': 1}
            logger.debug(_T("Submit Task"))
            TaskManager.cur_task = task
            TaskManager.submit(task)
        logger.debug(_T("Poll Task Thread Exit"))

    def query_server_task():
        if not TaskManager.is_launched():
            return {"queue_pending": [], "queue_running": []}
        try:
            req = request.Request(f"{TaskManager.server.get_url()}/queue")
            res = request.urlopen(req)
            res = json.loads(res.read().decode())
        except BaseException:
            res = {"queue_pending": [], "queue_running": []}
        return res

    def submit(task: Task):
        task.submit_pre()
        task: dict[str, tuple] = task.task
        prompt = task["prompt"]
        for node in prompt:
            prompt[node][1]()
        TaskManager.clear_error_msg()

        def queue_task(task: dict):
            res = TaskManager.query_server_task()
            logger.debug("P/R: %s/%s", len(res["queue_pending"]), len(res["queue_running"]))

            api = task.get("api")
            if api == "prompt":
                prompt = {node: task.get("prompt")[node][0] for node in task.get("prompt")}

                cid = TaskManager.SessionId["SessionId"]
                content = {"client_id": cid,
                           "prompt": prompt,
                           "extra_data": {
                               "extra_pnginfo": {"workflow": task.get("workflow")}
                           }}
                data = json.dumps(content).encode()
                req = request.Request(f"{TaskManager.server.get_url()}/{api}", data=data)
                History.put_history(task.get("workflow"))
                # logger.debug(f'post to {TaskManager.server.get_url()}/{api}:')
                # logger.debug(data.decode())
                try:
                    request.urlopen(req)
                except request.HTTPError as e:
                    print(_T("Invalid Node Connection"))
                    TaskManager.put_error_msg(_T("Invalid Node Connection"))
                    err_parser = TaskErrPaser()
                    err_parser.parse(e)
                    if err_parser.error_info:
                        TaskManager.mark_finished_with_info([])
                    else:
                        TaskManager.mark_finished()
                except URLError:
                    TaskManager.put_error_msg(_T("Server Not Launched"))
                    TaskManager.mark_finished(with_noexe=False)
                except Exception as e:
                    logger.error(e)
                    TaskManager.put_error_msg(str(e))
                    TaskManager.mark_finished(with_noexe=False)
            else:
                ...
        TaskManager.executer.submit(queue_task, task)
        # Thread(target=queue_task, args=(task, )).start()

    def mark_finished(with_noexe=True):
        TaskManager.progress = {}
        TaskManager.cur_task = None
        if not TaskManager.execute_status_record and with_noexe:
            TaskManager.put_error_msg(_T("Node Tree Not Executed, May Caused by:"))
            TaskManager.put_error_msg(f"    1.{_T('Params Not Changed')}")
            TaskManager.put_error_msg(f"    2.{_T('Input Image Error')}")
            TaskManager.put_error_msg(f"    3.{_T('Node Connection Error')}")
            TaskManager.put_error_msg(f"    4.{_T('Server Not Launched')}")
        TaskManager.execute_status_record.clear()

    def mark_finished_with_info(info):
        TaskManager.progress = {}
        TaskManager.cur_task = None
        for i in info:
            TaskManager.put_error_msg(i)
        TaskManager.execute_status_record.clear()

    def proc_res():
        uid = TaskManager.server.uid
        while uid == TaskManager.server.uid:
            time.sleep(0.1)
            if TaskManager.res_queue.empty():
                continue
            task = TaskManager.res_queue.get()
            if task.res.empty():
                continue
            logger.debug(_T("Proc Result"))
            res = task.res.get()
            node = res["node"]
            prompt = task.task["prompt"]
            if node in prompt:
                prompt[node][2](task, res)
        logger.debug(_T("Proc Task Thread Exit"))

    @staticmethod
    def poll_res():
        tm = TaskManager
        SessionId = TaskManager.SessionId

        def on_message(ws, message):
            msg = json.loads(message)
            mtype = msg["type"]
            data = msg["data"]
            if mtype == "executing":
                n = data.get('node', '')
                if n:
                    logger.debug(f"{_T('Executing Node')}: {n}")
            elif mtype == "execution_start":
                ...
            elif mtype == "execution_cached":
                logger.debug(f"{_T('Execution Cached')}: {data.get('nodes', '')}")
            elif mtype == "status":
                ...
            elif mtype != 'progress':
                logger.debug(f'{_T("got response")}: {message}')

            def update():
                import bpy
                for area in bpy.context.screen.areas:
                    area.tag_redraw()
            Timer.put(update)

            if hasattr(tm, mtype):
                setattr(tm, mtype, data)

            if mtype == "status":
                {'status': {'exec_info': {'queue_remaining': 1}}, 'sid': 'ComfyUICUP'}
                SessionId["SessionId"] = data.get("sid", SessionId["SessionId"])
            elif mtype == "executing":
                {"type": "executing", "data": {"node": "7"}}
                if not data["node"]:
                    if tm.cur_task:
                        tm.cur_task.set_finished()
                    tm.mark_finished()
                else:
                    TaskManager.execute_status_record.append(data["node"])
                    if tm.cur_task:
                        tm.cur_task.set_executing_node_id(n)
                # logger.debug(data)
            elif mtype == "progress":
                m = 40
                fac = m / data["max"]
                v = int(data["value"] * fac)
                TaskManager.progress_bar = v
                cf = "\033[92m" + "█" * v + "\033[0m"
                cp = "\033[32m" + "░" * (m - v) + "\033[0m"
                content = f"\r{v*100/m:3.0f}% " + cf + cp + f" {v}/{m}"
                sys.stdout.write(content)
                sys.stdout.flush()
                if tm.cur_task:
                    tm.cur_task.set_process(data)

            elif mtype == "executed":
                {"node": "9", "output": {"images": ["ComfyUI_00028_.png"]}}
                if TaskManager.progress_bar != 0:
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    TaskManager.progress_bar = 0
                tm.push_res(data)
                logger.warn(f"{_T('Ran Node')}: {data['node']}", )
            elif mtype == "execution_error":
                logger.error(data.get("message"))
            elif mtype == "execution_start":
                ...
            elif mtype == "execution_interrupted":
                {"type": "execution_interrupted",
                 "data": {"prompt_id": "e1f3cbf9-4b83-47cf-95c3-9f9a76ab5508",
                          "node_id": "3",
                          "node_type": "KSampler",
                          "executed": ["4", "7", "6", "5"]}
                 }
                TaskManager.put_error_msg(_T("Execute Node Cancelled!"))
                # tm.mark_finished(with_noexe=False)
            elif mtype == "execution_cached":
                # {"type": "execution_cached", "data": {"nodes": ["12", "7", "10"], "prompt_id": "ddd"}}
                # logger.warn(message)
                ...  # pass
            else:
                logger.error(message)
        
        ws = WebSocketApp(f"ws://{get_ip()}:{get_port()}/ws?clientId={SessionId['SessionId']}", on_message=on_message)
        TaskManager.ws = ws
        ws.run_forever()
        logger.debug(_T("Poll Result Thread Exit"))
        TaskManager.ws = None


def removetemp():
    tempdir = Path(__file__).parent / "temp"
    if tempdir.exists():
        rmtree(tempdir, ignore_errors=True)


removetemp()
atexit.register(removetemp)


def run_server():
    if "--background" in sys.argv or "-b" in sys.argv:
        return

    atexit.register(removetemp)
    TaskManager.run_server()
