import bpy
import traceback
from queue import Queue
from typing import Any
from .kclogger import logger


class Timer:
    TimerQueue = Queue()
    TimerQueue2 = Queue()

    @staticmethod
    def put(delegate: Any):
        Timer.TimerQueue.put(delegate)

    @staticmethod
    def put2(delegate: Any):
        Timer.TimerQueue2.put(delegate)

    @staticmethod
    def executor(t):
        if type(t) in {list, tuple}:
            t[0](*t[1:])
        else:
            t()

    @staticmethod
    def run1():
        return Timer.run_ex(Timer.TimerQueue)

    @staticmethod
    def run2():
        return Timer.run_ex(Timer.TimerQueue2)

    @staticmethod
    def run_ex(queue: Queue):
        while not queue.empty():
            t = queue.get()
            # Timer.executor(t)
            try:
                Timer.executor(t)
            except Exception as e:
                traceback.print_exc()
                logger.error(f"{type(e).__name__}: {e}")
            except KeyboardInterrupt:
                ...
        return 0.1

    @staticmethod
    def clear():
        while not Timer.TimerQueue.empty():
            Timer.TimerQueue.get()
        while not Timer.TimerQueue2.empty():
            Timer.TimerQueue2.get()

    @staticmethod
    def wait_run(func):
        def wrap(*args, **kwargs):
            q = Queue()

            def wrap_job(q):
                q.put(func(*args, **kwargs))

            Timer.put((wrap_job, q))
            return q.get()

        return wrap

    @staticmethod
    def reg():
        bpy.app.timers.register(Timer.run1, persistent=True)
        bpy.app.timers.register(Timer.run2, persistent=True)

    @staticmethod
    def unreg():
        Timer.clear()
        try:
            bpy.app.timers.unregister(Timer.run1)
            bpy.app.timers.unregister(Timer.run2)
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
                logger.error(f"{type(e).__name__}: {e}")
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
                logger.error(f"{type(e).__name__}: {e}")
            except KeyboardInterrupt:
                ...

def timer_reg():
    Timer.reg()
    Worker.reg()
    bpy.app.handlers.load_pre.append(Worker.clear)


def timer_unreg():
    Timer.unreg()
    Worker.unreg()
