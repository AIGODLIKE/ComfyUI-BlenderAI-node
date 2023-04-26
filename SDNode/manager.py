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
from ..utils import logger
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
        from ..External import psutil
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
            os.kill(pid, signal.SIGKILL)
        logger.error(f"Kill Last ComfyUI Process {pid}")

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
            logger.error("ComfyUI路径不存在")
            return
        logger.debug(f"Update Model Path: {model_path}")
        python = Path(model_path) / "../python_embeded/python.exe"
        logger.warn("Server Launching")
        if not python.exists():
            logger.error("未找到 python解释器:")
            logger.error("   ↳请确保python_embeded文件夹存放于ComfyUI路径同级目录:")
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
        if Path(pref.with_webui_model).exists():
            ...
            yaml = """
a111:
    base_path: {}path/to/stable-diffusion-webui/

    checkpoints: {}models/Stable-diffusion
    configs: {}models/Stable-diffusion
    vae: {}models/VAE
    loras: {}models/Lora
    upscale_models: |
                  {}models/ESRGAN
                  {}models/SwinIR
    embeddings: {}embeddings
    controlnet: {}models/ControlNet
            """
            with open(Path(__file__).parent / "config.yaml", "w") as f:
                f.write(yaml)
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
                if b"CUDA out of memory" in line:
                    TaskManager.put_error_msg("错误:显存不足, 请重启blender")
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
        logger.warn("Server Launched")
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
        logger.debug("Add Task")
        if TaskManager.pid == -1:
            TaskManager.put_error_msg("服务未启动, 任务添加失败")
            TaskManager.put_error_msg("请检查ComfyUI路径")
            logger.error("服务未启动")
            return
        TaskManager.task_queue.put(Task(task))

    def push_res(res):
        logger.debug("Add Result")
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
            logger.debug("Submit Task")
            TaskManager.cur_task = task
            TaskManager.submit(task.task)

    def query_server_task():
        if TaskManager.pid == -1:
            return {"queue_pending": [], "queue_running": []}
        req = request.Request(f"{url}/queue")
        res = request.urlopen(req)
        res = json.loads(res.read().decode())
        {"queue_pending": [], "queue_running": []}
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
                    TaskManager.put_error_msg("无效节点连接")
                    TaskManager.mark_finished()
                except URLError:
                    TaskManager.put_error_msg("服务未启动")
                    TaskManager.mark_finished(with_noexe=False)
            else:
                ...

        Thread(target=queue_task, args=(task, )).start()

    def mark_finished(with_noexe=True):
        TaskManager.progress = {}
        TaskManager.cur_task = None
        if not TaskManager.execute_status_record and with_noexe:
            TaskManager.put_error_msg("节点树未被执行, 可能原因:")
            TaskManager.put_error_msg("    1.参数未变更")
            TaskManager.put_error_msg("    2.输入图像错误")
            TaskManager.put_error_msg("    3.节点连接错误")
            TaskManager.put_error_msg("    4.服务未启动")
        TaskManager.execute_status_record.clear()

    def proc_res():
        while True:
            time.sleep(0.1)
            task = TaskManager.res_queue.get()
            logger.debug("Proc Resutl")
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
                v = data["value"]
                m = data["max"]
                fac = 40 / m
                v = int(v * fac)
                m = 40
                content = f"\r{v*100/m:3.0f}%  " + "█" * v + "░" * (m - v) + f" {v}/{m}" + "\n" * int(v == m)
                sys.stdout.write(content)
                sys.stdout.flush()

            elif mtype == "executed":
                {"node": "9", "output": {"images": ["ComfyUI_00028_.png"]}}
                tm.push_res(data)
                logger.warn(f"Ran Node: {data['node']}", )
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
