import os
import re
import shutil
import sys
import requests
import json
import time
import atexit
import signal
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

port = 8189
ip = "127.0.0.1"
url = f"http://{ip}:{port}"


class Task:
    def __init__(self, task=None, res=None) -> None:
        self.task = task
        self.res = res


class TaskManager:
    _instance = None
    pid = -1
    child = None

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

    def __new__(cls, *args, **kw):
        if cls._instance is None:
            cls._instance = object.__new__(cls, *args, **kw)
        return cls._instance

    def put_error_msg(error):
        TaskManager.error_msg.append(str(error))

    def clear_error_msg():
        TaskManager.error_msg.clear()

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
        else:
            ...
            # os.kill(pid, signal.SIGKILL)
        logger.error(f"{_T('Kill Last ComfyUI Process')} id -> {pid}")

    def run_server():
        from .tree import rtnode_reg, rtnode_unreg
        rtnode_unreg()

        TaskManager.run_server_ex()

        rtnode_reg()

    def run_server_ex():
        pidpath = Path(__file__).parent / "pid"
        if pidpath.exists():
            TaskManager.force_kill(pidpath.read_text())

        from ..preference import get_pref
        pref = get_pref()
        model_path = pref.model_path
        if not model_path or not Path(model_path).exists():
            logger.error(_T("ComfyUI Path Not Found"))
            return
        logger.debug(f"{_T('Model Path')}: {model_path}")
        python = Path(model_path) / "../python_embeded/python.exe"
        logger.warn(_T("Server Launching"))
        if not python.exists():
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
        args = [str(python)]
        # arg = f"-s {str(model_path)}/main.py"
        args.append("-s")
        args.append(f"{str(model_path)}/main.py")

        # arg += f" --port {port}"
        args.append("--port")
        args.append(f"{port}")
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
            yaml += f"""
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
        if pref.with_comfyui_model and Path(pref.with_comfyui_model).exists():
            cmp = Path(pref.with_comfyui_model).as_posix()  # 指定到 models
            cmpp = Path(pref.with_comfyui_model).parent.as_posix()
            yaml += f"""
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
        if yaml:
            extra_model_paths = Path(__file__).parent / "config.yaml"
            extra_model_paths.write_text(yaml)
            args.append("--extra-model-paths-config")
            args.append(extra_model_paths.as_posix())
        # cmd = " ".join([str(python), arg])
        # 加了 stderr后 无法获取 进度?
        # logger.debug(args)
        p = Popen(args, stdout=PIPE, cwd=model_path)
        TaskManager.child = p
        TaskManager.pid = p.pid
        pidpath.write_text(str(p.pid))

        def listen(p, tm):
            while p.poll() is None:
                if tm.child != p:
                    return
                line = p.stdout.readline().strip()
                if not line:
                    continue
                # \xa8\x80
                # line = line.replace(b"\xa8\x87", b">")
                # line = line.replace(b"\xa8\x86", b">")
                # line = line.replace(b"\xa8\x85", b">")
                # line = line.replace(b"\xa8\x84", b">")
                # line = line.replace(b"\xa8\x83", b">")
                # line = line.replace(b"\xa8\x82", b">")
                # line = line.replace(b"\xa8\x81", b">")
                # line = line.replace(b"\xa8\x80", b"=")
                # logger.info(line)
                # print(re.findall("\|(.*?)[", line.decode("gbk")))
                if b"CUDA out of memory" in line or b"not enough memory" in line:
                    TaskManager.put_error_msg(f"{_T('Error: Out of VRam, try restart blender')}")
                proc = re.findall("[█ ]\\| (.*?) \\[", line.decode("gbk"))
                if not proc:
                    # content = line.decode("gbk").replace("██", "=").replace("  ", " ")
                    logger.info(line.decode("gbk"))
                # else:
                #     content = proc[0]
                #     c, a = content.split("/")
                #     c, a = int(c), int(a)
                #     content = f"\r{c*100/a:3.0f}%  " + "█" * c + "░" * (a - c) + f" {c}/{a}" + "\n" * int(c == a)
                #     sys.stdout.write(content)
                #     sys.stdout.flush()

        listen = Thread(target=listen, args=(p, TaskManager), daemon=True)
        listen.start()

        while True:
            try:
                if requests.get(f"{url}/object_info").status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                ...
            time.sleep(0.5)
        logger.warn(_T("Server Launched"))
        atexit.register(p.kill)

        Thread(target=TaskManager.poll_task, daemon=True).start()
        Thread(target=TaskManager.poll_res, daemon=True).start()
        Thread(target=TaskManager.proc_res, daemon=True).start()

    def close_server():
        if TaskManager.child:
            TaskManager.child.kill()
        TaskManager.child = None
        TaskManager.pid = -1

    def restart_server():
        TaskManager.clear_all()
        TaskManager.close_server()
        TaskManager.run_server()

    def push_task(task):
        logger.debug(_T('Add Task'))
        if TaskManager.pid == -1:
            TaskManager.put_error_msg(_T("Server Not Launched, Add Task Failed"))
            TaskManager.put_error_msg(_T("Please Check ComfyUI Directory"))
            logger.error(_T("Server Not Launched"))
            return
        TaskManager.task_queue.put(Task(task))

    def push_res(res):
        logger.debug(_T("Add Result"))
        TaskManager.cur_task.res = res
        TaskManager.res_queue.put(TaskManager.cur_task)

    # def get_res():
    #     if TaskManager.res_queue.empty():
    #         return None
    #     return TaskManager.res_queue.get()

    def query_process():
        ...

    def interrupt():
        ...

    def clear_all():
        TaskManager.interrupt()
        while not TaskManager.task_queue.empty():
            TaskManager.task_queue.get()

    @staticmethod
    def poll_task():
        while True:
            time.sleep(0.1)
            if TaskManager.progress:
                continue
            task = TaskManager.task_queue.get()
            TaskManager.progress = {'value': 0, 'max': 1}
            logger.debug(_T("Submit Task"))
            TaskManager.cur_task = task
            TaskManager.submit(task.task)

    def query_server_task():
        if TaskManager.pid == -1:
            return {"queue_pending": [], "queue_running": []}
        try:
            req = request.Request(f"{url}/queue")
            res = request.urlopen(req)
            res = json.loads(res.read().decode())
        except BaseException:
            res = {"queue_pending": [], "queue_running": []}
        return res

    def submit(task: dict[str, tuple]):
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
                req = request.Request(f"{url}/{api}", data=data)
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

        Thread(target=queue_task, args=(task, )).start()

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
        while True:
            time.sleep(0.1)
            task = TaskManager.res_queue.get()
            logger.debug(_T("Proc Resutl"))
            node = task.res["node"]
            prompt = task.task["prompt"]
            if node in prompt:
                prompt[node][1](task)

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
            elif mtype == "execution_cached":
                # {"type": "execution_cached", "data": {"nodes": ["12", "7", "10"], "prompt_id": "ddd"}}
                # logger.warn(message)
                ...  # pass
            else:
                logger.error(message)

        ws = WebSocketApp(f"ws://{ip}:{port}/ws?clientId={SessionId['SessionId']}", on_message=on_message)
        ws.run_forever()


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
