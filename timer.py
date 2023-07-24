import bpy
import traceback
from queue import Queue
from .kclogger import logger


class Timer:
    TimerQueue = Queue()
    TimerQueue2 = Queue()

    def put(delegate):
        Timer.TimerQueue.put(delegate)

    def put2(delegate):
        Timer.TimerQueue2.put(delegate)

    def executor(t):
        if type(t) in {list, tuple}:
            t[0](*t[1:])
        else:
            t()

    def run1():
        return Timer.run_ex(Timer.TimerQueue)

    def run2():
        return Timer.run_ex(Timer.TimerQueue2)

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

    def clear():
        while not Timer.TimerQueue.empty():
            Timer.TimerQueue.get()
        while not Timer.TimerQueue2.empty():
            Timer.TimerQueue2.get()

    def wait_run(func):
        def wrap(*args, **kwargs):
            q = Queue()

            def wrap_job(q):
                q.put(func(*args, **kwargs))

            Timer.put((wrap_job, q))
            return q.get()
        return wrap

    def reg():
        bpy.app.timers.register(Timer.run1, persistent=True)
        bpy.app.timers.register(Timer.run2, persistent=True)

    def unreg():
        Timer.clear()
        try:
            bpy.app.timers.unregister(Timer.run1)
            bpy.app.timers.unregister(Timer.run2)
        except BaseException:
            ...


def timer_reg():
    Timer.reg()


def timer_unreg():
    Timer.unreg()
