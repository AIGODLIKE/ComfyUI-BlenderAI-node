import bpy
import traceback
from queue import Queue
from typing import Any
from .kclogger import logger


class Timer:
    TimerQueue = Queue()
    TimerQueue2 = Queue()
    stoped = False

    @classmethod
    def put(cls, delegate: Any):
        if cls.stoped:
            return
        cls.TimerQueue.put(delegate)

    @classmethod
    def put2(cls, delegate: Any):
        if cls.stoped:
            return
        cls.TimerQueue2.put(delegate)

    @classmethod
    def executor(cls, t):
        if type(t) in {list, tuple}:
            t[0](*t[1:])
        else:
            t()

    @classmethod
    def stop_added(cls):
        cls.stoped = True

    @classmethod
    def start_added(cls):
        cls.stoped = False

    @classmethod
    def run1(cls):
        return cls.run_ex(cls.TimerQueue)

    @classmethod
    def run2(cls):
        return cls.run_ex(cls.TimerQueue2)

    @classmethod
    def run_ex(cls, queue: Queue):
        while not queue.empty():
            t = queue.get()
            try:
                cls.executor(t)
            except Exception as e:
                traceback.print_exc()
                logger.error("%s: %s", type(e).__name__, e)
            except KeyboardInterrupt:
                ...
        return 0.016666666666666666

    @classmethod
    def clear(cls):
        while not cls.TimerQueue.empty():
            cls.TimerQueue.get()
        while not cls.TimerQueue2.empty():
            cls.TimerQueue2.get()

    @classmethod
    def wait_run(cls, func):
        def wrap(*args, **kwargs):
            q = Queue()

            def wrap_job(q):
                try:
                    res = func(*args, **kwargs)
                    q.put(res)
                except Exception as e:
                    q.put(e)

            cls.put((wrap_job, q))
            res = q.get()
            if isinstance(res, Exception):
                raise res
            return res

        return wrap

    @classmethod
    def reg(cls):
        bpy.app.timers.register(cls.run1, persistent=True)
        bpy.app.timers.register(cls.run2, persistent=True)

    @classmethod
    def unreg(cls):
        cls.clear()
        try:
            bpy.app.timers.unregister(cls.run1)
            bpy.app.timers.unregister(cls.run2)
        except Exception:
            ...


class WorkerFunc:
    args = {}

    def __init__(self) -> None:
        self.args = self.__class__.args

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        pass


class Worker:
    JOB_WORK = set()
    JOB_CLEAR = Queue()

    @staticmethod
    def push_worker(func):
        Worker.JOB_WORK.add(func)

    @staticmethod
    def push_clear(func):
        Worker.JOB_CLEAR.put(func)

    @staticmethod
    def remove_worker(func):
        Worker.JOB_WORK.discard(func)

    @staticmethod
    def worker():
        for func in Worker.JOB_WORK:
            try:
                Worker.executor(func)
            except Exception as e:
                traceback.print_exc()
                logger.error("%s: %s", type(e).__name__, e)
            except KeyboardInterrupt:
                ...
        return 1

    @staticmethod
    def executor(t):
        if type(t) in {list, tuple}:
            t[0](*t[1:])
        else:
            t()

    @staticmethod
    def reg():
        bpy.app.timers.register(Worker.worker, persistent=True)

    @staticmethod
    def unreg():
        try:
            bpy.app.timers.unregister(Worker.worker)
        except Exception:
            ...

    @staticmethod
    @bpy.app.handlers.persistent
    def clear(_):
        Worker.JOB_WORK.clear()
        while not Worker.JOB_CLEAR.empty():
            try:
                func = Worker.JOB_CLEAR.get()
                func()
            except Exception as e:
                traceback.print_exc()
                logger.error("%s: %s", type(e).__name__, e)
            except KeyboardInterrupt:
                ...


def timer_reg():
    Timer.reg()
    Worker.reg()
    bpy.app.handlers.load_pre.append(Worker.clear)


def timer_unreg():
    Timer.unreg()
    Worker.unreg()
