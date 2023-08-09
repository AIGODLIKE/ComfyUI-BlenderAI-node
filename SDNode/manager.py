from functools import lru_cache
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

from copy import deepcopy
from shutil import rmtree
from urllib import request
from urllib.error import URLError
from threading import Thread
from subprocess import Popen, PIPE
from pathlib import Path
from queue import Queue
from ..utils import logger, _T, PkgInstaller
from ..timer import Timer
from ..preference import get_pref

def get_ip():
    ip = get_pref().ip
    return ip

def get_port():
    port = get_pref().port
    return port

def get_url():
    return f"http://{get_ip()}:{get_port()}"


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
    # custom_nodes: {cmpp}/custom_nodes
            """


class Task:
    def __init__(self, task=None, pre=None, post=None) -> None:
        self.task = task
        self.res = Queue()
        self._pre = pre
        self._post = post

    def submit_pre(self):
        if not self._pre:
            return
        self._pre()

    def post(self):
        if not self._post:
            return
        self._post()


class TaskManager:
    _instance = None
    pid = -1
    child: Popen = None
    process_exited = False
    task_queue = Queue()
    res_queue = Queue()
    SessionId = {"SessionId": "无限圣杯"}
    status = {}
    progress = {}
    executing = {}
    cur_task: Task = None
    execute_status_record = []
    error_msg = []
    progress_bar = 0

    executer = ThreadPoolExecutor(max_workers=1)

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
        return TaskManager.pid != -1

    def force_kill(pid):
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
                os.system(f'taskkill /F /IM {process.name()}')
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

    def run_server(fake=False):
        import time

        from .tree import rtnode_reg, rtnode_unreg
        t1 = time.time()
        rtnode_unreg()
        t2 = time.time()
        logger.info(f"UnregNode Time: {t2-t1:.2f}s")
        if not fake:
            TaskManager.run_server_ex()
            t3 = time.time()
            logger.info(f"Launch Time: {t3-t2:.2f}s")
        t3 = time.time()
        rtnode_reg()
        t4 = time.time()
        logger.info(f"RegNode Time: {t4-t3:.2f}s")

    def run_server_pre(model_path):
        """
        Check pre install
        """
        # controlnet check
        logger.warn(_T("ControlNet Init...."))
        python = Path("python3")
        if sys.platform == "win32":
            python = Path(model_path) / "../python_embeded/python.exe"
        # elif sys.platform == "darwin":
        #     requirements = Path(model_path) / "requirements.txt"
        #     command = [python.as_posix(), "-m", "pip", "install", "-r", requirements.as_posix()]
        #     if fast_url := PkgInstaller.select_pip_source():
        #         site = urlparse(fast_url)
        #         command.append("-i")
        #         command.append(fast_url)
        #         command.append("--trusted-host")
        #         command.append(site.netloc)
        #     proc = Popen(command, cwd=model_path)
        #     proc.wait()

        controlnet = Path(model_path) / "custom_nodes/comfy_controlnet_preprocessors"
        if controlnet.exists():
            fvcore = Path(model_path) / "../python_embeded/Lib/site-packages/fvcore"
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

                # args = [str(python)]
                # args.append("-s")
                # args.append((controlnet / "install.py").as_posix())
                # p = Popen(args, cwd=model_path)
                # p.wait()

        logger.warn(_T("ControlNet Init Finished."))
        logger.warn(_T("If controlnet still not worked, install manually by double clicked {}").format((controlnet / "install.bat").as_posix()))

    def run_server_ex():
        pidpath = Path(__file__).parent / "pid"
        if pidpath.exists():
            TaskManager.force_kill(pidpath.read_text())

        pref = get_pref()
        model_path = pref.model_path
        if not model_path or not Path(model_path).exists():
            logger.error(_T("ComfyUI Path Not Found"))
            return
        logger.debug(f"{_T('Model Path')}: {model_path}")
        python = Path("python3")
        if sys.platform == "win32":
            python = Path(model_path) / "../python_embeded/python.exe"
        if pref.install_deps:
            TaskManager.run_server_pre(model_path)

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
            if not file.suffix == ".py":
                continue
            if file.name == "cup.py":
                t = file.read_text()
                t = t.replace("XXXMODEL-CFGXXX", str(Path(__file__).parent / "PATH_CFG.json"))
                (Path(model_path) / "custom_nodes" / file.name).write_text(t)
                continue
            shutil.copyfile(file, Path(model_path) / "custom_nodes" / file.name)
        args = [python.as_posix()]
        # arg = f"-s {str(model_path)}/main.py"
        args.append("-s")
        args.append(f"{str(model_path)}/main.py")

        args.append("--listen")
        args.append(get_ip())
        args.append("--port")
        args.append(f"{get_port()}")
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
        # cmd = " ".join([str(python), arg])
        # 加了 stderr后 无法获取 进度?
        # logger.debug(args)
        import bpy
        if bpy.app.version >= (3, 6):
            p = Popen(args, stdout=PIPE, cwd=Path(model_path).joinpath("..").resolve().as_posix())
        else:
            p = Popen(args, stdout=PIPE, cwd=Path(model_path).joinpath("..").resolve().as_posix())
        TaskManager.child = p
        TaskManager.pid = p.pid
        pidpath.write_text(str(p.pid))
        TaskManager.process_exited = False
        Thread(target=TaskManager.stdout_listen, daemon=True).start()

        while True:
            import requests
            try:
                if requests.get(f"{get_url()}/object_info", proxies={"http": None, "https": None}, timeout=0.1).status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                ...
            except Exception as e:
                logger.error(e)
            if TaskManager.process_exited:
                break
            time.sleep(0.5)
        if not TaskManager.process_exited:
            logger.warn(_T("Server Launched"))
            atexit.register(p.kill)
            Thread(target=TaskManager.poll_res, daemon=True).start()
            Thread(target=TaskManager.poll_task, daemon=True).start()
            Thread(target=TaskManager.proc_res, daemon=True).start()
        else:
            logger.error(_T("Server Launch Failed"))
            TaskManager.close_server()

    def stdout_listen():
        p = TaskManager.child
        while p.poll() is None and TaskManager.child == p:
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
        TaskManager.process_exited = True
        logger.debug("STDOUT Listen Thread Exit")

    def close_server():
        if TaskManager.child:
            TaskManager.child.kill()
        TaskManager.child = None
        TaskManager.pid = -1

    def restart_server():
        TaskManager.clear_all()
        TaskManager.close_server()
        TaskManager.run_server()

    def push_task(task, pre=None, post=None):
        logger.debug(_T('Add Task'))
        if TaskManager.pid == -1:
            TaskManager.put_error_msg(_T("Server Not Launched, Add Task Failed"))
            TaskManager.put_error_msg(_T("Please Check ComfyUI Directory"))
            logger.error(_T("Server Not Launched"))
            return
        TaskManager.task_queue.put(Task(task, pre=pre, post=post))

    def push_res(res):
        logger.debug(_T("Add Result"))
        TaskManager.cur_task.res.put(res)
        TaskManager.res_queue.put(TaskManager.cur_task)

    # def get_res():
    #     if TaskManager.res_queue.empty():
    #         return None
    #     return TaskManager.res_queue.get()

    def query_process():
        ...

    def clear_cache():
        req = request.Request(f"{get_url()}/cup/clear_cache", method="POST")
        try:
            request.urlopen(req)
        except URLError:
            ...

    def interrupt():
        req = request.Request(f"{get_url()}/interrupt", method="POST")
        try:
            request.urlopen(req)
        except URLError:
            ...

    def clear_all():
        TaskManager.interrupt()
        while not TaskManager.task_queue.empty():
            TaskManager.task_queue.get()

    @staticmethod
    def poll_task():
        pid = TaskManager.pid
        while pid == TaskManager.pid:
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
        logger.debug("Poll Task Thread Exit")

    def query_server_task():
        if TaskManager.pid == -1:
            return {"queue_pending": [], "queue_running": []}
        try:
            req = request.Request(f"{get_url()}/queue")
            req.set_proxy(None, None)
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
                               "extra_pnginfo": {"workflow": task.get("workflow")},
                               "client_id": cid,
                           }}
                data = json.dumps(content).encode()
                req = request.Request(f"{get_url()}/{api}", data=data)
                try:
                    request.urlopen(req)
                except request.HTTPError:
                    TaskManager.put_error_msg(_T("Invalid Node Connection"))
                    TaskManager.mark_finished()
                except URLError:
                    TaskManager.put_error_msg(_T("Server Not Launched"))
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

    def proc_res():
        pid = TaskManager.pid
        while pid == TaskManager.pid:
            time.sleep(0.1)
            if TaskManager.res_queue.empty():
                continue
            task = TaskManager.res_queue.get()
            if task.res.empty():
                continue
            logger.debug(_T("Proc Resutl"))
            res = task.res.get()
            node = res["node"]
            prompt = task.task["prompt"]
            if node in prompt:
                prompt[node][2](task, res)
        logger.debug("Proc Task Thread Exit")

    @staticmethod
    def poll_res():
        tm = TaskManager
        SessionId = TaskManager.SessionId
        from .websocket import WebSocketApp

        def on_message(ws, message):
            msg = json.loads(message)
            mtype = msg["type"]
            data = msg["data"]

            def update():
                import bpy
                for area in bpy.context.screen.areas:
                    area.tag_redraw()
            Timer.put(update)

            if hasattr(tm, mtype):
                setattr(tm, mtype, data)

            if mtype == "status":
                {'status': {'exec_info': {'queue_remaining': 1}}, 'sid': '无限圣杯'}
                SessionId["SessionId"] = data.get("sid", SessionId["SessionId"])
            elif mtype == "executing":
                {"type": "executing", "data": {"node": "7"}}
                if not data["node"]:
                    tm.mark_finished()
                else:
                    TaskManager.execute_status_record.append(data["node"])
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
        ws.run_forever()
        logger.debug("Poll Result Thread Exit")


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
