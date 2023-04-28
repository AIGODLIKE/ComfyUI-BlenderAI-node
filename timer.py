import bpy
from queue import Queue
from .utils import logger


class Timer:
    TimerQueue = Queue()
    
    def put(delegate):
        Timer.TimerQueue.put(delegate)
        
    def executor(t):
        if type(t) in {list, tuple}:
            t[0](*t[1:])
        else:
            t()
            
    def run():
        while not Timer.TimerQueue.empty():
            t = Timer.TimerQueue.get()
            try:
                Timer.executor(t)
            except Exception as e:
                logger.error(f"{type(e).__name__}: {e}")
            except KeyboardInterrupt:
                ...
        return 0.1

    def clear():
        while not Timer.TimerQueue.empty():
            Timer.TimerQueue.get()

    def wait_run(func):
        def wrap(*args, **kwargs):
            q = Queue()

            def wrap_job(q):
                q.put(func(*args, **kwargs))

            Timer.put((wrap_job, q))
            return q.get()
        return wrap

    def reg():
        bpy.app.timers.register(Timer.run, persistent=True)

    def unreg():
        Timer.clear()
        try:
            bpy.app.timers.unregister(Timer.run)
        except BaseException:
            ...


def timer_reg():
    Timer.reg()


def timer_unreg():
    Timer.unreg()
