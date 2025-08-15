import { app } from "../../scripts/app.js";
import { $el } from "../../scripts/ui.js";

function deepEqual(obj1, obj2) {
  if (obj1 === obj2) return true;

  function isObject(obj) {
    return obj !== null && typeof obj === "object";
  }

  if (!isObject(obj1) || !isObject(obj2)) return false;

  const keys1 = Object.keys(obj1);
  const keys2 = Object.keys(obj2);

  if (keys1.length !== keys2.length) return false;

  for (let key of keys1) {
    if (!keys2.includes(key) || !deepEqual(obj1[key], obj2[key])) {
      console.error("key:", key);
      return false;
    }
  }

  return true;
}

class WebUIToComfyUI
{
    static SAMPLERNAME_W2C = {
        "Euler": "euler",
        "Euler a": "euler_ancestral",
        "Heun": "heun",
        "DPM fast": "dpm_fast",
        "DPM adaptive": "dpm_adaptive",
        "DPM2": "dpm_2",
        "DPM2 a": "dpm_2_ancestral",
        "DPM++ 2M": "dpmpp_2m",
        "DPM++ SDE": "dpmpp_sde_gpu",
        "DPM++ 2M SDE": "dpmpp_2m_sde_gpu",
        "DPM++ 3M SDE": "dpmpp_3m_sde",
        "DDIM": "ddim",
        "LMS": "lms",
        "LCM": "LCM",
        "UniPC": "uni_pc",
    };
    static SCHEDULERNAME_W2C = {
        "Automatic": "normal",
        "Karras": "karras",
        "Exponential": "exponential",
        "SGM Uniform": "sgm_uniform",
    };
    static PREPROCESSOR_W2C = {
        "animal_openpose": "AnimalPosePreprocessor",
        "blur_gaussian": "*TilePreprocessor",
        "canny": "CannyEdgePreprocessor",
        "densepose (pruple bg & purple torso)": "DensePosePreprocessor",
        "densepose_parula (black bg & blue torso)": "DensePosePreprocessor",
        "depth_anything": "DepthAnythingPreprocessor",
        "depth_anything_v2": "DepthAnythingV2Preprocessor",
        "depth_hand_refiner": "MeshGraphormer+ImpactDetector-DepthMapPreprocessor",
        "depth_leres": "LeReS-DepthMapPreprocessor",
        "depth_leres++": "*LeReS-DepthMapPreprocessor",
        "depth_midas": "MiDaS-DepthMapPreprocessor",
        "depth_zoe": "Zoe-DepthMapPreprocessor",
        "dw_openpose_full": "DWPreprocessor",
        "facexlib": "",
        "inpaint_global_harmonious": "",
        "inpaint_only": "InpaintPreprocessor",
        "inpaint_only+lama": "",
        "instant_id_face_embedding": "",
        "instant_id_face_keypoints": "",
        "invert (from white bg & black line)": "ImageInvert",
        "ip-adapter-auto": "IPAdapter+IPAdapterUnifiedLoader",
        "ip-adapter_clip_g": "IPAdapter+IPAdapterUnifiedLoader",
        "ip-adapter_clip_h": "IPAdapter+IPAdapterUnifiedLoader",
        "ip-adapter_clip_sdxl_plus_vith": "IPAdapter+IPAdapterUnifiedLoader",
        "ip-adapter_face_id": "IPAdapterFaceID+IPAdapterUnifiedLoaderFaceID",
        "ip-adapter_face_id_plus": "IPAdapterFaceID+IPAdapterUnifiedLoaderFaceID",
        "ip-adapter_pulid": "",
        "lineart_anime": "AnimeLineArtPreprocessor",
        "lineart_anime_denoise": "",
        "lineart_coarse": "LineArtPreprocessor",
        "lineart_realistic": "LineArtPreprocessor",
        "lineart_standard (from white bg & black line)": "LineartStandardPreprocessor",
        "mediapipe_face": "MediaPipe-FaceMeshPreprocessor",
        "mlsd": "M-LSDPreprocessor",
        "none": "",
        "normal_bae": "BAE-NormalMapPreprocessor",
        "normal_dsine": "DSINE-NormalMapPreprocessor",
        "normal_midas": "MiDaS-NormalMapPreprocessor",
        "openpose": "OpenposePreprocessor",
        "openpose_face": "OpenposePreprocessor",
        "openpose_faceonly": "OpenposePreprocessor",
        "openpose_full": "OpenposePreprocessor",
        "openpose_hand": "OpenposePreprocessor",
        "recolor_intensity": "ImageIntensityDetector",
        "recolor_luminance": "ImageLuminanceDetector",
        "reference_adain": "",
        "reference_adain+attn": "",
        "reference_only": "",
        "revision_clipvision": "",
        "revision_ignore_prompt": "",
        "scribble_hed": "FakeScribblePreprocessor",
        "scribble_pidinet": "Scribble_PiDiNet_Preprocessor",
        "scribble_xdog": "Scribble_XDoG_Preprocessor",
        "seg_anime_face": "AnimeFace_SemSegPreprocessor",
        "seg_ofade20k": "OneFormer-ADE20K-SemSegPreprocessor",
        "seg_ofcoco": "OneFormer-COCO-SemSegPreprocessor",
        "seg_ufade20k": "UniFormer-SemSegPreprocessor",
        "shuffle": "ShufflePreprocessor",
        "softedge_anyline": "",
        "softedge_hed": "HEDPreprocessor",
        "softedge_hedsafe": "HEDPreprocessor",
        "softedge_pidinet": "PiDiNetPreprocessor",
        "softedge_pidisafe": "PiDiNetPreprocessor",
        "softedge_teed": "TEED_Preprocessor",
        "t2ia_color_grid": "ColorPreprocessor",
        "t2ia_sketch_pidi": "",
        "t2ia_style_clipvision": "",
        "threshold": "BinaryPreprocessor",
        "tile_colorfix": "",
        "tile_colorfix+sharp": "",
        "tile_resample": "TilePreprocessor",
    }
    constructor(text){
        this.text = text;
        this.parse_cn = false;
        this.params = {};
    }
    is_webui_format(){
        if (this.text.includes("Negative prompt: ") && this.text.includes("Steps:"))
            return true;
        return false;
    }
    with_efficient(){
      return "Efficient Loader" in LiteGraph.registered_node_types && "KSampler (Efficient)" in LiteGraph.registered_node_types;
    }
    apply_nodes_offset(nodes, offset=[0, 0]){
        for (var node of nodes) {
          node["pos"][0] += offset[0];
          node["pos"][1] += offset[1];
        }
    }
    find_following_nodes(wk, node, _nodes = []){
      for (var out of node["outputs"] || []) {
        if (!out["links"]) continue;
        for (var link_id of out["links"] || []) {
          var _l = wk["links"].find((l) => l[0] == link_id);
          if (!_l) continue;
          var _in = wk["nodes"].find((n) => n["id"] == _l[3]);
          if (!_in) continue;
          if (!_nodes.includes(_in)) _nodes.push(_in);
          this.find_following_nodes(wk, _in, _nodes);
        }
      }
      return _nodes;
    }
    make_link(workflow, out_node, out_index, in_node, in_index)
    {
        var last_link_id = ++workflow["last_link_id"];
        var ltype = out_node["outputs"][out_index].type | null;
        var link = [
          last_link_id,
          out_node["id"],
          out_index,
          in_node["id"],
          in_index,
          ltype,
        ];
        out_node["outputs"][out_index].links.push(last_link_id);
        var old_in_link = in_node["inputs"][in_index].link;
        if (old_in_link !== null && old_in_link != last_link_id)
          this.remove_link(workflow, old_in_link);
        in_node["inputs"][in_index].link = last_link_id;
        workflow["links"].push(link);
    }
    remove_link(workflow, link_id)
    {
      if (link_id === null || link_id === undefined) return;
      if (link_id == workflow["last_link_id"]) workflow["last_link_id"]--;
      for (var i = 0; i < workflow["links"].length; i++) {
        var link = workflow["links"][i];
        if (link[0] == link_id) {
          workflow["links"].splice(i, 1);
          return;
        }
      }
    }
    remove_node_by_id(workflow, id)
    {
      if (id === null || id === undefined) return;
      var find_node = null;
      var find_node_index = -1;
      for (var i = 0; i < workflow["nodes"].length; i++) {
        if (workflow["nodes"][i].id == id) {
          find_node = workflow["nodes"][i];
          find_node_index = i;
          break;
        }
      }
      if (find_node == null) return;
      // 移除关联的link
      for (var i = 0; i < (find_node.inputs || []).length; i++) {
        var link_id = find_node.inputs[i].link;
        if (link_id == null) continue;
        for (var node of workflow["nodes"]) {
          for(var output of node.outputs)
          {
            var f_index = output.links.indexOf(link_id);
            if (f_index == -1) continue;
            output.links.splice(f_index, 1);
          }
        }
        this.remove_link(workflow, link_id);
      }
      for (var i = 0; i < (find_node.outputs || []).length; i++) {
        for (var link_id of find_node.outputs[i].links) {
          if (link_id == null) continue;
          for (var node of workflow["nodes"]) {
            for(var input of node.inputs || [])
              input.link = input.link == link_id ? null : input.link;
          }
          this.remove_link(workflow, link_id);
        }
      }
      // 移除节点
      workflow["nodes"].splice(find_node_index, 1);
    }
    to_comfyui_format(){
      if (this.with_efficient())
      {
        return this.to_comfyui_format_efficient();
      }
      return this.to_comfyui_format_base();
    }
    to_comfyui_format_base(){
        var params = this.params;
        var wk = this.base_workflow();
        this.apply_nodes_offset(wk["nodes"], [-200, 63]);
        var np = wk["nodes"][0];
        var pp = wk["nodes"][1];
        var empty_image = wk["nodes"][2];
        var ksampler = wk["nodes"][3];
        var checkpoint_loader = wk["nodes"][6];
        var clip_last_layer = wk["nodes"][7];
        if ("Negative prompt" in params)
            np["widgets_values"][0] = params["Negative prompt"];
        if ("Positive prompt" in params)
            pp["widgets_values"][0] = params["Positive prompt"];
        if ("Size" in params)
        {
            var width = 512;
            var height = 512;
            if (params["Size"].includes("x"))
            {
                var size_list = params["Size"].split("x");
                width = size_list[0];
                height = size_list[1];
            }
            empty_image["widgets_values"][0] = width;
            empty_image["widgets_values"][1] = height;
        }
        if ("Seed" in params)
            ksampler["widgets_values"][0] = params["Seed"];
        if ("Steps" in params)
            ksampler["widgets_values"][2] = params["Steps"];
        if ("CFG scale" in params)
            ksampler["widgets_values"][3] = params["CFG scale"];
        if ("Sampler" in params)
        {
            var sampler_name = params["Sampler"];
            var scheduler_name = "normal";
            if ("Schedule type" in params)
            {
                sampler_name = params["Sampler"];
                scheduler_name = params["Schedule type"];
            }
            else
            {
                // samper存储 sampler_name + " " + scheduler_name
                var all_scheduler_names = Object.keys(WebUIToComfyUI.SCHEDULERNAME_W2C);
                for(const one_sch_name of all_scheduler_names)
                {
                  if (sampler_name.includes(one_sch_name))
                  {
                      scheduler_name = one_sch_name;
                      sampler_name = sampler_name.replace(one_sch_name, "").trim();
                      break;
                  }
                }
            }
            if (sampler_name in WebUIToComfyUI.SAMPLERNAME_W2C)
                ksampler["widgets_values"][4] = WebUIToComfyUI.SAMPLERNAME_W2C[sampler_name];
            if (scheduler_name in WebUIToComfyUI.SCHEDULERNAME_W2C)
                ksampler["widgets_values"][5] = WebUIToComfyUI.SCHEDULERNAME_W2C[scheduler_name];
            this._gen_control_net(wk, ksampler, pp, np);
        }
        if ("Denoising strength" in params)
        {
            ksampler["widgets_values"][6] = params["Denoising strength"];
            if (params["Denoising strength"] < 1)
            {
              // 图生图, 需要添加图片输入
              var last_node_id = wk["last_node_id"];
              var load_image = {
                id: ++last_node_id,
                type: "LoadImage",
                pos: [250, -110],
                size: [320, 310],
                mode: 0,
                outputs: [
                  {
                    name: "IMAGE",
                    type: "IMAGE",
                    links: [],
                    shape: 3,
                    label: "图像",
                    slot_index: 0,
                  },
                  {
                    name: "MASK",
                    type: "MASK",
                    links: null,
                    shape: 3,
                    label: "遮罩",
                  },
                ],
                properties: { "Node name for S&R": "LoadImage" },
                widgets_values: ["xxx.png", "image"],
              };
              var vae_encode = {
                id: ++last_node_id,
                type: "VAEEncode",
                pos: [640, 10],
                size: [210, 50],
                mode: 0,
                inputs: [
                  {
                    name: "pixels",
                    type: "IMAGE",
                    link: 0,
                    label: "图像",
                  },
                  {
                    name: "vae",
                    type: "VAE",
                    link: null,
                    label: "VAE",
                  },
                ],
                outputs: [
                  {
                    name: "LATENT",
                    type: "LATENT",
                    links: [],
                    shape: 3,
                    label: "Latent",
                    slot_index: 0,
                  },
                ],
                properties: { "Node name for S&R": "VAEEncode" },
              };
              wk["nodes"].push(load_image);
              wk["nodes"].push(vae_encode);
              wk["last_node_id"] = last_node_id;
              this.remove_node_by_id(wk, empty_image["id"]);
              this.make_link(wk, load_image, 0, vae_encode, 0);
              this.make_link(wk, checkpoint_loader, 2, vae_encode, 1);
              this.make_link(wk, vae_encode, 0, ksampler, 3);
            }
        }
        if ("Model" in params)
        {
            var model = params["Model"]; // TODO: 模型得加后缀名字, 和webui不同
            var node_type = LiteGraph.registered_node_types[checkpoint_loader.type];
            var model_list = node_type?.nodeData?.input?.required?.ckpt_name?.[0];
            model_list = model_list ? model_list : [];
            for(var _m of model_list)
            {
                var sep_i = _m.lastIndexOf("/");
                if(_m.slice(sep_i + 1).split(".")[0] == model)
                    checkpoint_loader["widgets_values"][0] = _m;
            }
            // if (model_list && model_list.contain(model))
            //     checkpoint_loader["widgets_values"][0] = params["Model"]; // TODO: 模型得加后缀名字, 和webui不同
        }
        if ("Clip skip" in params)
            clip_last_layer["widgets_values"][0] = -1 * params["Clip skip"];
        return JSON.stringify(wk);
    }
    to_comfyui_format_efficient(){
      var params = this.params;
      var wk = this.efficient_workflow();
      var loader = wk["nodes"][1];
      var ksampler = wk["nodes"][2];
      if ("Negative prompt" in params)
          loader["widgets_values"][7] = params["Negative prompt"];
      if ("Positive prompt" in params)
          loader["widgets_values"][6] = params["Positive prompt"];
      if ("Size" in params)
      {
          var width = 512;
          var height = 512;
          if (params["Size"].includes("x"))
          {
              var size_list = params["Size"].split("x");
              width = size_list[0];
              height = size_list[1];
          }
          loader["widgets_values"][10] = width;
          loader["widgets_values"][11] = height;
      }
      if ("Seed" in params)
          ksampler["widgets_values"][0] = params["Seed"];
      if ("Steps" in params)
          ksampler["widgets_values"][2] = params["Steps"];
      if ("CFG scale" in params)
          ksampler["widgets_values"][3] = params["CFG scale"];
      if ("Sampler" in params)
      {
          var sampler_name = params["Sampler"];
          var scheduler_name = "normal";
          if ("Schedule type" in params)
          {
              sampler_name = params["Sampler"];
              scheduler_name = params["Schedule type"];
          }
          else
          {
              // samper存储 sampler_name + " " + scheduler_name
              var all_scheduler_names = Object.keys(WebUIToComfyUI.SCHEDULERNAME_W2C);
              for(const one_sch_name of all_scheduler_names)
              {
                if (sampler_name.includes(one_sch_name))
                {
                    scheduler_name = one_sch_name;
                    sampler_name = sampler_name.replace(one_sch_name, "").trim();
                    break;
                }
              }
          }
          if (sampler_name in WebUIToComfyUI.SAMPLERNAME_W2C)
              ksampler["widgets_values"][4] = WebUIToComfyUI.SAMPLERNAME_W2C[sampler_name];
          if (scheduler_name in WebUIToComfyUI.SCHEDULERNAME_W2C)
              ksampler["widgets_values"][5] = WebUIToComfyUI.SCHEDULERNAME_W2C[scheduler_name];
          this._gen_control_net(wk, ksampler, loader, loader);
      }
      if ("Denoising strength" in params)
      {
        ksampler["widgets_values"][6] = params["Denoising strength"];
        if (params["Denoising strength"] < 1)
        {
          // 图生图, 需要添加图片输入
          var last_node_id = wk["last_node_id"];
          var load_image = {
            id: ++last_node_id,
            type: "LoadImage",
            pos: [250, -110],
            size: [320, 310],
            mode: 0,
            outputs: [
              {
                name: "IMAGE",
                type: "IMAGE",
                links: [],
                shape: 3,
                label: "图像",
                slot_index: 0,
              },
              {
                name: "MASK",
                type: "MASK",
                links: null,
                shape: 3,
                label: "遮罩",
              },
            ],
            properties: { "Node name for S&R": "LoadImage" },
            widgets_values: ["xxx.png", "image"],
          };
          var vae_encode = {
            id: ++last_node_id,
            type: "VAEEncode",
            pos: [640, 10],
            size: { 0: 210, 1: 50 },
            mode: 0,
            inputs: [
              {
                name: "pixels",
                type: "IMAGE",
                link: 0,
                label: "图像",
              },
              {
                name: "vae",
                type: "VAE",
                link: null,
                label: "VAE",
              },
            ],
            outputs: [
              {
                name: "LATENT",
                type: "LATENT",
                links: [],
                shape: 3,
                label: "Latent",
                slot_index: 0,
              },
            ],
            properties: { "Node name for S&R": "VAEEncode" },
          };
          wk["nodes"].push(load_image);
          wk["nodes"].push(vae_encode);
          wk["last_node_id"] = last_node_id;
          this.make_link(wk, load_image, 0, vae_encode, 0);
          this.make_link(wk, loader, 4, vae_encode, 1);
          this.make_link(wk, vae_encode, 0, ksampler, 3);
        }
      }
      if ("Model" in params)
      {
          var model = params["Model"]; // 模型得加后缀名字, 和webui不同
          var node_type = LiteGraph.registered_node_types[loader.type];
          var model_list = node_type?.nodeData?.input?.required?.ckpt_name?.[0];
          model_list = model_list ? model_list : [];
          for(var _m of model_list)
          {
              var sep_i = _m.lastIndexOf("/");
              if(_m.slice(sep_i + 1).split(".")[0] == model)
                  loader["widgets_values"][0] = _m;
          }
      }
      if ("Clip skip" in params)
          loader["widgets_values"][2] = -1 * params["Clip skip"];
      return JSON.stringify(wk);
    }
    parse(text){
        this.text = text ? text : this.text;
        this.test();
        this.parse_cn = true;
        this._parse(text);
        return this.params;
    }
    _parse(text){
        if(text !== undefined)
        {
            this.text = text;
            this.params = {};
        }
        this._prompt();
        this._base();
        this._control_net();
        this._ti_hashes();
        this._tiled_diffusion();
        this._adetailer();
        this._version();
        return this.params;
    }
    _prompt(){
        var pp = this.text.match(/^(.*?)Negative prompt:/s);
        if(pp !== null)
        {
            pp = pp[1].trim();
            var pp_str = pp.slice(-1) == "," ? pp.slice(0, -1).trim() : pp;
            if (pp_str.startsWith("parameters"))
              pp_str = pp_str.slice("parameters".length).trim();
            this.params["Positive prompt"] = pp_str;
            this.text = this.text.replace(pp, "").trim();
        }
        var np = this.text.match(/(Negative prompt: .*?)(?:Steps: )/s);
        np = np ? np : this.text.match(/(Negative prompt: .*?)(?:,\r\n)/s);
        np = np ? np : this.text.match(/(Negative prompt: .*?)(?:,\n)/s);
        np = np ? np : this.text.match(/(Negative prompt: .*?)(?:\n)/s);
        if(np !== null)
        {
            var prompt = np[1].slice("Negative prompt: ".length).trim();
            prompt = prompt.slice(-1) == "," ? prompt.slice(0, -1).trim() : prompt;
            this.params["Negative prompt"] = prompt;
            this.text = this.text.replace(np[1], "").trim();
        }
    }
    _control_net(){
        /*
Controlnet 0: "preprocessor: dw_openpose_full, model: control_v11p_sd15_openpose, weight: 1.0, starting/ending: (0.0, 1.0), resize mode: Crop and Resize, pixel_perfect: False, control mode: Balanced, preprocessor params: (1024, None, None)", 
Controlnet 1: "preprocessor: depth_leres (LeRes 深度图估算）, model: control_v11f1p_sd15_depth, weight: 0.7, starting/ending: (0.23, 0.76), resize mode: Crop and Resize, pixel_perfect: True, control mode: Balanced, preprocessor params: (1024, 0, 0)", 
ControlNet 2: "Module: tile_resample, Model: control_v11f1e_sd15_tile_fp16 [3b860298], Weight: 0.6, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 1.0, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced",
        */
        if (this.text.match(/(Control[nN]et \d+): /s) == null) return;
        function parse_cn_params(text) {
          var params = {};
          var new_ver = text.includes("preprocessor params: ");
          if (new_ver) {
            // Controlnet 0: "preprocessor: dw_openpose_full, model: control_v11p_sd15_openpose, weight: 1.0, starting/ending: (0.0, 1.0), resize mode: Crop and Resize, pixel_perfect: False, control mode: Balanced, preprocessor params: (1024, None, None)",
            var preprocessor = text.match(/preprocessor: (.*?), /s)[1];
            var model = text.match(/model: (.*?), /s)[1];
            var weight = text.match(/weight: (.*?), /s)[1];
            var starting_end = text.match(/starting\/ending: \((.*?)\),/s)[1];
            starting_end = starting_end ? JSON.parse(`[${starting_end}]`) : [];
            var resize_mode = text.match(/resize mode: (.*?), /s)[1];
            var pixel_perfect = text.match(/pixel_perfect: (.*?), /s)[1];
            pixel_perfect = pixel_perfect == "True";
            var control_mode = text.match(/control mode: (.*?),/s)[1];
            var pp_params = text.match(/preprocessor params: \((.*?)\)/s)[1];
            pp_params = pp_params.replaceAll("None", "null");
            // 去掉括号并按逗号分割
            pp_params = pp_params ? JSON.parse(`[${pp_params}]`) : [];

            params = {
              preprocessor: preprocessor,
              model: model,
              weight: weight,
              starting_end: starting_end,
              resize_mode: resize_mode,
              preprocessor_params: pp_params,
              pixel_perfect: pixel_perfect,
              control_mode: control_mode,
            };
          } else {
            // "ControlNet 0": "Module: tile_resample, Model: control_v11f1e_sd15_tile_fp16 [3b860298], Weight: 0.6, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 1.0, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced",
            var preprocessor = text.match(/Module: (.*?), /s)[1];
            var model = text.match(/Model: (.*?), /s)[1];
            var weight = text.match(/Weight: (.*?), /s)[1];
            var resize_mode = text.match(/Resize Mode: (.*?), /s)[1];

            var pp_param_res = text.match(/Processor Res: (.*?), /s)[1];
            var pp_param_a = text.match(/Threshold A: (.*?), /s)[1];
            var pp_param_b = text.match(/Threshold B: (.*?), /s)[1];

            var starting = text.match(/Guidance Start: (.*?), /s)[1];
            var end = text.match(/Guidance End: (.*?), /s)[1];
            var pixel_perfect = text.match(/Pixel Perfect: (.*?), /s)[1];
            pixel_perfect = pixel_perfect == "True";
            var control_mode = text.match(/Control Mode: (.*?)$/s)[1];
            params = {
              preprocessor: preprocessor,
              model: model,
              weight: weight,
              starting_end: [starting, end],
              resize_mode: resize_mode,
              preprocessor_params: [pp_param_res, pp_param_a, pp_param_b],
              pixel_perfect: pixel_perfect,
              control_mode: control_mode,
            };
          }
          return params;
        }
        var cns = this.text.matchAll(/(Control[nN]et \d+): "(.*?)",/gs);
        for (const cn of cns) {
          this.params[cn[1]] = this.parse_cn ? parse_cn_params(cn[2]) : cn[2];
          this.text = this.text.replace(cn[0], "");
        }
    }
    _gen_control_net(wk, ksampler, out_p, out_n)
    {
      const offset = 500;
      // CN部分
      var load_image_cn = {
        id: wk["last_node_id"] + 1,
        type: "LoadImage",
        pos: [320, 800],
        mode: 0,
        outputs: [
          {
            name: "IMAGE",
            type: "IMAGE",
            links: [],
            shape: 3,
            label: "图像",
            slot_index: 0,
          },
          {
            name: "MASK",
            type: "MASK",
            links: null,
            shape: 3,
            label: "遮罩",
          },
        ],
        widgets_values: ["xxx.png", "image"],
      };
      wk["nodes"].push(load_image_cn);
      wk["last_node_id"] += 1;
      var count = -1;
      for (var key in this.params) {
        if (!key.toLowerCase().startsWith("controlnet")) continue;
        ++count;
        var last_node_id = wk["last_node_id"];
        var value = this.params[key];
        // 新增 aux 集成 preproccessor
        var aux_preprocessor = {
          id: last_node_id + 1,
          type: "AIO_Preprocessor",
          pos: [700 + offset * count, 640],
          mode: 0,
          inputs: [
            {
              name: "image",
              type: "IMAGE",
              link: null,
              label: "图像",
            },
          ],
          outputs: [
            {
              name: "IMAGE",
              type: "IMAGE",
              links: [],
              shape: 3,
              label: "图像",
              slot_index: 0,
            },
          ],
          widgets_values: ["CannyEdgePreprocessor", 512],
        };
        // 新增 apply controlnet
        var apply_controlnet = {
          id: last_node_id + 2,
          type: "ControlNetApplyAdvanced",
          pos: [710 + offset * count, 270],
          mode: 0,
          inputs: [
            {
              name: "positive",
              type: "CONDITIONING",
              link: null,
              label: "正面条件",
            },
            {
              name: "negative",
              type: "CONDITIONING",
              link: null,
              label: "负面条件",
            },
            {
              name: "control_net",
              type: "CONTROL_NET",
              link: null,
              label: "ControlNet",
            },
            {
              name: "image",
              type: "IMAGE",
              link: null,
              label: "图像",
            },
          ],
          outputs: [
            {
              name: "positive",
              type: "CONDITIONING",
              links: [],
              shape: 3,
              label: "正面条件",
              slot_index: 0,
            },
            {
              name: "negative",
              type: "CONDITIONING",
              links: [20],
              shape: 3,
              label: "负面条件",
              slot_index: 1,
            },
          ],
          widgets_values: [1, 0, 1],
        };
        var controlnet_loader = {
          id: last_node_id + 3,
          type: "ControlNetLoader",
          pos: [720 + offset * count, 500],
          mode: 0,
          outputs: [
            {
              name: "CONTROL_NET",
              type: "CONTROL_NET",
              links: [],
              shape: 3,
              label: "ControlNet",
            },
          ],
          widgets_values: ["xxx.pth", null],
        };
        wk["last_node_id"] += 3;
        wk["nodes"].push(aux_preprocessor, apply_controlnet, controlnet_loader);
        // 参数处理
        if(value["preprocessor"] in WebUIToComfyUI.PREPROCESSOR_W2C)
        {
          var pmodel = WebUIToComfyUI.PREPROCESSOR_W2C[value["preprocessor"]];
          pmodel = pmodel || aux_preprocessor["widgets_values"][0];
          aux_preprocessor["widgets_values"][0] = pmodel;
        }
        aux_preprocessor["widgets_values"][1] = value["preprocessor_params"][0];
        // controlnet_loader["widgets_values"][0] = value["model"];
        
        var cn_model = value["model"];
        if (cn_model.includes("[") && cn_model.includes("]"))
          cn_model = cn_model.slice(0, cn_model.indexOf("[")).trim();
        var cn_model2 = cn_model.replaceAll("_", "-");
        var node_type = LiteGraph.registered_node_types[controlnet_loader.type];
        var ml = node_type?.nodeData?.input?.required?.control_net_name?.[0];
        ml = ml || [];
        var find_cn_model = "";
        if (ml) find_cn_model = find_cn_model || ml[0];
        for (var _m of ml || []) {
          var sep_i = _m.lastIndexOf("/");
          if (_m.slice(sep_i + 1).split(".")[0] in [cn_model, cn_model2])
            find_cn_model = _m;
        }
        controlnet_loader["widgets_values"][0] = find_cn_model;
        apply_controlnet["widgets_values"][0] = value["weight"];
        apply_controlnet["widgets_values"][1] = value["starting_end"][0];
        apply_controlnet["widgets_values"][2] = value["starting_end"][1];
        this.make_link(wk, load_image_cn, 0, aux_preprocessor, 0);
        this.make_link(wk, controlnet_loader, 0, apply_controlnet, 2);
        this.make_link(wk, aux_preprocessor, 0, apply_controlnet, 3);
        // 完美像素
        if (value["pixel_perfect"])
        {
          aux_preprocessor["inputs"].push({
            name: "resolution",
            type: "INT",
            link: null,
            widget: {
              name: "resolution",
            },
            label: "分辨率",
          });
          var gen_res = {
            id: wk["last_node_id"] + 1,
            type: "ImageGenResolutionFromImage",
            pos: [690 + offset * count, 950],
            mode: 0,
            inputs: [
              {
                name: "image",
                type: "IMAGE",
                link: null,
                label: "图像",
              },
            ],
            outputs: [
              {
                name: "IMAGE_GEN_WIDTH (INT)",
                type: "INT",
                links: [],
                shape: 3,
                label: "宽度(整数)",
                slot_index: 0,
              },
              {
                name: "IMAGE_GEN_HEIGHT (INT)",
                type: "INT",
                links: [],
                shape: 3,
                label: "高度(整数)",
                slot_index: 1,
              },
            ],
          };
          var pixel_perfect = {
            id: wk["last_node_id"] + 2,
            type: "PixelPerfectResolution",
            pos: [680 + offset * count, 780],
            mode: 0,
            inputs: [
              {
                name: "original_image",
                type: "IMAGE",
                link: null,
                label: "图像",
              },
              {
                name: "image_gen_width",
                type: "INT",
                link: null,
                widget: {
                  name: "image_gen_width",
                },
                label: "宽度",
              },
              {
                name: "image_gen_height",
                type: "INT",
                link: null,
                widget: {
                  name: "image_gen_height",
                },
                label: "高度",
              },
            ],
            outputs: [
              {
                name: "RESOLUTION (INT)",
                type: "INT",
                links: [],
                shape: 3,
                label: "分辨率(整数)",
                slot_index: 0,
              },
            ],
          };
          wk["last_node_id"] += 2;
          wk["nodes"].push(gen_res, pixel_perfect);
          this.make_link(wk, load_image_cn, 0, gen_res, 0);
          this.make_link(wk, load_image_cn, 0, pixel_perfect, 0);
          this.make_link(wk, gen_res, 0, pixel_perfect, 1);
          this.make_link(wk, gen_res, 1, pixel_perfect, 2);
          this.make_link(wk, pixel_perfect, 0, aux_preprocessor, 1);
        }
        if (out_p["type"] === "Efficient Loader") {
          this.make_link(wk, out_p, 1, apply_controlnet, 0);
          this.make_link(wk, out_n, 2, apply_controlnet, 1);
        } else if (out_p["type"] === "CLIPTextEncode") {
          this.make_link(wk, out_p, 0, apply_controlnet, 0);
          this.make_link(wk, out_n, 0, apply_controlnet, 1);
        } else if (out_p["type"] === "ControlNetApplyAdvanced") {
          this.make_link(wk, out_p, 0, apply_controlnet, 0);
          this.make_link(wk, out_n, 1, apply_controlnet, 1);
        }
        out_p = apply_controlnet;
        out_n = apply_controlnet;
        this.make_link(wk, apply_controlnet, 0, ksampler, 1);
        this.make_link(wk, apply_controlnet, 1, ksampler, 2);
        var follow_nodes = [ksampler];
        this.find_following_nodes(wk, ksampler, follow_nodes);
        this.apply_nodes_offset(follow_nodes, [offset, 0]);
      }
    }
    _ti_hashes()
    {
        var th = this.text.match(/TI hashes: (".*?"),/s);
        if (th === null) return;
        this.params["TI hashes"] = th[1].trim();
        this.text = this.text.replace(th[0], "").trim();
    }
    _tiled_diffusion()
    {
        var td = this.text.match(/Tiled Diffusion: ({.*?}),/s);
        if (td === null) return;
        this.params["Tiled Diffusion"] = td[1].trim();
        this.text = this.text.replace(td[0], "").trim();
    }
    _adetailer(){
        /*
            "ADetailer model": "face_yolov8n.pt",
            "ADetailer prompt": "\"black eyes, black hair, \"",
            "ADetailer confidence": "0.3",
            "ADetailer dilate erode": "4",
            "ADetailer mask blur": "4",
            "ADetailer denoising strength": "0.4",
            "ADetailer inpaint only masked": "True",
            "ADetailer inpaint padding": "32",
            "ADetailer version": "24.5.1",
         */
        var ad_p =  this.text.match(/ADetailer prompt: (".*?"),/s);
        if (ad_p !== null)
        {
            this.params["ADetailer prompt"] = ad_p[1].trim();
            this.text = this.text.replace(ad_p[0], "").trim();
        }
        var ads = this.text.matchAll(/(ADetailer .*?): (.*?),/gs);
        if (ads === null) return;
        for(const ad of ads)
        {
            this.params[ad[1]] = ad[2];
            this.text = this.text.replace(ad[0], "");
        }
    }
    _version(){
        var v = this.text.match(/Version: (.*?)(?:.\s|$)/s);
        if (v === null) return;
        this.params["Version"] = v[1].trim();
        this.text = this.text.replace(v[0], "").trim();
    }
    _base(){
        /*
            "Steps": "8",
            "Sampler": "DPM++ 2M Karras",
            "CFG scale": "2",
            "Seed": "3627297328",
            "Size": "768x1024",
            "Model hash": "bbd321d4a3",
            "Model": "raemuXL_v35Lightning",
            "Denoising strength": "0.5",
            "Clip skip": "2",
            "VAE": "xxx",
            "VAE hash"

            "Hires upscale": "2",
            "Hires steps": "4",
            "Hires upscaler": "ESRGAN_4x",
            "Downcast alphas_cumprod": "True",
            "Version": "1.8.0-RC"
         */
        var step = this.text.match(/Steps: (.*?),/s);
        if (step !== null)
        {
            this.params["Steps"] = step[1].trim();
            this.text = this.text.replace(step[0], "").trim();
        }
        var sampler = this.text.match(/Sampler: (.*?),/s);
        if (sampler !== null)
        {
            this.params["Sampler"] = sampler[1].trim();
            this.text = this.text.replace(sampler[0], "").trim();
        }
        var scheduler = this.text.match(/Schedule type: (.*?),/s);
        if (scheduler !== null)
        {
            this.params["Schedule type"] = scheduler[1].trim();
            this.text = this.text.replace(scheduler[0], "").trim();
        }
        var cfg = this.text.match(/CFG scale: (.*?),/s);
        if (cfg !== null)
        {
            this.params["CFG scale"] = cfg[1].trim();
            this.text = this.text.replace(cfg[0], "").trim();
        }
        var seed = this.text.match(/Seed: (.*?),/s);
        if (seed !== null)
        {
            this.params["Seed"] = seed[1].trim();
            this.text = this.text.replace(seed[0], "").trim();
        }
        var size = this.text.match(/Size: (.*?),/s);
        if (size !== null)
        {
            this.params["Size"] = size[1].trim();
            this.text = this.text.replace(size[0], "").trim();
        }
        var model_hash = this.text.match(/Model hash: (.*?),/s);
        if (model_hash !== null)
        {
            this.params["Model hash"] = model_hash[1].trim();
            this.text = this.text.replace(model_hash[0], "").trim();
        }
        var model = this.text.match(/Model: (.*?),/s);
        if (model !== null)
        {
            this.params["Model"] = model[1].trim();
            this.text = this.text.replace(model[0], "").trim();
        }
        var denoising = this.text.match(/Denoising strength: (.*?),/s);
        if (denoising !== null)
        {
            this.params["Denoising strength"] = denoising[1].trim();
            this.text = this.text.replace(denoising[0], "").trim();
        }
        var clip_skip = this.text.match(/Clip skip: (.*?),/s);
        if (clip_skip !== null)
        {
            this.params["Clip skip"] = clip_skip[1].trim();
            this.text = this.text.replace(clip_skip[0], "").trim();
        }
        var vae = this.text.match(/VAE: (.*?),/s);
        if (vae !== null)
        {
            this.params["VAE"] = vae[1].trim();
            this.text = this.text.replace(vae[0], "").trim();
        }
        var vae_hash = this.text.match(/VAE hash: (.*?),/s);
        if (vae_hash !== null)
        {
            this.params["VAE hash"] = vae_hash[1].trim();
            this.text = this.text.replace(vae_hash[0], "").trim();
        }
        // var nagative_prompt = text.match(/^.*?Negative prompt: (.*?),\s/s)[1];
        // text = text.split(nagative_prompt)[1];
        // key: value, key: value,... key: value

        // var parts = this.text.split(": ");
        // var keys = [];
        // for (var i = 0; i < parts.length - 1; i++) {
        //     var part = parts[i];
        //     var sep_i = part.lastIndexOf(",");
        //     keys.push(part.slice(sep_i + 1).trim());
        // }
        // var values = [];
        // for (var i = 1; i < parts.length; i++) {
        //   if (part.includes(",") == false) {
        //     values.push(part.trim());
        //   } else {
        //     var part = parts[i];
        //     var sep_i = part.lastIndexOf(",");
        //     values.push(part.slice(0, sep_i).trim());
        //   }
        // }
        // this.text = this.text[0] == "," ? this.text.slice(1).trim() : this.text.trim();
        // // (.+?): (.+?)(?:,\s|$)
        // for (var i = 0; i < keys.length; i++) {
        //     this.params[keys[i]] = values[i];
        // }
    }
    test(){
        var in_t0  = `
masterpiece,best quality,1girl,
BREAK thighhighs,
BREAK (colorful spot black:1.5),color gradient,
BREAK multicolored background,
Negative prompt: nsfw,nipples,navel,cameltoe,lowres,bad anatomy,bad hands,text,error,missing fingers,extra digit,fewer digits,cropped,worst quality,low quality,normal quality,jpeg artifacts,signature,watermark,username,blurry,
Steps: 8, Sampler: DPM++ 2M Karras, CFG scale: 2, Seed: 3627297328, Size: 768x1024, Model hash: bbd321d4a3, Model: raemuXL_v35Lightning, Denoising strength: 0.5, Clip skip: 2, ADetailer model: face_yolov8n.pt, ADetailer prompt: "black eyes, black hair, ", ADetailer confidence: 0.3, ADetailer dilate erode: 4, ADetailer mask blur: 4, ADetailer denoising strength: 0.4, ADetailer inpaint only masked: True, ADetailer inpaint padding: 32, ADetailer version: 24.5.1, Hires upscale: 2, Hires steps: 4, Hires upscaler: ESRGAN_4x, Downcast alphas_cumprod: True, Version: 1.8.0-RC
        `;
        var out_t0 = {
            "Positive prompt": `masterpiece,best quality,1girl,
BREAK thighhighs,
BREAK (colorful spot black:1.5),color gradient,
BREAK multicolored background`.trim(),
            "Negative prompt": "nsfw,nipples,navel,cameltoe,lowres,bad anatomy,bad hands,text,error,missing fingers,extra digit,fewer digits,cropped,worst quality,low quality,normal quality,jpeg artifacts,signature,watermark,username,blurry",
            "Steps": "8",
            "Sampler": "DPM++ 2M Karras",
            "CFG scale": "2",
            "Seed": "3627297328",
            "Size": "768x1024",
            "Model hash": "bbd321d4a3",
            "Model": "raemuXL_v35Lightning",
            "Denoising strength": "0.5",
            "Clip skip": "2",
            "ADetailer model": "face_yolov8n.pt",
            "ADetailer prompt": "\"black eyes, black hair, \"",
            "ADetailer confidence": "0.3",
            "ADetailer dilate erode": "4",
            "ADetailer mask blur": "4",
            "ADetailer denoising strength": "0.4",
            "ADetailer inpaint only masked": "True",
            "ADetailer inpaint padding": "32",
            "ADetailer version": "24.5.1",
            // "Hires upscale": "2",
            // "Hires steps": "4",
            // "Hires upscaler": "ESRGAN_4x",
            // "Downcast alphas_cumprod": "True",
            "Version": "1.8.0-RC"
        };
        console.assert(deepEqual(this._parse(in_t0), out_t0), "Test 0 failed");
        var in_t1 = `
masterpiece,ultra high quality,highest quality,super fine,1girl,solo,(black background:1.3),(silhouette:1.1),sparkle,looking at viewer,upper body,simple background,glowing,(dim lighting:1.2),crystal clear,colorful clothes,
Negative prompt: Easy Negative,bad handv4,ng_deepnegative_v1_75t,(worst quality:2),(low quality:2),(normal quality:2),lowres,((monochrome)),((grayscale)),bad anatomy,DeepNegative,skin spots,acnes,skin blemishes,(fat:1.2),facing away,looking away,tilted head,lowres,bad anatomy,bad hands,missing fingers,extra digit,fewer digits,bad feet,poorly drawn hands,poorly drawn face,mutation,deformed,extra fingers,extra limbs,extra arms,extra legs,malformed limbs,fused fingers,too many fingers,long neck,cross-eyed,mutated hands,polar lowres,bad body,bad proportions,gross proportions,missing arms,missing legs,extra digit,extra arms,extra leg,extra foot,teethcroppe,signature,watermark,username,blurry,cropped,jpeg artifacts,text,Lower body exposure,
Steps: 30, Sampler: UniPC, Schedule type: Karras, CFG scale: 7, Seed: 3620085674, Size: 1024x1536, Model hash: 3d1b3c42ec, Model: AWPainting_v1.2, ControlNet 0: "Module: tile_resample, Model: control_v11f1e_sd15_tile_fp16 [3b860298], Weight: 0.6, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 1.0, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced", TI hashes: "ng_deepnegative_v1_75t: 54e7e4826d53", Pad conds: True, Version: v1.9.4
        `;
        var out_t1 = {
            "Positive prompt": `masterpiece,ultra high quality,highest quality,super fine,1girl,solo,(black background:1.3),(silhouette:1.1),sparkle,looking at viewer,upper body,simple background,glowing,(dim lighting:1.2),crystal clear,colorful clothes`.trim(),
            "Negative prompt": "Easy Negative,bad handv4,ng_deepnegative_v1_75t,(worst quality:2),(low quality:2),(normal quality:2),lowres,((monochrome)),((grayscale)),bad anatomy,DeepNegative,skin spots,acnes,skin blemishes,(fat:1.2),facing away,looking away,tilted head,lowres,bad anatomy,bad hands,missing fingers,extra digit,fewer digits,bad feet,poorly drawn hands,poorly drawn face,mutation,deformed,extra fingers,extra limbs,extra arms,extra legs,malformed limbs,fused fingers,too many fingers,long neck,cross-eyed,mutated hands,polar lowres,bad body,bad proportions,gross proportions,missing arms,missing legs,extra digit,extra arms,extra leg,extra foot,teethcroppe,signature,watermark,username,blurry,cropped,jpeg artifacts,text,Lower body exposure",
            "Steps": "30",
            "Sampler": "UniPC",
            "Schedule type": "Karras",
            "CFG scale": "7",
            "Seed": "3620085674",
            "Size": "1024x1536",
            "Model hash": "3d1b3c42ec",
            "Model": "AWPainting_v1.2",
            "ControlNet 0": "Module: tile_resample, Model: control_v11f1e_sd15_tile_fp16 [3b860298], Weight: 0.6, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 1.0, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced",
            "TI hashes": "\"ng_deepnegative_v1_75t: 54e7e4826d53\"",
            // "Pad conds": "True",
            "Version": "v1.9.4"
        };
        console.assert(deepEqual(this._parse(in_t1), out_t1), "Test 1 failed");
        var in_t2 = `
parameters(official art:1.2),(colorful:1.1),(masterpiece:1.2),best quality,masterpiece,highres,original,extremely detailed wallpaper,1girl,solo,very long hair,(loli:1.3),vibrant color palette,dazzling hues,kaleidoscopic patterns,enchanting young maiden,radiant beauty,chromatic harmony,iridescent hair,sparkling eyes,lush landscapes,vivid blossoms,mesmerizing sunsets,brilliant rainbows,prismatic reflections,whimsical attire,captivating accessories,stunning chromatic display,artful composition,picturesque backdrop,breathtaking scenery,visual symphony,spellbinding chromatic enchantment,
(shiny:1.2),(Oil highlights:1.2),[wet with oil:0.7],(shiny:1.2),[wet with oil:0.5],
Negative prompt: (worst quality, low quality, blurry:1.5),(bad hands:1.4),watermark,(greyscale:0.88),multiple limbs,(deformed fingers, bad fingers:1.2),(ugly:1.3),monochrome,horror,geometry,bad anatomy,bad limbs,(Blurry pupil),(bad shading),error,bad composition,Extra fingers,NSFW,badhandv4,charturnerv2,corneo_dva,EasyNegative,EasyNegativeV2,ng_deepnegative_v1_75t,
Steps: 25, Sampler: Euler, Schedule type: Automatic, CFG scale: 7, Seed: 848680687, Size: 1024x1536, Model hash: 099e07547a, Model: Dark Sushi Mix 大颗寿司Mix_BrighterPruned, VAE hash: f921fb3f29, VAE: kl-f8-anime2.ckpt, Denoising strength: 0.75, Clip skip: 2, Tiled Diffusion: {"Method": "MultiDiffusion", "Tile tile width": 96, "Tile tile height": 96, "Tile Overlap": 48, "Tile batch size": 4, "Keep input size": true, "NoiseInv": true, "NoiseInv Steps": 10, "NoiseInv Retouch": 1, "NoiseInv Renoise strength": 0.5, "NoiseInv Kernel size": 64}, ControlNet 0: "Module: tile_resample, Model: control_v11f1e_sd15_tile_fp16 [3b860298], Weight: 0.5, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 1.0, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced", Pad conds: True, Version: v1.9.4
        `;
        var out_t2 = {
            "Positive prompt": `
(official art:1.2),(colorful:1.1),(masterpiece:1.2),best quality,masterpiece,highres,original,extremely detailed wallpaper,1girl,solo,very long hair,(loli:1.3),vibrant color palette,dazzling hues,kaleidoscopic patterns,enchanting young maiden,radiant beauty,chromatic harmony,iridescent hair,sparkling eyes,lush landscapes,vivid blossoms,mesmerizing sunsets,brilliant rainbows,prismatic reflections,whimsical attire,captivating accessories,stunning chromatic display,artful composition,picturesque backdrop,breathtaking scenery,visual symphony,spellbinding chromatic enchantment,
(shiny:1.2),(Oil highlights:1.2),[wet with oil:0.7],(shiny:1.2),[wet with oil:0.5]`.trim(),
            "Negative prompt": "(worst quality, low quality, blurry:1.5),(bad hands:1.4),watermark,(greyscale:0.88),multiple limbs,(deformed fingers, bad fingers:1.2),(ugly:1.3),monochrome,horror,geometry,bad anatomy,bad limbs,(Blurry pupil),(bad shading),error,bad composition,Extra fingers,NSFW,badhandv4,charturnerv2,corneo_dva,EasyNegative,EasyNegativeV2,ng_deepnegative_v1_75t",
            "Steps": "25",
            "Sampler": "Euler",
            "Schedule type": "Automatic",
            "CFG scale": "7",
            "Seed": "848680687",
            "Size": "1024x1536",
            "Model hash": "099e07547a",
            "Model": "Dark Sushi Mix 大颗寿司Mix_BrighterPruned",
            "VAE hash": "f921fb3f29",
            "VAE": "kl-f8-anime2.ckpt",
            "Denoising strength": "0.75",
            "Clip skip": "2",
            "Tiled Diffusion": `{"Method": "MultiDiffusion", "Tile tile width": 96, "Tile tile height": 96, "Tile Overlap": 48, "Tile batch size": 4, "Keep input size": true, "NoiseInv": true, "NoiseInv Steps": 10, "NoiseInv Retouch": 1, "NoiseInv Renoise strength": 0.5, "NoiseInv Kernel size": 64}`,
            "ControlNet 0": "Module: tile_resample, Model: control_v11f1e_sd15_tile_fp16 [3b860298], Weight: 0.5, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 1.0, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced",
            // "Pad conds": "True",
            "Version": "v1.9.4",
        };
        console.assert(deepEqual(this._parse(in_t2), out_t2), "Test 2 failed");
        var in_t3 = `
masterpiece, best quality, girl,woman,female, short hair, light smile, closed_eyes, cat_ears, overskirt,white dress,frills, pale blue Clothes,tiara
Negative prompt: easynegative, ng_deepnegative_v1_75t, By bad artist -neg, verybadimagenegative_v1.3
Steps: 20, Sampler: Euler a, CFG scale: 7, Seed: 3850677924, Size: 768x1024, Model hash: 19dbfda152, Model: 二次元_mixProV45Colorbox_v45, Clip skip: 2, ENSD: 31337
        `;
        var out_t3 = {
          "Positive prompt": `
masterpiece, best quality, girl,woman,female, short hair, light smile, closed_eyes, cat_ears, overskirt,white dress,frills, pale blue Clothes,tiara`.trim(),
          "Negative prompt": "easynegative, ng_deepnegative_v1_75t, By bad artist -neg, verybadimagenegative_v1.3",
          "Steps": "20",
          "Sampler": "Euler a",
          "CFG scale": "7",
          "Seed": "3850677924",
          "Size": "768x1024",
          "Model hash": "19dbfda152",
          "Model": "二次元_mixProV45Colorbox_v45",
          "Clip skip": "2",
        };
        console.assert(deepEqual(this._parse(in_t3), out_t3), "Test 3 failed");
        var in_t4 = `
masterpiece, best quality, 1girl, solo, voxel art,
gazebo, white girl,
rust hair, ochre eyes,
long hair, folded ponytail,
evening gown, trim dress,
ribbon, Gift Hat Hair Band , Opera-length necklaces, Arm harnesses,
classic, medieval, noble
Negative prompt: lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, badhandv4, easynegative, ng_deepnegative_v1_75t, verybadimagenegative_v1.3
Steps: 20, Sampler: Euler a, CFG scale: 7, Seed: 1825312441, Size: 640x960, Model hash: 149fe7d36c, Model: 二次元_meinaalter_v1, ENSD: 31337, Wildcard prompt: "masterpiece, best quality, 1girl, solo, voxel art,
__scene-location__, white girl,
__color__ hair, __color__ eyes,
__character-hair-Size__, __character-hair-Style__,
__character-clothing-Dress__, trim dress,
ribbon, __character-accessories-Hair__, __character-accessories-Neck__, __character-accessories-Arm__,
classic, medieval, noble"`;
        var out_t4 = {
          "Positive prompt": `
masterpiece, best quality, 1girl, solo, voxel art,
gazebo, white girl,
rust hair, ochre eyes,
long hair, folded ponytail,
evening gown, trim dress,
ribbon, Gift Hat Hair Band , Opera-length necklaces, Arm harnesses,
classic, medieval, noble`.trim(),
          "Negative prompt": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, badhandv4, easynegative, ng_deepnegative_v1_75t, verybadimagenegative_v1.3",
          "Steps": "20",
          "Sampler": "Euler a",
          "CFG scale": "7",
          "Seed": "1825312441",
          "Size": "640x960",
          "Model hash": "149fe7d36c",
          "Model": "二次元_meinaalter_v1",
        };
        console.assert(deepEqual(this._parse(in_t4), out_t4), "Test 4 failed");
    }
    base_workflow(){
        var wk = {
            "last_node_id": 11,
            "last_link_id": 13,
            "nodes": [
              {
                "id": 7,
                "type": "CLIPTextEncode",
                "pos": [
                  413,
                  389
                ],
                "size": {
                  "0": 425.27801513671875,
                  "1": 180.6060791015625
                },
                "mode": 0,
                "inputs": [
                  {
                    "name": "clip",
                    "type": "CLIP",
                    "link": 12,
                    "label": "CLIP"
                  }
                ],
                "outputs": [
                  {
                    "name": "CONDITIONING",
                    "type": "CONDITIONING",
                    "links": [
                      6
                    ],
                    "slot_index": 0,
                    "label": "条件"
                  }
                ],
                "properties": {
                  "Node name for S&R": "CLIPTextEncode"
                },
                "widgets_values": [
                  "text, watermark"
                ]
              },
              {
                "id": 6,
                "type": "CLIPTextEncode",
                "pos": [
                  415,
                  186
                ],
                "size": {
                  "0": 422.84503173828125,
                  "1": 164.31304931640625
                },
                "mode": 0,
                "inputs": [
                  {
                    "name": "clip",
                    "type": "CLIP",
                    "link": 11,
                    "label": "CLIP"
                  }
                ],
                "outputs": [
                  {
                    "name": "CONDITIONING",
                    "type": "CONDITIONING",
                    "links": [
                      4
                    ],
                    "slot_index": 0,
                    "label": "条件"
                  }
                ],
                "properties": {
                  "Node name for S&R": "CLIPTextEncode"
                },
                "widgets_values": [
                  "beautiful scenery nature glass bottle landscape, , purple galaxy bottle,"
                ]
              },
              {
                "id": 5,
                "type": "EmptyLatentImage",
                "pos": [
                  473,
                  609
                ],
                "size": {
                  "0": 315,
                  "1": 106
                },
                "mode": 0,
                "outputs": [
                  {
                    "name": "LATENT",
                    "type": "LATENT",
                    "links": [
                      2
                    ],
                    "slot_index": 0,
                    "label": "Latent"
                  }
                ],
                "properties": {
                  "Node name for S&R": "EmptyLatentImage"
                },
                "widgets_values": [
                  512,
                  512,
                  1
                ]
              },
              {
                "id": 3,
                "type": "KSampler",
                "pos": [
                  863,
                  186
                ],
                "size": {
                  "0": 315,
                  "1": 262
                },
                "mode": 0,
                "inputs": [
                  {
                    "name": "model",
                    "type": "MODEL",
                    "link": 1,
                    "label": "模型"
                  },
                  {
                    "name": "positive",
                    "type": "CONDITIONING",
                    "link": 4,
                    "label": "正面条件"
                  },
                  {
                    "name": "negative",
                    "type": "CONDITIONING",
                    "link": 6,
                    "label": "负面条件"
                  },
                  {
                    "name": "latent_image",
                    "type": "LATENT",
                    "link": 2,
                    "label": "Latent"
                  }
                ],
                "outputs": [
                  {
                    "name": "LATENT",
                    "type": "LATENT",
                    "links": [
                      7
                    ],
                    "slot_index": 0,
                    "label": "Latent"
                  }
                ],
                "properties": {
                  "Node name for S&R": "KSampler"
                },
                "widgets_values": [
                  156680208700286,
                  "fixed",
                  20,
                  8,
                  "euler",
                  "normal",
                  1
                ]
              },
              {
                "id": 8,
                "type": "VAEDecode",
                "pos": [
                  1209,
                  188
                ],
                "size": {
                  "0": 210,
                  "1": 46
                },
                "mode": 0,
                "inputs": [
                  {
                    "name": "samples",
                    "type": "LATENT",
                    "link": 7,
                    "label": "Latent"
                  },
                  {
                    "name": "vae",
                    "type": "VAE",
                    "link": 8,
                    "label": "VAE"
                  }
                ],
                "outputs": [
                  {
                    "name": "IMAGE",
                    "type": "IMAGE",
                    "links": [
                      9,
                      13
                    ],
                    "slot_index": 0,
                    "label": "图像"
                  }
                ],
                "properties": {
                  "Node name for S&R": "VAEDecode"
                }
              },
              {
                "id": 9,
                "type": "SaveImage",
                "pos": [
                  1451,
                  189
                ],
                "size": {
                  "0": 210,
                  "1": 58
                },
                "mode": 0,
                "inputs": [
                  {
                    "name": "images",
                    "type": "IMAGE",
                    "link": 9,
                    "label": "图像"
                  }
                ],
                "properties": {},
                "widgets_values": [
                  "ComfyUI"
                ]
              },
              {
                "id": 4,
                "type": "CheckpointLoaderSimple",
                "pos": [
                  -348,
                  179
                ],
                "size": {
                  "0": 315,
                  "1": 98
                },
                "mode": 0,
                "outputs": [
                  {
                    "name": "MODEL",
                    "type": "MODEL",
                    "links": [
                      1
                    ],
                    "slot_index": 0,
                    "label": "模型"
                  },
                  {
                    "name": "CLIP",
                    "type": "CLIP",
                    "links": [
                      10
                    ],
                    "slot_index": 1,
                    "label": "CLIP"
                  },
                  {
                    "name": "VAE",
                    "type": "VAE",
                    "links": [
                      8
                    ],
                    "slot_index": 2,
                    "label": "VAE"
                  }
                ],
                "properties": {
                  "Node name for S&R": "CheckpointLoaderSimple"
                },
                "widgets_values": [
                  "mixProV4_v4.safetensors"
                ]
              },
              {
                "id": 10,
                "type": "CLIPSetLastLayer",
                "pos": [
                  17,
                  181
                ],
                "size": {
                  "0": 315,
                  "1": 58
                },
                "mode": 0,
                "inputs": [
                  {
                    "name": "clip",
                    "type": "CLIP",
                    "link": 10,
                    "label": "CLIP"
                  }
                ],
                "outputs": [
                  {
                    "name": "CLIP",
                    "type": "CLIP",
                    "links": [
                      11,
                      12
                    ],
                    "shape": 3,
                    "label": "CLIP",
                    "slot_index": 0
                  }
                ],
                "properties": {
                  "Node name for S&R": "CLIPSetLastLayer"
                },
                "widgets_values": [
                  -1
                ]
              },
              {
                  "id": 11,
                  "type": "PreviewImage",
                  "pos": [
                      1450,
                      380
                  ],
                  "size": {
                      "0": 210,
                      "1": 30
                  },
                  "mode": 0,
                  "inputs": [
                      {
                          "name": "images",
                          "type": "IMAGE",
                          "link": 13,
                          "label": "图像"
                      }
                  ],
                  "properties": {
                      "Node name for S&R": "PreviewImage"
                  }
              },
            ],
            "links": [
              [
                1,
                4,
                0,
                3,
                0,
                "MODEL"
              ],
              [
                2,
                5,
                0,
                3,
                3,
                "LATENT"
              ],
              [
                4,
                6,
                0,
                3,
                1,
                "CONDITIONING"
              ],
              [
                6,
                7,
                0,
                3,
                2,
                "CONDITIONING"
              ],
              [
                7,
                3,
                0,
                8,
                0,
                "LATENT"
              ],
              [
                8,
                4,
                2,
                8,
                1,
                "VAE"
              ],
              [
                9,
                8,
                0,
                9,
                0,
                "IMAGE"
              ],
              [
                10,
                4,
                1,
                10,
                0,
                "CLIP"
              ],
              [
                11,
                10,
                0,
                6,
                0,
                "CLIP"
              ],
              [
                12,
                10,
                0,
                7,
                0,
                "CLIP"
              ],
              [
                  13,
                  8,
                  0,
                  11,
                  0,
                  "IMAGE"
              ],
            ],
            "groups": [],
            "config": {},
            "extra": {
              "ds": {
                "scale": 1.2100000000000004,
                "offset": [
                  253.97393794242356,
                  53.4865032972739
                ]
              }
            },
            "version": 0.4
          };
          return wk;
    }
    efficient_workflow(){
        var wk = {
          "last_node_id": 5,
          "last_link_id": 9,
          "nodes": [
            {
              "id": 4,
              "type": "SaveImage",
              "pos": [
                1040,
                250
              ],
              "size": {
                "0": 320,
                "1": 60
              },
              "mode": 0,
              "inputs": [
                {
                  "name": "images",
                  "type": "IMAGE",
                  "link": 8,
                  "label": "图像"
                }
              ],
              "properties": {
                "Node name for S&R": "SaveImage"
              },
              "widgets_values": [
                "ComfyUI"
              ]
            },
            {
              "id": 2,
              "type": "Efficient Loader",
              "pos": [
                210,
                250
              ],
              "size": {
                "0": 400,
                "1": 462
              },
              "mode": 0,
              "inputs": [
                {
                  "name": "lora_stack",
                  "type": "LORA_STACK",
                  "link": null,
                  "label": "LoRA堆"
                },
                {
                  "name": "cnet_stack",
                  "type": "CONTROL_NET_STACK",
                  "link": null,
                  "label": "ControlNet堆"
                }
              ],
              "outputs": [
                {
                  "name": "MODEL",
                  "type": "MODEL",
                  "links": [
                    7
                  ],
                  "shape": 3,
                  "label": "模型",
                  "slot_index": 0
                },
                {
                  "name": "CONDITIONING+",
                  "type": "CONDITIONING",
                  "links": [
                    3
                  ],
                  "shape": 3,
                  "label": "正面条件",
                  "slot_index": 1
                },
                {
                  "name": "CONDITIONING-",
                  "type": "CONDITIONING",
                  "links": [
                    4
                  ],
                  "shape": 3,
                  "label": "负面条件",
                  "slot_index": 2
                },
                {
                  "name": "LATENT",
                  "type": "LATENT",
                  "links": [
                    5
                  ],
                  "shape": 3,
                  "label": "Latent",
                  "slot_index": 3
                },
                {
                  "name": "VAE",
                  "type": "VAE",
                  "links": [
                    6
                  ],
                  "shape": 3,
                  "label": "VAE",
                  "slot_index": 4
                },
                {
                  "name": "CLIP",
                  "type": "CLIP",
                  "links": null,
                  "shape": 3,
                  "label": "CLIP"
                },
                {
                  "name": "DEPENDENCIES",
                  "type": "DEPENDENCIES",
                  "links": null,
                  "shape": 3,
                  "label": "依赖"
                }
              ],
              "properties": {
                "Node name for S&R": "Efficient Loader"
              },
              "widgets_values": [
                "animagineXLV3_v30.safetensors",
                "Baked VAE",
                -1,
                "None",
                1,
                1,
                "CLIP_POSITIVE",
                "CLIP_NEGATIVE",
                "none",
                "A1111",
                512,
                512,
                1
              ],
              "bgcolor": "#335555",
              "shape": 1
            },
            {
              "id": 1,
              "type": "KSampler (Efficient)",
              "pos": [
                660,
                250
              ],
              "size": {
                "0": 330,
                "1": 370
              },
              "mode": 0,
              "inputs": [
                {
                  "name": "model",
                  "type": "MODEL",
                  "link": 7,
                  "label": "模型",
                  "slot_index": 0
                },
                {
                  "name": "positive",
                  "type": "CONDITIONING",
                  "link": 3,
                  "label": "正面条件"
                },
                {
                  "name": "negative",
                  "type": "CONDITIONING",
                  "link": 4,
                  "label": "负面条件"
                },
                {
                  "name": "latent_image",
                  "type": "LATENT",
                  "link": 5,
                  "label": "Latent"
                },
                {
                  "name": "optional_vae",
                  "type": "VAE",
                  "link": 6,
                  "label": "VAE(可选)"
                },
                {
                  "name": "script",
                  "type": "SCRIPT",
                  "link": null,
                  "label": "脚本"
                }
              ],
              "outputs": [
                {
                  "name": "MODEL",
                  "type": "MODEL",
                  "links": null,
                  "shape": 3,
                  "label": "模型"
                },
                {
                  "name": "CONDITIONING+",
                  "type": "CONDITIONING",
                  "links": null,
                  "shape": 3,
                  "label": "正面条件"
                },
                {
                  "name": "CONDITIONING-",
                  "type": "CONDITIONING",
                  "links": null,
                  "shape": 3,
                  "label": "负面条件"
                },
                {
                  "name": "LATENT",
                  "type": "LATENT",
                  "links": null,
                  "shape": 3,
                  "label": "Latent"
                },
                {
                  "name": "VAE",
                  "type": "VAE",
                  "links": null,
                  "shape": 3,
                  "label": "VAE"
                },
                {
                  "name": "IMAGE",
                  "type": "IMAGE",
                  "links": [
                    8,
                    9
                  ],
                  "shape": 3,
                  "label": "图像",
                  "slot_index": 5
                }
              ],
              "properties": {
                "Node name for S&R": "KSampler (Efficient)"
              },
              "widgets_values": [
                800315283332510,
                "fixed",
                20,
                7,
                "euler",
                "normal",
                1,
                "auto",
                "true"
              ],
              "bgcolor": "#333355",
              "shape": 1
            },
            {
              "id": 5,
              "type": "PreviewImage",
              "pos": [
                1050,
                520
              ],
              "size": {
                "0": 210,
                "1": 30
              },
              "mode": 0,
              "inputs": [
                {
                  "name": "images",
                  "type": "IMAGE",
                  "link": 9,
                  "label": "图像"
                }
              ],
              "properties": {
                "Node name for S&R": "PreviewImage"
              }
            }
          ],
          "links": [
            [
              3,
              2,
              1,
              1,
              1,
              "CONDITIONING"
            ],
            [
              4,
              2,
              2,
              1,
              2,
              "CONDITIONING"
            ],
            [
              5,
              2,
              3,
              1,
              3,
              "LATENT"
            ],
            [
              6,
              2,
              4,
              1,
              4,
              "VAE"
            ],
            [
              7,
              2,
              0,
              1,
              0,
              "MODEL"
            ],
            [
              8,
              1,
              5,
              4,
              0,
              "IMAGE"
            ],
            [
              9,
              1,
              5,
              5,
              0,
              "IMAGE"
            ]
          ],
          "groups": [],
          "config": {},
          "extra": {
            "ds": {
              "scale": 1.2100000000000006,
              "offset": [
                -639.1956340693308,
                -38.20042379820701
              ]
            }
          },
          "version": 0.4
        };
        return wk;
    }
}

function isVersionGreater(version1, version2) {
  const v1 = version1.split(".").map(Number);
  const v2 = version2.split(".").map(Number);
  const maxLength = Math.max(v1.length, v2.length);
  for (let i = 0; i < maxLength; i++) {
    const num1 = v1[i] || 0;
    const num2 = v2[i] || 0;
    if (num1 > num2) return true;
    if (num1 < num2) return false;
  }
  return false;
}

const ext = {
    name: "AIGODLIKE.CUP-CLIPBOARD",
    async init(app) {
    },
    async setup(app) {
        // 添加按钮
        var btnCopy = $el("button", {
            id: "clipbord-copy-button",
            textContent: "CopyTree",
            style: {
                "font-size": "16px",
            },
            onclick: () => {
                var data = window.app.graph.serialize();
                navigator.clipboard.writeText(JSON.stringify(data));
            },
        });
        var btnPaste = $el("button", {
            id: "clipbord-paste-button",
            textContent: "PasteTree",
            style: {
                "font-size": "16px",
            },
            onclick: () => {
                navigator.clipboard.readText().then(ext.paste);
            },
        });
        app.ui.menuContainer.appendChild(
            $el("div.comfy-menu-btns", [btnCopy, btnPaste])
        );
        if(isVersionGreater(window.__COMFYUI_FRONTEND_VERSION__, "1.2"))
        {
          var ComfyButtonGroup = window.comfyAPI.buttonGroup.ComfyButtonGroup;
          var ComfyButton = window.comfyAPI.button.ComfyButton;

          var btnCopy = new ComfyButton({
            icon: "content-copy",
            action: () => {
              var data = window.app.graph.serialize();
              navigator.clipboard.writeText(JSON.stringify(data));
            },
            tooltip: "CopyTree",
            content: "",
            classList: "clipbord-copy-button comfyui-button"
          });
          var btnPaste = new ComfyButton({
            icon: "content-paste",
            action: () => {
              navigator.clipboard.readText().then(ext.paste);
            },
            tooltip: "PasteTree",
            content: "",
            classList: "clipbord-paste-button comfyui-button"
          });
          var group = new ComfyButtonGroup(btnCopy.element, btnPaste.element);
          app.menu?.settingsGroup.element.before(group.element);
        }
    },
    paste(text){
        var webui_parser = new WebUIToComfyUI(text);
        if (webui_parser.is_webui_format())
        {
            webui_parser.parse(text);
            text = webui_parser.to_comfyui_format();
        }
        try {
            var data = JSON.parse(text);
            if (data.hasOwnProperty("workflow"))
                data = data.workflow;
            window.app.loadGraphData(data);
        } catch (e) {
            if (e instanceof SyntaxError) {
                alert("Clipboard data is not valid.");
            } else {
                alert(e);
            }
        }
    },
};

app.registerExtension(ext);
