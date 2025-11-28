import logging
import os
import numpy as np
from pathlib import Path
import math
import random
import time
import ctypes
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader

from slimgui import imgui
from slimgui import implot


def _make_texture():
    size = 128
    x = np.linspace(-1, 1, size)
    y = np.linspace(-1, 1, size)
    x, y = np.meshgrid(x, y)

    radius = np.sqrt(x**2 + y**2)
    image = np.sin(radius * 5 * np.pi)
    image = (image * 0.5 + 0.5) * 255
    image = np.stack((image, image, image, image), axis=-1)
    image[:, :, 3] = 255
    image = image.astype(np.uint8)
    image = np.clip(image, 0, 255)
    image = np.array(image, dtype=np.uint8)

    h, w, _c = image.shape
    tex_id = glGenTextures(1)

    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, image)

    assert glGetError() == GL_NO_ERROR, "Error creating texture"
    return {
        "id": tex_id,
        "width": w,
        "height": h,
    }


class ParticleSystem:
    def __init__(self, max_particles=1500):
        self.max_particles = max_particles
        self.particle_count = 0
        self.last_time = time.time()
        self.mouse_pos = np.array([0.0, 0.0], dtype=np.float32)
        self.mouse_down = False

        # Pre-allocate NumPy arrays for all particle data
        self.positions = np.zeros((max_particles, 2), dtype=np.float32)  # x, y
        self.velocities = np.zeros((max_particles, 2), dtype=np.float32)  # vx, vy
        self.accelerations = np.zeros((max_particles, 2), dtype=np.float32)  # ax, ay
        self.life = np.zeros(max_particles, dtype=np.float32)
        self.start_life = np.zeros(max_particles, dtype=np.float32)
        self.sizes = np.zeros(max_particles, dtype=np.float32)
        self.start_sizes = np.zeros(max_particles, dtype=np.float32)
        self.colors = np.zeros((max_particles, 4), dtype=np.float32)  # r, g, b, a

    def update(self):
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time

        io = imgui.get_io()
        self.mouse_pos[:] = io.mouse_pos
        self.mouse_down = io.mouse_down[0]

        if self.particle_count == 0:
            self.spawn_particles(10)
            return

        # Create mask for alive particles
        alive_mask = self.life[: self.particle_count] > 0
        alive_count = np.sum(alive_mask)

        if alive_count < self.particle_count:
            # Compact arrays by removing dead particles
            self.positions[:alive_count] = self.positions[: self.particle_count][alive_mask]
            self.velocities[:alive_count] = self.velocities[: self.particle_count][alive_mask]
            self.accelerations[:alive_count] = self.accelerations[: self.particle_count][alive_mask]
            self.life[:alive_count] = self.life[: self.particle_count][alive_mask]
            self.start_life[:alive_count] = self.start_life[: self.particle_count][alive_mask]
            self.sizes[:alive_count] = self.sizes[: self.particle_count][alive_mask]
            self.start_sizes[:alive_count] = self.start_sizes[: self.particle_count][alive_mask]
            self.colors[:alive_count] = self.colors[: self.particle_count][alive_mask]
            self.particle_count = alive_count

        if self.particle_count == 0:
            return

        # Vectorized update for all active particles
        n = self.particle_count
        fac1 = 0.01

        # Update positions and velocities
        self.positions[:n] += self.velocities[:n] * dt
        self.velocities[:n] += self.accelerations[:n] * dt * fac1
        self.life[:n] -= dt

        # Update sizes based on life
        life_ratio = np.maximum(0, self.life[:n] / self.start_life[:n])
        self.sizes[:n] = np.maximum(1, self.start_sizes[:n] * life_ratio) * 4

        # Mouse interaction (vectorized)
        if self.mouse_down:
            # Calculate displacement vector (dx, dy) in one operation
            delta = self.positions[:n] - self.mouse_pos
            dist_sq = np.sum(delta * delta, axis=1)

            # Only affect particles within range
            in_range = dist_sq < 1000
            if np.any(in_range):
                force = 50000 / (dist_sq[in_range] + 1)
                # Apply force in both directions at once
                self.velocities[:n][in_range] += (delta[in_range] / dist_sq[in_range, np.newaxis]) * force[:, np.newaxis] * dt * 10000

        # Spawn new particles
        if self.particle_count < self.max_particles:
            self.spawn_particles(10)

    def spawn_particles(self, count):
        # Calculate how many particles we can actually spawn
        available = self.max_particles - self.particle_count
        count = min(count, available)
        if count <= 0:
            return

        start_idx = self.particle_count
        end_idx = self.particle_count + count

        # Generate random values
        angles = np.random.uniform(0, 2 * np.pi, count)
        speeds = np.random.uniform(20, 100, count)
        lives = np.random.uniform(2, 5, count)
        sizes = np.random.uniform(3, 8, count)

        # Determine spawn positions
        spawn_type = np.random.random(count) < 0.7
        io = imgui.get_io()
        display_w, display_h = io.display_size

        # Edge spawns
        side = np.random.randint(0, 4, count)
        x_edge = np.where(side == 0, np.random.uniform(0, display_w, count), np.where(side == 1, display_w, np.where(side == 2, np.random.uniform(0, display_w, count), 0)))
        y_edge = np.where(side == 0, 0, np.where(side == 1, np.random.uniform(0, display_h, count), np.where(side == 2, display_h, np.random.uniform(0, display_h, count))))

        # Mouse spawns
        x_mouse = self.mouse_pos[0] + np.random.uniform(-20, 20, count)
        y_mouse = self.mouse_pos[1] + np.random.uniform(-20, 20, count)

        # Choose spawn position based on type
        x_pos = np.where(spawn_type, x_edge, x_mouse)
        y_pos = np.where(spawn_type, y_edge, y_mouse)
        lives = np.where(spawn_type, lives, lives * 0.5)

        # Set particle data
        self.positions[start_idx:end_idx, 0] = x_pos
        self.positions[start_idx:end_idx, 1] = y_pos
        self.velocities[start_idx:end_idx, 0] = np.cos(angles) * speeds
        self.velocities[start_idx:end_idx, 1] = np.sin(angles) * speeds
        self.accelerations[start_idx:end_idx, 0] = np.random.uniform(-10, 10, count)
        self.accelerations[start_idx:end_idx, 1] = np.random.uniform(-10, 10, count)
        self.life[start_idx:end_idx] = lives
        self.start_life[start_idx:end_idx] = lives
        self.sizes[start_idx:end_idx] = sizes
        self.start_sizes[start_idx:end_idx] = sizes

        # Generate colors
        for i in range(count):
            self.colors[start_idx + i] = self.random_color()

        self.particle_count = end_idx

    def random_color(self):
        hues = [0.0, 0.1, 0.6, 0.8]
        hue = random.choice(hues)
        saturation = random.uniform(0.3, 0.7)
        value = random.uniform(0.7, 1.0)
        alpha = random.uniform(0.3, 0.8)

        h_i = int(hue * 6)
        f = hue * 6 - h_i
        p = value * (1 - saturation)
        q = value * (1 - f * saturation)
        t = value * (1 - (1 - f) * saturation)

        if h_i == 0:
            r, g, b = value, t, p
        elif h_i == 1:
            r, g, b = q, value, p
        elif h_i == 2:
            r, g, b = p, value, t
        elif h_i == 3:
            r, g, b = p, q, value
        elif h_i == 4:
            r, g, b = t, p, value
        else:
            r, g, b = value, p, q

        return np.array([r, g, b, alpha], dtype=np.float32)

    def get_render_data(self):
        """返回用于渲染的粒子数据"""
        if self.particle_count == 0:
            return None

        n = self.particle_count
        life_ratio = self.life[:n] / self.start_life[:n]

        # 返回 (x, y, size, r, g, b, a) 格式的数据
        return np.column_stack([self.positions[:n, 0], self.positions[:n, 1], self.sizes[:n], self.colors[:n, 0], self.colors[:n, 1], self.colors[:n, 2], self.colors[:n, 3] * life_ratio]).astype(np.float32)


class ShaderParticleRenderer:
    def __init__(self):
        self.shader_program = None
        self.vao = None
        self.vbo = None
        self.compile_shaders()
        self.setup_buffers()

    def compile_shaders(self):
        # Vertex shader - simple pass-through
        vertex_shader_source = """
        #version 330 core
        layout (location = 0) in vec2 aPos;
        layout (location = 1) in float aSize;
        layout (location = 2) in vec4 aColor;
        
        out vec4 vertexColor;
        out float pointSize;
        
        void main() {
            gl_Position = vec4(aPos, 0.0, 1.0);
            gl_PointSize = aSize;
            vertexColor = aColor;
        }
        """

        # Fragment shader - draw circles
        fragment_shader_source = """
        #version 330 core
        in vec4 vertexColor;
        in float pointSize;
        out vec4 FragColor;
        
        void main() {
            vec2 coord = gl_PointCoord - vec2(0.5);
            float dist = length(coord);
            
            if (dist > 0.5) {
                discard;
            }
            
            // Smooth edges
            float alpha = 1.0 - smoothstep(0.4, 0.5, dist);
            FragColor = vec4(vertexColor.rgb, vertexColor.a * alpha);
        }
        """

        # Compile shaders individually
        vertex_shader = compileShader(vertex_shader_source, GL_VERTEX_SHADER)
        fragment_shader = compileShader(fragment_shader_source, GL_FRAGMENT_SHADER)

        # Create and link program manually without validation
        self.shader_program = glCreateProgram()
        glAttachShader(self.shader_program, vertex_shader)
        glAttachShader(self.shader_program, fragment_shader)
        glLinkProgram(self.shader_program)

        # Check linking status
        if glGetProgramiv(self.shader_program, GL_LINK_STATUS) != GL_TRUE:
            info_log = glGetProgramInfoLog(self.shader_program)
            raise RuntimeError(f"Shader program linking failed: {info_log}")

        # Clean up shaders (they're now linked into the program)
        glDeleteShader(vertex_shader)
        glDeleteShader(fragment_shader)

    def setup_buffers(self):
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)

        # Allocate buffer with dummy data to initialize it
        dummy_data = np.array([0.0] * 7, dtype=np.float32)
        glBufferData(GL_ARRAY_BUFFER, dummy_data.nbytes, dummy_data, GL_DYNAMIC_DRAW)

        # Position attribute
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 7 * 4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)

        # Size attribute
        glVertexAttribPointer(1, 1, GL_FLOAT, GL_FALSE, 7 * 4, ctypes.c_void_p(2 * 4))
        glEnableVertexAttribArray(1)

        # Color attribute
        glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 7 * 4, ctypes.c_void_p(3 * 4))
        glEnableVertexAttribArray(2)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def render_particles(self, particle_system, display_width, display_height):
        # Get render data from particle system
        vertex_data = particle_system.get_render_data()
        if vertex_data is None:
            return

        # Save OpenGL state to restore later
        last_program = glGetIntegerv(GL_CURRENT_PROGRAM)
        last_vao = glGetIntegerv(GL_VERTEX_ARRAY_BINDING)
        last_array_buffer = glGetIntegerv(GL_ARRAY_BUFFER_BINDING)
        last_blend_src = glGetIntegerv(GL_BLEND_SRC_ALPHA)
        last_blend_dst = glGetIntegerv(GL_BLEND_DST_ALPHA)
        last_blend_enabled = glIsEnabled(GL_BLEND)

        try:
            # Convert screen coordinates to normalized device coordinates
            vertex_data[:, 0] = (vertex_data[:, 0] / display_width) * 2.0 - 1.0
            vertex_data[:, 1] = 1.0 - (vertex_data[:, 1] / display_height) * 2.0  # Flip Y

            # Flatten for OpenGL
            vertex_data_flat = vertex_data.flatten()

            # Enable point size in shader
            glEnable(GL_PROGRAM_POINT_SIZE)

            # Bind VAO first, then shader program
            glBindVertexArray(self.vao)
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glBufferData(GL_ARRAY_BUFFER, vertex_data_flat.nbytes, vertex_data_flat, GL_DYNAMIC_DRAW)

            glUseProgram(self.shader_program)

            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            glDrawArrays(GL_POINTS, 0, len(vertex_data))

        finally:
            # Restore OpenGL state
            if last_blend_enabled:
                glEnable(GL_BLEND)
            else:
                glDisable(GL_BLEND)
            glBlendFunc(last_blend_src, last_blend_dst)

            glDisable(GL_PROGRAM_POINT_SIZE)

            glUseProgram(last_program)
            glBindBuffer(GL_ARRAY_BUFFER, last_array_buffer)
            glBindVertexArray(last_vao)

    def cleanup(self):
        if self.vao:
            glDeleteVertexArrays(1, [self.vao])
        if self.vbo:
            glDeleteBuffers(1, [self.vbo])
        if self.shader_program:
            glDeleteProgram(self.shader_program)


def create_cool_effect_callback(particle_system, renderer):
    def cb(draw_list: imgui.DrawList, draw_cmd: imgui.DrawCmd, user_data):
        # Update particle system
        particle_system.update()

        # Get display size for coordinate conversion
        io = imgui.get_io()
        display_width = io.display_size[0]
        display_height = io.display_size[1]

        # Render particles using modern OpenGL
        renderer.render_particles(particle_system, display_width, display_height)

    return cb


def run():
    try:
        from example.util import imgui_window
        from example.demo_window import show_demo_window
    except ModuleNotFoundError:
        from .example.util import imgui_window
        from .example.demo_window import show_demo_window

    font_path = Path(__file__).parent / "assets/font/MiSans-Medium.ttf"
    font_bytes = font_path.read_bytes()

    window = imgui_window.ImguiWindow(
        title="Prompt tool",
        close_on_esc=True,
        font_bytes=font_bytes,
        request_opengl_core_profile=True,
    )
    window.set_font_size(24)
    implot.create_context()

    texture = _make_texture()

    # Create particle system and modern OpenGL renderer
    particle_system = ParticleSystem(max_particles=100000)
    particle_renderer = ShaderParticleRenderer()
    cool_effect_cb = create_cool_effect_callback(particle_system, particle_renderer)

    def cb(draw_list: imgui.DrawList, draw_cmd: imgui.DrawCmd, user_data):
        col = imgui.get_color_u32((1, 0, 0, 1))
        draw_list.add_rect_filled((0, 0), (100, 200), col)

    try:
        while not window.should_close():
            window.begin_frame()

            # Add the cool effect to background draw list

            show_demo_window(True, texture)

            imgui.begin("Prompt tool")
            # dl = imgui.get_window_draw_list()
            # dl = imgui.get_foreground_draw_list()
            # dl.add_callback(cool_effect_cb, 0)
            # dl.add_callback(cb, 0)
            imgui.text("Hello world!")
            imgui.text("Move mouse to interact with particles!")
            imgui.text(f"Particles: {particle_system.particle_count}")
            if imgui.button("Click me!"):
                particle_system.spawn_particles(100)
            imgui.end()
            
            imgui.begin("Viewport Layer Redraw")
            # imgui.set_next_item_allow_overlap()
            # imgui.button("Click1", (100, 100))
            # imgui.same_line()
            # imgui.set_next_item_allow_overlap()
            # pos = imgui.get_cursor_pos()
            # imgui.set_cursor_pos((pos[0] - 50, pos[1]))
            # imgui.button("Click2", (100, 100))
            
            imgui.set_next_item_allow_overlap() # Allow subsequent items to overlap this button
            if (imgui.button("Button 1", (100, 100))):
                print("Button 1 clicked")

            imgui.set_cursor_pos((0, 0)) # Position Button 2 on top of Button 1
            if (imgui.button("Button 2", (50, 50))):
                print("Button 2 clicked")

            window.end_frame()
    finally:
        # Clean up OpenGL resources
        particle_renderer.cleanup()

    window.close()


def main():
    run()


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(message)s")
    main()
