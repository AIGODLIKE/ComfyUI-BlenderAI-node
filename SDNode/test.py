import subprocess

c = """
import sys
import time
for i in range(5):
    sys.stdout.write('Processing')
    sys.stdout.flush()
    time.sleep(1)

for i in range(5):
    sys.stderr.write('Processing')
    sys.stderr.flush()
    time.sleep(1)

"""
# p = subprocess.Popen(["python3", "-c", c], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
# while p.poll() is None:
#     print("----", p.stderr.readline().decode())


# import subprocess
# import select
# import fcntl
# import os

# # 创建子进程
# p = subprocess.Popen(["python3", "-c", c], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# # 将子进程stderr设置为非阻塞
# fd = p.stderr.fileno()
# flags = fcntl.fcntl(fd, fcntl.F_GETFL)
# fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

# # 将子进程stdout设置为非阻塞
# fd = p.stdout.fileno()
# flags = fcntl.fcntl(fd, fcntl.F_GETFL)
# fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

# # 读取子进程的输出
# while p.poll() is None:
#     # 使用select模块等待子进程stderr上是否有输出
#     ready, _, _ = select.select([p.stderr], [], [], 1)
#     if ready:
#         output = p.stderr.read()
#         print("---", output.decode())
#     ready, _, _ = select.select([p.stdout], [], [], 1)
#     if ready:
#         output = p.stdout.read()
#         print("--", output.decode())

    
