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
    constructor(text){
        this.text = text;
        this.params = {};
    }
    is_webui_format(){
        if (this.text.includes("Negative prompt: ") && this.text.includes("Steps:"))
            return true;
        return false;
    }
    to_comfyui_format(){
        var params = this.params;
        var wk = this.base_workflow();
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
                var rlast = sampler_name.lastIndexOf(" ");
                if (rlast != -1)
                {
                    scheduler_name = sampler_name.slice(rlast + 1);
                    sampler_name = sampler_name.slice(0, rlast);
                }
            }
            if (sampler_name in WebUIToComfyUI.SAMPLERNAME_W2C)
                ksampler["widgets_values"][4] = WebUIToComfyUI.SAMPLERNAME_W2C[sampler_name];
            if (scheduler_name in WebUIToComfyUI.SCHEDULERNAME_W2C)
                ksampler["widgets_values"][5] = WebUIToComfyUI.SCHEDULERNAME_W2C[scheduler_name];
        }
        if ("Denoising strength" in params)
            ksampler["widgets_values"][6] = params["Denoising strength"];
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
            clip_last_layer["widgets_values"][0] = params["Clip skip"];
        return JSON.stringify(wk);
    }
    parse(text){
        this.text = text ? text : this.text;
        this.test();
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
            this.params["Positive prompt"] = pp.slice(-1) == "," ? pp.slice(0, -1).trim() : pp;
            this.text = this.text.replace(pp, "").trim();
        }
        var np = this.text.match(/Negative prompt: (.*?)(?:,\n)/s);
        np = np ? np : this.text.match(/Negative prompt: (.*?)(?:,\r\n)/s);
        if(np !== null)
        {
            this.params["Negative prompt"] = np[1].trim();
            this.text = this.text.replace(np[0], "").trim();
        }
    }
    _control_net(){
        /*
Controlnet 0: "preprocessor: dw_openpose_full, model: control_v11p_sd15_openpose, weight: 1.0, starting/ending: (0.0, 1.0), resize mode: Crop and Resize, pixel_perfect: False, control mode: Balanced, preprocessor params: (1024, None, None)", 
Controlnet 1: "preprocessor: depth_leres (LeRes 深度图估算）, model: control_v11f1p_sd15_depth, weight: 0.7, starting/ending: (0.23, 0.76), resize mode: Crop and Resize, pixel_perfect: True, control mode: Balanced, preprocessor params: (1024, 0, 0)", 
ControlNet 2: "Module: tile_resample, Model: control_v11f1e_sd15_tile_fp16 [3b860298], Weight: 0.6, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 1.0, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced",
        */
        if(this.text.match(/(Control[nN]et \d+): /s) == null)
            return;
        for(const cn of this.text.matchAll(/(Control[nN]et \d+): (".*?"),/gs))
        {
            this.params[cn[1]] = cn[2];
            this.text = this.text.replace(cn[0], "");
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
            "ControlNet 0": `"Module: tile_resample, Model: control_v11f1e_sd15_tile_fp16 [3b860298], Weight: 0.6, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 1.0, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced"`,
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
parameters(official art:1.2),(colorful:1.1),(masterpiece:1.2),best quality,masterpiece,highres,original,extremely detailed wallpaper,1girl,solo,very long hair,(loli:1.3),vibrant color palette,dazzling hues,kaleidoscopic patterns,enchanting young maiden,radiant beauty,chromatic harmony,iridescent hair,sparkling eyes,lush landscapes,vivid blossoms,mesmerizing sunsets,brilliant rainbows,prismatic reflections,whimsical attire,captivating accessories,stunning chromatic display,artful composition,picturesque backdrop,breathtaking scenery,visual symphony,spellbinding chromatic enchantment,
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
            "ControlNet 0": `"Module: tile_resample, Model: control_v11f1e_sd15_tile_fp16 [3b860298], Weight: 0.5, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 1.0, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced"`,
            // "Pad conds": "True",
            "Version": "v1.9.4",
        };
        console.assert(deepEqual(this._parse(in_t2), out_t2), "Test 2 failed");
    }
    base_workflow(){
        var wk = {
            "last_node_id": 10,
            "last_link_id": 12,
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
                "flags": {},
                "order": 4,
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
                "flags": {},
                "order": 3,
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
                "flags": {},
                "order": 0,
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
                "flags": {},
                "order": 5,
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
                  "randomize",
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
                "flags": {},
                "order": 6,
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
                      9
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
                "flags": {},
                "order": 7,
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
                "flags": {},
                "order": 1,
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
                "flags": {},
                "order": 2,
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
              }
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
              ]
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
