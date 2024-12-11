from __future__ import annotations
import os
import re
import shutil
import sys
import json
import time
import atexit
import aud
from platform import system
import struct
from ast import literal_eval
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from shutil import rmtree
from urllib import request
from urllib.parse import urlparse
from urllib.error import URLError
from threading import Thread
from subprocess import Popen, PIPE, STDOUT
from pathlib import Path
from queue import Queue
from .utils import WindowLogger
from ..utils import rmtree as rt, logger, _T, PkgInstaller, update_screen
from ..timer import Timer
from ..preference import get_pref
from .history import History
from ..External.websocket import WebSocketApp


def get_ip():
    return TaskManager.server.get_ip()


def get_port():
    return TaskManager.server.get_port()


def get_url():
    return TaskManager.server.get_url().replace("0.0.0.0", "localhost")


WITH_PROXY = False
if not WITH_PROXY:
    request.install_opener(request.build_opener(request.ProxyHandler({})))


class Task:
    def __init__(self, task=None, pre=None, post=None, tree=None) -> None:
        self.task = task
        self.res = Queue()
        self._pre = pre
        self._post = post
        from .tree import CFNodeTree
        from .nodes import NodeBase
        self.tree: CFNodeTree = tree
        self.executing_node_id = ""
        self.executing_node: NodeBase = None
        self.is_finished = False
        self.process = {}
        self.binary_message = b""
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
                n.restore_appearance()
        Timer.put((f, self))

    def set_executing_node_id(self, node_id):
        self.executing_node_id = node_id
        self.binary_message = b""

        def f(self: Task):
            from .nodes import NodeBase
            if not self.is_tree_valid():
                return
            self.process = {}
            if self.executing_node:
                self.executing_node.restore_appearance()
            self.executing_node = None
            pnode_id = node_id.split(":")[0]
            for n in self.tree.nodes:
                if not hasattr(n, "id"):
                    continue
                if n.id == pnode_id and n.bl_idname == self.node_ref_map.get(pnode_id, ""):
                    self.executing_node = n
                    break
            n: NodeBase = self.executing_node
            n.store_appearance()
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
            if isinstance(etype, str) and etype.endswith("cup.CupException"):
                info = literal_eval(info["message"])
                etype = info["type"]
            func = getattr(self, etype, self.unknown)
            return func(info)

        def sdn_no_image_provided(self, info):
            return self.__print__(info)

        def sdn_image_not_found(self, info):
            return self.__print__(info)

        def unknown(self, info):
            if self.WITH_PRINT:
                print(info)
            return []

        def TypeError(self, info):
            if self.WITH_PRINT:
                print(info)
            return [info["message"]]

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
                WindowLogger.push_log(msg)
            if dt:
                info_list.append(dt)
                WindowLogger.push_log(dt)
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

    def __init__(self) -> None:
        self.error_info = {}

    def decode_info(self, e: request.HTTPError):
        try:
            self.error_info = json.loads(e.read().decode())
        except BaseException:
            self.error_info = {}

    def parse(self, e):
        if isinstance(e, request.HTTPError):
            self.decode_info(e)
        elif isinstance(e, dict):
            self.error_info = e
        if not self.error_info:
            return
        print("----------------")
        print(self.error_info)
        print("----------------")
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
        from .utils import get_tree
        logger.error(_T("Node Error Parse"))
        WindowLogger.push_log(_T("Node Error Parse"))
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
                        n.store_appearance()
                        n.color = (1, 0, 0)
                        n.use_custom_color = True
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
    server_type = "Base"
    uid = 0

    def __new__(cls, *args, **kw):
        if cls._instance is None:
            cls._instance = object.__new__(cls, *args, **kw)
        return cls._instance

    def __init__(self) -> None:
        self.launch_ip = "127.0.0.1"
        self.launch_port = 8188
        self.launch_url = "http://127.0.0.1:8188"
        self.elapsed_time = 0
        self.tstart = 0

    def run(self) -> bool:
        self.tstart = time.time()
        self.uid = time.time_ns()
        TaskManager.clear_error_msg()
        return True

    def get_running_info(self):
        self.elapsed_time = time.time() - self.tstart
        return f"{_T('Time Elapsed')}: {self.elapsed_time:.2f}s"

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

    def exited(self):
        return False


class FakeServer(Server):
    server_type = "Fake"


class RemoteServer(Server):
    server_type = "Remote"

    def __init__(self) -> None:
        self.server_connected = False
        self.cs_support = "UNKNOWN"
        self.covers = {}
        super().__init__()

    def run(self) -> bool:
        self.tstart = time.time()
        self.server_connected = False
        self.cs_support = "UNKNOWN"
        self.covers.clear()
        TaskManager.clear_error_msg()
        self.uid = time.time_ns()
        self.launch_ip = get_ip()
        self.launch_port = get_port()
        self.launch_url = f"http://{self.launch_ip}:{self.launch_port}"
        return self.wait_connect()

    def is_cs_support(self):
        if self.cs_support in {"NO", "YES"}:
            return self.cs_support == "YES"
        self.cs_support = "NO"
        try:
            import requests
            url = f"{get_url()}/cs/fetch_config"
            if WITH_PROXY:
                req = requests.post(url=url, json={}, timeout=5)
            else:
                req = requests.post(url=url, json={}, proxies={"http": None, "https": None}, timeout=5)
            if req.status_code == 200:
                self.cs_support = "YES"
        except Exception as e:
            logger.error(e)
        return self.cs_support == "YES"

    def cache_model_icon(self, mtype, model) -> str | None:
        if model in self.covers:
            return self.covers[model]
        if not mtype:
            return
        if not self.is_cs_support():
            return
        self.covers[model] = None
        try:
            import requests
            from tempfile import gettempdir
            from urllib3.util import Timeout
            timeout = Timeout(connect=0.1, read=2)
            url = f"{get_url()}/cs/fetch_config"
            req_json = {"mtype": mtype, "models": [model]}
            if WITH_PROXY:
                req = requests.post(url=url, json=req_json, timeout=timeout)
            else:
                req = requests.post(url=url,
                                    json=req_json,
                                    proxies={"http": None, "https": None},
                                    timeout=timeout)
            if req.status_code != 200:
                return
            data = req.json().get(model, {})
            cover = data.get("cover", "")
            img_quote = cover.split("?t=")[0]
            cover_url = f"{get_url()}{img_quote}"
            img_data = requests.get(cover_url, timeout=5).content
            if not img_data:
                return
            img_name = model.replace("/", "_").replace("\\", "_")
            img_path = Path(gettempdir()).joinpath(img_name).with_suffix(Path(img_quote).suffix)
            with open(img_path, "wb") as f:
                f.write(img_data)
            self.covers[model] = img_path
        except requests.exceptions.ConnectionError:
            logger.warning("Server Launch Failed")
        except ModuleNotFoundError:
            logger.error("Module: requests import error!")
        except Exception as e:
            logger.error(e)
        return self.covers[model]

    def wait_connect(self) -> bool:
        import requests
        try:
            if requests.get(f"{self.get_url()}/object_info", proxies={"http": None, "https": None}, timeout=10).status_code == 200:
                self.server_connected = True
                update_screen()
                get_pref().preview_method = get_pref().preview_method
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
        logger.warning(_T("Remote Server Closed"))


class LocalServer(Server):
    server_type = "Local"
    exited_status = {}

    def __init__(self) -> None:
        self.pid = -1
        self.child: Popen = None
        super().__init__()

    def run(self) -> bool:
        self.tstart = time.time()
        TaskManager.clear_error_msg()
        self.uid = time.time_ns()
        pidpath = Path(__file__).parent / "pid"
        if pidpath.exists():
            self.force_kill(pidpath.read_text())
            pidpath.unlink(missing_ok=True)

        pref = get_pref()
        model_path = pref.model_path
        if not model_path or not Path(model_path).exists():
            logger.error(_T("ComfyUI Path Not Found"))
            TaskManager.put_error_msg(_T("ComfyUI Path Not Found"))
            WindowLogger.push_log(_T("ComfyUI Path Not Found"))
            return
        logger.debug("%s: %s", _T("Model Path"), model_path)
        WindowLogger.push_log("%s: %s", _T("Model Path"), model_path)
        python = pref.get_python()
        if pref.install_deps:
            self.run_pre()

        logger.warning(_T("Server Launching"))
        WindowLogger.push_log(_T("Server Launching"))
        if sys.platform == "win32" and not python.exists():
            logger.error("%s:", _T("python interpreter not found"))
            logger.error("   ↳%s:", _T("Ensure that the python_embeded located in the same level as ComfyUI dir"))
            logger.error("      SomeDirectory")
            logger.error("      ├─ ComfyUI")
            logger.error("      ├─ python_embeded")
            logger.error("      │ ├─ python.exe")
            logger.error("      │ └─ ...")
            logger.error("      └─ ...")
            WindowLogger.push_log("%s:", _T("python interpreter not found"))
            WindowLogger.push_log("   ↳%s:", _T("Ensure that the python_embeded located in the same level as ComfyUI dir"))
            WindowLogger.push_log("      SomeDirectory")
            WindowLogger.push_log("      ├─ ComfyUI")
            WindowLogger.push_log("      ├─ python_embeded")
            WindowLogger.push_log("      │ ├─ python.exe")
            WindowLogger.push_log("      │ └─ ...")
            WindowLogger.push_log("      └─ ...")
            return

        # custom_nodes
        for file in Path(__file__).parent.joinpath("custom_nodes").iterdir():
            dst = Path(model_path).joinpath("custom_nodes", file.name)
            if not file.is_dir():
                continue
            if dst.exists():
                try:
                    rt(dst)
                except Exception as e:
                    # 可能会删除失败
                    ...
            try:
                shutil.copytree(file, dst, dirs_exist_ok=True)
                cup_py = file.joinpath("cup.py")
                old_cup_py = Path(model_path).joinpath("custom_nodes", cup_py.name)
                if cup_py.exists():
                    t = cup_py.read_text(encoding="utf-8")
                    t = t.replace("XXXHOST-PATHXXX", Path(__file__).parent.as_posix())
                    t = t.replace("FORCE_LOG = False", f"FORCE_LOG = {get_pref().force_log}")
                    Path(model_path).joinpath("custom_nodes", file.name, cup_py.name).write_text(t, encoding="utf-8")
                if old_cup_py.exists():
                    Path(model_path).joinpath("custom_nodes", cup_py.name).unlink(missing_ok=True)
            except Exception as e:
                # 可能会拷贝失败(权限问题)
                ...
        args = pref.parse_server_args(self)
        self.launch_ip = get_ip()
        self.launch_port = get_port()
        self.launch_url = f"http://{self.launch_ip}:{self.launch_port}"
        # cmd = " ".join([str(python), arg])
        # 加了 stderr后 无法获取 进度?
        # logger.debug(" ".join(args))
        if system() == 'Linux':
            args = " ".join(args)
            args = f"source {pref.python_path}/activate; {args}"
            if Path("/opt/intel/oneapi/setvars.sh").exists():
                args = "source /opt/intel/oneapi/setvars.sh; " + args
                logger.warning("Using Intel OneAPI")
            args = ["/bin/bash", "-c", args]  # shell=True will use /bin/sh which can't source
        # mac
        if system() == "Darwin":
            os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
        p = Popen(args, stdout=PIPE, stderr=STDOUT, cwd=Path(model_path).resolve().as_posix())
        self.child = p
        self.pid = p.pid
        self.exited_status[self.pid] = False
        pidpath.write_text(str(p.pid))
        atexit.register(self.child.kill)
        Thread(target=self.stdout_listen, daemon=True).start()
        return self.wait_connect()

    def close(self):
        pidpath = Path(__file__).parent / "pid"
        if pidpath.exists():
            self.force_kill(pidpath.read_text())
            pidpath.unlink(missing_ok=True)

        if self.child:
            self.child.kill()
        self.exited_status[self.pid] = True
        self.child = None
        self.pid = -1

    def exited(self):
        return self.exited_status.get(self.pid, False)

    def wait_connect(self) -> bool:
        pid = self.pid
        while True:
            update_screen()
            import requests
            try:
                if requests.get(f"{self.get_url()}/object_info", proxies={"http": None, "https": None}, timeout=5).status_code == 200:
                    get_pref().preview_method = get_pref().preview_method
                    return True
            except requests.exceptions.ConnectionError:
                ...
            except Exception as e:
                logger.error(e)
            if self.exited_status.get(pid, False):
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
        logger.error("%s id -> %s", _T("Kill Last ComfyUI Process"), pid)

    def run_pre(self):
        """
        Check pre install
        """
        # controlnet check
        logger.warning(_T("ControlNet Init...."))
        python = get_pref().get_python()
        model_path = get_pref().model_path

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

        logger.warning(_T("ControlNet Init Finished."))
        logger.warning(_T("If controlnet still not worked, install manually by double clicked {}").format((controlnet / "install.bat").as_posix()))

    def stdout_listen(self):
        p = self.child
        pid = self.pid
        while p.poll() is None and self.child == p:
            line = p.stdout.readline().strip()
            if not line:
                continue
            # logger.info(line)
            # print(re.findall("\|(.*?)[", line.decode("gbk")))
            if "# 😺dzNodes:".encode() in line:
                continue
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
        self.exited_status[pid] = True
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
    timers = []
    executer = ThreadPoolExecutor(max_workers=1)
    ws: WebSocketApp = None
    is_server_launching = False

    def __new__(cls, *args, **kw):
        if cls._instance is None:
            cls._instance = object.__new__(cls, *args, **kw)
        return cls._instance

    @staticmethod
    def register_timer(timer):
        if timer in TaskManager.timers:
            return
        TaskManager.timers.append(timer)

    @staticmethod
    def unregister_timer(timer):
        try:
            TaskManager.timers.remove(timer)
        except ValueError:
            ...

    @staticmethod
    def clear_timer():
        TaskManager.timers.clear()

    @staticmethod
    def put_error_msg(error, with_clear=False):
        if with_clear:
            TaskManager.clear_error_msg()
        TaskManager.error_msg.append(str(error))

    @staticmethod
    def clear_error_msg():
        TaskManager.error_msg.clear()

    @staticmethod
    def get_error_msg(copy=False):
        if copy:
            return deepcopy(TaskManager.error_msg)
        return TaskManager.error_msg

    @staticmethod
    def get_progress():
        return TaskManager.progress

    @staticmethod
    def get_task_num():
        return TaskManager.task_queue.qsize()

    @staticmethod
    def is_launching() -> bool:
        return TaskManager.is_server_launching

    @staticmethod
    def is_launched() -> bool:
        if TaskManager.server:
            return TaskManager.server.is_launched()
        return False

    @staticmethod
    def run_server(fake=False):
        def refresh_node():
            Timer.clear()  # timer may cause crash
            from .tree import rtnode_reg, rtnode_unreg
            t1 = time.time()
            rtnode_unreg()
            t2 = time.time()
            logger.info(_T("UnregNode Time:") + f" {t2 - t1:.2f}s")
            rtnode_reg()
            t3 = time.time()
            logger.info(_T("RegNode Time:") + f" {t3 - t2:.2f}s")
        if TaskManager.is_launching():
            return

        def callback():
            Timer.put(refresh_node)

        def job():
            def update_screen_timer():
                update_screen()
                return 0.01
            import bpy
            bpy.app.timers.register(update_screen_timer)
            t1 = time.time()
            TaskManager.is_server_launching = True
            run_success = TaskManager.init_server(fake=fake, callback=callback)
            if not fake and not run_success:
                TaskManager.init_server(fake=True, callback=callback)
            TaskManager.is_server_launching = False
            t2 = time.time()
            logger.info(_T("Launch Time:") + f" {t2 - t1:.2f}s")
            bpy.app.timers.unregister(update_screen_timer)
        if fake:
            job()
            refresh_node()
        else:
            t = Thread(target=job, daemon=True)
            t.start()
        # logger.info(_T("UnregNode Time:") + f" {t2-t1:.2f}s")
        # logger.info(_T("Launch Time:") + f" {t3-t2:.2f}s")
        # logger.info(_T("RegNode Time:") + f" {t4-t3:.2f}s")

    @staticmethod
    def init_server(fake=False, callback=lambda: ...):
        if fake:
            TaskManager.server = FakeServer()
            return
        if get_pref().server_type == "Local":
            TaskManager.server = LocalServer()
        else:
            TaskManager.server = RemoteServer()
        running = TaskManager.server.run()
        if not TaskManager.server.exited() and running:
            logger.warning(_T("Server Launched"))
            WindowLogger.push_log(_T("Server Launched"))
            TaskManager.start_polling()
            callback()
        else:
            logger.error(_T("Server Launch Failed"))
            WindowLogger.push_log(_T("Server Launch Failed"))
            TaskManager.server.close()
        return running

    @staticmethod
    def start_polling():
        Thread(target=TaskManager.poll_res, daemon=True).start()
        Thread(target=TaskManager.poll_task, daemon=True).start()
        Thread(target=TaskManager.proc_res, daemon=True).start()
        Thread(target=TaskManager.proc_timer, daemon=True).start()

    @staticmethod
    def restart_server(fake=False):
        TaskManager.clear_all()
        TaskManager.server.close()
        TaskManager.run_server(fake=fake)

    @staticmethod
    def close_server():
        if TaskManager.ws:
            TaskManager.ws.close()
            TaskManager.ws = None
        TaskManager.cur_task = None
        TaskManager.restart_server(fake=True)

    @staticmethod
    def push_task(task, pre=None, post=None, tree=None):
        logger.debug(_T('Add Task'))
        WindowLogger.push_log(_T('Add Task'))
        if not TaskManager.is_launched():
            TaskManager.put_error_msg(_T("Server Not Launched, Add Task Failed"))
            WindowLogger.push_log(_T("Server Not Launched, Add Task Failed"))
            TaskManager.put_error_msg(_T("Please Check ComfyUI Directory"))
            WindowLogger.push_log(_T("Please Check ComfyUI Directory"))
            logger.error(_T("Server Not Launched"))
            WindowLogger.push_log(_T("Server Not Launched"))
            return
        TaskManager.task_queue.put(Task(task, pre=pre, post=post, tree=tree))

    @staticmethod
    def push_res(res):
        logger.debug(_T("Add Result"))
        TaskManager.cur_task.res.put(res)
        TaskManager.res_queue.put(TaskManager.cur_task)

    @staticmethod
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

    @staticmethod
    def interrupt():
        from http.client import RemoteDisconnected
        import traceback
        req = request.Request(f"{TaskManager.server.get_url()}/interrupt", method="POST")
        try:
            request.urlopen(req)
        except URLError:
            ...
        except RemoteDisconnected:
            ...
        except Exception:
            traceback.print_exc()

    @staticmethod
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
            WindowLogger.push_log(_T("Submit Task"))
            TaskManager.cur_task = task
            try:
                TaskManager.submit(task)
            except Exception as e:
                logger.error(e)
                TaskManager.put_error_msg(str(e), with_clear=True)
                TaskManager.mark_finished(with_noexe=False)
        logger.debug(_T("Poll Task Thread Exit"))

    @staticmethod
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

    @staticmethod
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
            WindowLogger.push_log("P/R: %s/%s", len(res["queue_pending"]), len(res["queue_running"]))

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

    @staticmethod
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

    @staticmethod
    def mark_finished_with_info(info):
        TaskManager.progress = {}
        TaskManager.cur_task = None
        for i in info:
            TaskManager.put_error_msg(i)
        TaskManager.execute_status_record.clear()

    @staticmethod
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
    def proc_timer():
        uid = TaskManager.server.uid
        while uid == TaskManager.server.uid:
            time.sleep(1)
            for timer in TaskManager.timers:
                try:
                    timer()
                except Exception as e:
                    logger.info(e)
        logger.debug(_T("Proc Timer Thread Exit"))

    @staticmethod
    def try_play_finished_sound(msg_data):
        if not get_pref().play_finish_sound:
            return
        is_queue_finished = msg_data.get('status', {}).get('exec_info', {}).get('queue_remaining', 1) == 0
        if not is_queue_finished:
            return
        # 尝试播放任务完成时音效
        try:  # The user may not type the filepath in correctly
            device = aud.Device()
            device.volume = get_pref().finish_sound_volume
            sound = aud.Sound(get_pref().finish_sound_path)
            sound_buffered = aud.Sound.cache(sound)
            device.play(sound_buffered)
        except Exception as e:
            logger.error("Error when playing sound:", e)

    @staticmethod
    def poll_res():
        tm = TaskManager
        SessionId = TaskManager.SessionId

        def on_message(ws, message):
            if isinstance(message, bytes):
                if tm.cur_task:
                    tm.cur_task.binary_message = message
                TaskManager.handle_binary_message(message)
                return
            msg = json.loads(message)
            try:
                from .custom_support import crystools_monitor, cup_monitor
                if crystools_monitor.process_msg(msg):
                    return
                if cup_monitor.process_msg(msg):
                    return
            except Exception:
                ...
            mtype = msg["type"]
            data = msg["data"]
            if mtype == "executing":
                n = data.get("node", "")
                if n:
                    logger.debug("%s: %s", _T("Executing Node"), n)
                    WindowLogger.push_log("%s: %s", _T("Executing Node"), n)
            elif mtype == "execution_start":
                ...
            elif mtype == "execution_cached":
                logger.debug("%s: %s", _T("Execution Cached"), data.get("nodes", ""))
                WindowLogger.push_log("%s: %s", _T("Execution Cached"), data.get("nodes", ""))
            elif mtype == "executed":
                ...
            elif mtype == "execution_success":
                ...
            elif mtype == "execution_error":
                ...
            elif mtype == "status":
                ...
            elif mtype != "progress":
                logger.debug("%s: %s", _T("Message Type"), mtype)
                WindowLogger.push_log("%s: %s", _T("Message Type"), mtype)

            Timer.put(update_screen)

            if hasattr(tm, mtype):
                setattr(tm, mtype, data)

            if mtype == "status":
                {'status': {'exec_info': {'queue_remaining': 1}}, 'sid': 'ComfyUICUP'}
                SessionId["SessionId"] = data.get("sid", SessionId["SessionId"])
                TaskManager.try_play_finished_sound(data)
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
                content = f"{v * 100 / m:3.0f}% " + cf + cp + f" {v}/{m}"
                logger.info(content + "\r", extra={"same_line": True})
                # sys.stdout.write(content)
                # sys.stdout.flush()
                if tm.cur_task:
                    tm.cur_task.set_process(data)

            elif mtype == "executed":
                {"node": "9", "output": {"images": ["ComfyUI_00028_.png"]}}
                if TaskManager.progress_bar != 0:
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    TaskManager.progress_bar = 0
                tm.push_res(data)
                logger.warning("%s: %s", _T("Ran Node"), data["node"])
                WindowLogger.push_log("%s: %s", _T("Ran Node"), data["node"])
            elif mtype == "execution_error":
                _msg = data.get("message", None)
                if not _msg:
                    _msg = data.get("exception_message", None)
                    node_id = data.get("node_id", None)
                    etype = data.get("exception_type", None)
                    ['prompt_id', 'node_id', 'node_type', 'executed', 'exception_message', 'exception_type', 'traceback', 'current_inputs', 'current_outputs']
                    # _msg = msg.get("data", None)
                    # print(_msg.keys())
                    trace = data.get("traceback", None)
                    if trace and isinstance(trace, list):
                        trace = "\n" + "".join([str(t) for t in trace])
                        logger.error(trace)
                    err_parser = TaskErrPaser()
                    node_error = {"errors": [{"type": etype,
                                              "message": _msg}],
                                  }
                    err_parser.error_info = {"node_errors": {node_id: node_error}}
                    Timer.put(err_parser.node_error_parse)
                logger.error(_msg)

            elif mtype == "execution_start":
                ...
            elif mtype == "execution_success":
                logger.warning("%s: %s", _T("Execute Node Success"), data["node"])
                WindowLogger.push_log("%s: %s", _T("Execute Node Success"), data["node"])
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
                # logger.warning(message)
                ...  # pass
            else:
                logger.error(message)
        listen_addr = f"ws://{get_ip()}:{get_port()}/ws?clientId={SessionId['SessionId']}"
        ws = WebSocketApp(listen_addr, on_message=on_message)
        TaskManager.ws = ws
        ws.run_forever()
        if True:
            ...
        else:
            # 备选方案
            from ..External.websockets.sync.client import connect
            from ..External.websockets import ConnectionClosedError
            ws = connect(listen_addr)
            TaskManager.ws = ws
            try:
                for msg in ws:
                    on_message(None, msg)
            except ConnectionClosedError:
                ...
        logger.debug(_T("Poll Result Thread Exit"))
        # WindowLogger.push_log(_T("Poll Result Thread Exit")) # 可能是blender退出, 会导致crash
        TaskManager.ws = None
        if TaskManager.server.is_launched():
            Timer.put((TaskManager.restart_server, True))

    @staticmethod
    def handle_binary_message(data):
        # 解析二进制数据的前4个字节获取事件类型
        event_type = struct.unpack(">I", data[:4])[0]
        # 根据事件类型处理数据
        if event_type != 1:
            logger.debug("Unknown binary event type: %s", event_type)
            return
        # 处理图像类型
        image_type = struct.unpack(">I", data[4:8])[0]
        image_mime = "image/png" if image_type == 2 else "image/jpeg"
        # 假设剩余的数据是图像数据，可以保存或进一步处理
        image_data = data[8:]
        return
        with open(f"/Users/karrycharon/Desktop/000.{image_mime.split('/')[1]}", "wb") as f:
            f.write(image_data)


def removetemp():
    tempdir = Path(__file__).parent / "temp"
    if tempdir.exists():
        rmtree(tempdir, ignore_errors=True)


removetemp()
atexit.register(removetemp)
