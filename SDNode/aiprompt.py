import socket
import json
from threading import Thread
from mathutils import Vector
from ..timer import Timer
from ..kclogger import logger

address = "127.0.0.1"
port = 54534

apn_name_map = {
    'prmopt': 'positive',  # 正面
    'negativeprmopt': 'negative',  # 反面
    'sampler': '',  # 采样ID
    'samplerName': 'sampler_name',  # 采样名
    'step': 'steps',  # 步数
    'width': 'width',  # 宽
    'height': 'height',  # 高
    'batch': 'batch_size',  # 批次
    'batchnum': '',  # 批量
    'cfg': 'cfg',  # 相关性
    'seed': 'seed',  # 种子
}
sampler_name_map = {
    "Euler": "euler",
    "Euler a": "euler_ancestral",
    "LMS": "lms",
    "Heun": "heun",
    "DPM2": "dpm_2",
    "DPM2 a": "dpm_2_ancestral",
    "DPM++ 2S a": "dpmpp_2s_ancestral",
    "DPM++ 2M": "dpmpp_2m",
    "DPM++ SDE": "",
    "DPM fast": "dpm_fast",
    "DPM adaptive": "dpm_adaptive",
    "LMS Karras": "",
    "DPM2 Karras": "",
    "DPM2 a Karras": "",
    "DPM++ 2S a Karras": "",
    "DPM++ 2M Karras": "",
    "DPM++ SDE Karras": "",
    "DDIM": "ddim",
    "PLM": ""

    #  'euler',
    #  'euler_ancestral',
    #  'lms',
    #  'heun',
    #  'dpm_2',
    #  'dpm_2_ancestral',
    #  'dpmpp_2s_ancestral',
    #  'dpmpp_2m',
    #  'dpm_fast',
    #  'dpm_adaptive',
    #  'ddim',

    #  'dpmpp_sde',
    #  'uni_pc',
    #  'uni_pc_bh2'
}
# config = {
#     'seed': 79,
#     'steps': 20,
#     'cfg': 8.0,
#     'sampler_name': 'euler',
#     'scheduler': 'karras',
#     'positive': "one girl",
#     'negative': "bad hand",
#     'denoise': 1.0
# }


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


def load_apn_config(data):
    # apn_info = {
    # 'prmopt': jsoninfo['prmopt'],  # 正面
    # 'negativeprmopt': jsoninfo['negativeprmopt'],  # 反面
    # 'sampler': jsoninfo['sampler'],  # 采样ID
    # 'samplerName':jsoninfo['samplerName'],  # 采样名
    # 'step': jsoninfo['step'],  # 步数
    # 'width': jsoninfo['width'],  # 宽
    # 'height':jsoninfo['height'],  # 高
    # 'batch':jsoninfo['batch'],  # 批次
    # 'batchnum': jsoninfo['batchnum'],  # 批量
    # 'cfg': jsoninfo['cfg'],  # 相关性
    # 'seed': jsoninfo['seed'],  # 种子
    # }
    try:
        strinfo = '{"message":' + str(data, encoding='utf-8').split('{"message":')[1]
        config = json.loads(strinfo)['message']
    except Exception as e:
        logger.error(f"|已忽略| APN Parse Error -> {e}")
        return

    # print(apn_info)
    # ==================Print 参数如下==================================
    # {
    # 'prmopt': '(masterpiece:1.2, best quality), (ultra-detailed), (illustration), (ultra highres), (delicate illustration), (hyper detailed),1girl,weapon, gun, holding weapon, camouflage,sniper rifle, on a building roof, holding, holding sniper, twintails, red hair,bag, long sleeves, blue eyes, scope, bangs, jacket, blush, cities, trigger discipline,',
    # 'negativeprmopt': '(watermark), sketch, duplicate, ugly, huge eyes, text, logo, monochrome, worst face, (bad and mutated hands:1.3), (worst quality:2.0), (low quality:2.0), (blurry:2.0), horror, geometry, (bad hands), (missing fingers), multiple limbs, bad anatomy, (interlocked fingers:1.2), Ugly Fingers, (extra digit and hands and fingers and legs and arms:1.4), crown braid, ((2girl)), (deformed fingers:1.2), (long fingers:1.2), (bad-artist-anime), EasyNegative',
    # 'sampler': 0,
    # 'samplerName': 'Euler a',
    # 'step': 20,
    # 'width': 64,
    # 'height': 64,
    # 'batch': 1,
    # 'batchnum': 2,
    # 'cfg': 7,
    # 'seed': 0
    # }
    # ====================================================
    # 其中SD的里的SamplerName分别如下
    # ['Euler a','Euler','LMS','Heun','DPM2','DPM2 a','DPM++ 2S a','DPM++ 2M','DPM++ SDE','DPM fast','DPM adaptive','LMS Karras','DPM2 Karras','DPM2 a Karras','DPM++ 2S a Karras','DPM++ 2M Karras','DPM++ SDE Karras','DDIM','PLMS']
    # 而comfyUI的SamplerName分别如下
    # ['euler','euler_ancestral','heun','dpm_2','dpm_2_ancestral','lms','dpm_fast','dpm_adaptive','dpmpp_2s_ancestral','dpmpp_sde','dpmpp_2m','ddim','uni_pc','uni_pc_bh2']
    # ====================================================
    
    tree = get_tree()
    if not tree:
        return
    logger.info(f"Recv APN Data -> {config}")

    for k in list(config.keys()):
        if k not in apn_name_map:
            continue
        config[apn_name_map[k]] = config[k]

    ksampler = get_ksampler(tree)
    if not isinstance(config, dict):
        logger.warn(f"|已忽略| APN Config Not Matching")
        return
    if not ksampler:
        logger.warn(f"|已忽略| KSampler Not Found")
        return
    pre_proc(config, tree, ksampler)
    for inp in ksampler.inp_types:
        if inp in ksampler.inputs:
            continue
        ori = getattr(ksampler, inp)
        if inp == "sampler_name":
            sampler_name = sampler_name_map[config.get(inp, "Euler")]
            setattr(ksampler, inp, sampler_name if sampler_name else ori)
        else:
            setattr(ksampler, inp, type(ori)(config.get(inp, ori)))


def pre_proc(config, tree, ksampler):
    if positive := config.pop("positive", None):
        if ksampler.inputs["positive"].links:
            plink = ksampler.inputs["positive"].links[0]
            clip = tree.find_from_node(plink)
        else:
            clip = tree.nodes.new("CLIPTextEncode")
            clip.location = Vector((-292, -110)) + ksampler.location
            tree.links.new(ksampler.inputs["positive"], clip.outputs[0])
        clip.text = positive
    if negative := config.pop("negative", None):
        if ksampler.inputs["negative"].links:
            plink = ksampler.inputs["negative"].links[0]
            clip = tree.find_from_node(plink)
        else:
            clip = tree.nodes.new("CLIPTextEncode")
            clip.location = Vector((-292, -237)) + ksampler.location
            tree.links.new(ksampler.inputs["negative"], clip.outputs[0])
        clip.text = negative
    
    if width := config.pop("width", None):
        if node := get_latent_image(tree, ksampler):
            node.sdn_width = width
    if height := config.pop("height", None):
        if node := get_latent_image(tree, ksampler):
            node.sdn_height = height
    if batch_size := config.pop("batch_size", None):
        if node := get_latent_image(tree, ksampler):
            node.batch_size = batch_size

def get_latent_image(tree, ksampler):
    if ksampler.inputs['latent_image'].is_linked:
        node = ksampler.inputs['latent_image'].links[0].from_node
        if node.bl_idname != "EmptyLatentImage":
            return
    else:
        node = tree.nodes.new("EmptyLatentImage")
        tree.links.new(ksampler.inputs["latent_image"], node.outputs["LATENT"])
    return node

def run_forever():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.bind((address, port))
    except OSError:
        return
    server.listen(5)
    while True:
        conn, _ = server.accept()
        data = conn.recv(102400)
        if not data:
            break

        Timer.put((load_apn_config, data))
        conn.close()
        # while True:
        #     try:
        #         logger.error("RECV")
        #         data = conn.recv(102400)
        #         if not data:
        #             break

        #         Timer.put((load_apn_config, data))
        #     except ConnectionResetError as e:
        #         break
        # conn.close()


t = Thread(target=run_forever, daemon=True)
t.start()
