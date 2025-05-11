import json
from typing import Callable
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs


# 运行服务器在子线程上
class SubThreadAPIServer:
    def __init__(self, port_range: tuple[int, int] = (8000, 8010), request_handler_class: type[BaseHTTPRequestHandler] = BaseHTTPRequestHandler):
        self.port_range = port_range
        self.RequestHandlerClass = request_handler_class

    def run(self):
        for port in range(*self.port_range):
            try:
                server = HTTPServer(("", port), self.RequestHandlerClass)
                print(f"Server started on port {port}")
                break
            except OSError:
                print(f"Port {port} is in use, trying next port...")
        else:
            print("Could not find an available port in the specified range.")
            return
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()


def handle_hello(self: "APIHandler"):
    query = parse_qs(urlparse(self.path).query)
    name = query.get("name", ["World"])[0]
    self.send_response(200, {"message": f"Hello, {name}!"})


def handle_post_data(self: "APIHandler"):
    content_length = int(self.headers["Content-Length"])
    post_data = self.rfile.read(content_length)

    try:
        data = json.loads(post_data)
        response = {
            "status": "received",
            "your_data": data,
            "method": "POST",
        }
        self.send_response(201, response)
    except json.JSONDecodeError:
        self.send_response(400, {"error": "Invalid JSON"})


def handle_post_get_data_from_blender(self: "APIHandler"):
    length = int(self.headers["Content-Length"])
    post_data = self.rfile.read(length)
    try:
        data: dict = json.loads(post_data)
    except json.JSONDecodeError:
        self.send_response(400, {"error": "Invalid JSON"})
        return
    event = data.get("event")
    if event == "echo":
        self.send_response(200)
    elif event == "run":
        unique_id = data.get("unique_id", "")
        data_name = data.get("message", {}).get("data_name")
        data_result = 1
        # 测试
        if data_name == "active_model":
            data_result = "3d/未命名.glb"
        resp_json = {
            "unique_id": unique_id,
            "message": {
                "data_name": data_name,
                "data_result": data_result,
            },
            "event": "run",
        }
        print("Received data from ComfyUI: ", data)
        self.send_response(201, resp_json)
    else:
        self.send_response(400, {"error": "Invalid event"})


class APIHandler(BaseHTTPRequestHandler):
    # 路由
    routes: dict[str, dict[str, Callable[["APIHandler"], None]]] = {
        "GET": {
            "/api/hello": handle_hello,
        },
        "POST": {
            "/api/data": handle_post_data,
            "/api/get_data_from_blender": handle_post_get_data_from_blender,
        },
    }

    # 通用响应方法
    def send_response(self, status_code, data=None):
        super().send_response(status_code)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")  # 跨域
        self.end_headers()
        if data:
            self.wfile.write(json.dumps(data).encode())

    # 路由分发器
    def handle_request(self):
        parsed_path = urlparse(self.path).path
        method = self.command

        # 查找路由对应的处理函数
        handler = self.routes.get(method, {}).get(parsed_path, None)
        if handler:
            handler(self)
        else:
            self.send_response(404, {"error": "Endpoint not found"})

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()


if __name__ == "__main__":
    BLENDER_IO_PORT_RANGE = (53819, 53824)
    BLENDER_IO_PORT_RANGE = (8000, 53824)
    server = SubThreadAPIServer(port_range=BLENDER_IO_PORT_RANGE, request_handler_class=APIHandler)
    server.run()
    # port = BLENDER_IO_PORT_RANGE[0]
    # server_address = ("", port)
    # httpd = HTTPServer(server_address, APIHandler)
    # httpd.serve_forever()
