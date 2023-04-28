import socket
import json
from threading import Thread
from ..timer import Timer
from ..kclogger import logger
address = "127.0.0.1"
port = 54534

config = {'seed': 79,
          'steps': 20,
          'cfg': 8.0,
          'sampler_name': 'euler',
          'scheduler': 'karras',
          'positive': "one girl",
          'negative': "bad hand",
          'denoise': 1.0}


def get_tree():
    import bpy
    for a in bpy.context.screen.areas:
        for s in a.spaces:
            if s.type != "NODE_EDITOR":
                continue
            if s.tree_type != "CFNodeTree":
                continue
            return s.node_tree
    return None


def get_ksampler(tree):
    for node in tree.get_nodes(cmf=True):
        if not node.select:
            continue
        if node.class_type in {"KSampler", "KSamplerAdvanced"}:
            return node


def load_apn_config(config):
    from mathutils import Vector
    tree = get_tree()
    if not tree:
        return
    logger.info(f"Recv APN Data -> {config}")
    try:
        config = json.loads(config)
    except Exception as e:
        logger.error(f"|已忽略| APN Parse Error -> {e}")
        return

    ksampler = get_ksampler(tree)
    if not isinstance(config, dict):
        logger.warn(f"|已忽略| APN Config Not Matching")
        return
    if not ksampler:
        logger.warn(f"|已忽略| KSampler Not Found")
        return
    positive = config.pop("positive")
    negative = config.pop("negative")
    for inp in ksampler.inp_types:
        if inp in ksampler.inputs:
            continue
        ori = getattr(ksampler, inp)
        setattr(ksampler, inp, type(ori)(config.get(inp, ori)))
    if positive:
        if ksampler.inputs["positive"].links:
            plink = ksampler.inputs["positive"].links[0]
            clip = tree.find_from_node(plink)
        else:
            clip = tree.nodes.new("CLIPTextEncode")
            clip.location = Vector((-292, -110)) + ksampler.location
            tree.links.new(ksampler.inputs["positive"], clip.outputs[0])
        clip.text = positive
    if negative:
        if ksampler.inputs["negative"].links:
            plink = ksampler.inputs["negative"].links[0]
            clip = tree.find_from_node(plink)
        else:
            clip = tree.nodes.new("CLIPTextEncode")
            clip.location = Vector((-292, -237)) + ksampler.location
            tree.links.new(ksampler.inputs["negative"], clip.outputs[0])
        clip.text = negative

def run_forever():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((address, port))
    server.listen(5)
    while True:
        conn, _ = server.accept()
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                Timer.put((load_apn_config, data.decode()))
            except ConnectionResetError as e:
                break
        conn.close()


t = Thread(target=run_forever, daemon=True)
t.start()
