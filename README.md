# Introduction
This is and addon for using [ComfyUI](https://github.com/comfyanonymous/ComfyUI) in Blender. To convert ComfyUI nodes into Blender nodes, you can use comfyui inside the blender without switching between softwares.
## Features

- Convert ComfyUI nodes to Blender nodes
- Edit launch arguments in n-panel/addon menu, or just link to a running comfyui process
- Special Blender nodes like camera input or compositing data
- Can draw masks with Grease pencil
- Node groups like the node group in geometry node
- Queue batch processing with mission excel
- Node tree presets and node group presets
- Model preview image on Loaders node
- Can directly input or replace the 3D models in Blender
- By using composite can output perfect controlnet image

Here are some workflow showcase:
You can find all these workflow presets in `ComfyUI-BlenderAI-node/presets/`

### Camera input
![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/f087f254-5486-4d9f-9a13-d327abed3e14)

### Camera input with roop

https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/cb96dd60-b93a-4f09-9ab6-043b66617313

### Import or replace AI generate mesh to 3D Viewport

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/92b2913f-f20b-4e6c-85b6-e9f60a7b58f1)

### Composite depth channel

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/2386dc4d-6faa-4054-83e7-93f49a27962a)

### Edit character bone with model

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/484c12bf-55b8-4baf-92df-e422fd900cbf)

# Installation

Only tested on WINDOWS 10\\11

1. **Install Blender**

Firstly, you need to install a [Blender](https://www.blender.org/download/)(Recommend Blender 3.5, 3.6.X, or previous 4.0).

![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/aacf1cfe-ae44-4930-9a93-c226a8408066)

2. **Install add-on（ComfyUI BlenderAI node）**

- Install with Blender addon

At the Blender preference menu, you can directly install an addon with select the zip file. This will automaticlly install the addon to the Blender that you are currently using.
And don't forget to enable the addon by click the cube at the tilte's left

*Note*: Some users reports that install the directyly downloaded zip file will lose preview image

![Pasted image 20240319183259](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/7772234d-6d7c-40da-9a32-ee918ca719fb)


- Install manually (recommend)

ComfyUI BlenderAI node is a standard Blender add-on. You can use git the addon to Blender's addon directory.

```
cd %USERPROFILE%\AppData\Roaming\Blender Foundation\blender\%version%\scripts\addons
git clone https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node.git --recursive
```
Then you can see the addont after refresh addon menu or reboot Blender.
And don't forget to enable the addon by click the cube at the tilte's left

# Usage

0. **Prepare a ComfyUI standard build**

You can download ComfyUI from here: [ComfyUI Release](https://github.com/comfyanonymous/ComfyUI/releases)

Or you can build one by your self as long as follow the standard path structure:

```
├── ComfyUI
│   ├── main.py
│   ...
├── python_embeded
│   ├── python.exe
│   ...
```

1. **Set the "ComfyUI Path" to your ComfyUI directory**

![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/5d081ee7-0b2a-4871-bdf9-ada05bb12831)


2. **Set the "Python Path" if you're not using the standard ComfyUI file directory**

The default (empty) path is:
```
├── ComfyUI
├── python_embeded
│   ├── python.exe  <-- Here
```

3.  **Open to ComfyUI node workspace**

Switch to the ComfyUI workspace, use the shortcut key "N" to open the panel, and click boot button launch the ComfyUI service.
Or, Switch the "Server Type" to remote server so that you can link your Blender to a running ComfyUI process
![Pasted image 20240319185542](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/e46c3a5a-ff32-4503-8228-f101c91c6664)


4. **Add nodes/presets**

Like other Blender nodes, you can use the shortcut keys "Shift+A" to bring up the creation menu. You can also click on the "Replace Node Tree" button or "Append Node Tree" button on the right to add/append a node tree.
**Image preview and input must use Blender specially designed nodes, otherwise the calculation results may not be displayed properly 
(using Blender special nodes won't affect the generation, results will be saved as ComfyUI standard data)**

![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/22c68423-07aa-4a07-93a9-9354880276e1)

## Special Nodes for Blender

### Input Image

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/9e89adcb-4574-4b93-b549-998db38cc128)

- Input image from directory
- Input image list from directory
- Input image from render
- Input image from viewport

### Mask

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/85c29090-b751-4686-b9b9-7373f7b6ffb1)

- Create mask by Grease pencil
- Create mask by object projection on camera
- Create mask by collection objects preojections

### Mat Image

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/8fff5b65-9c7f-4053-8bc6-ea16184774ad)

- Input texture from object
- Input textures from collection objects

### Save Image

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/edbc273d-40cd-482b-835f-fb8b69812684)

- Normaly save to folder
- Save to image in Blender to replace texture


### Multiline Textbox

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/bdc796c0-7dec-4c5d-922e-17860941a23e)

To make write prompt be more visually, we made a function that can show all prompts in a textbox since blender doesn't support multiline format node.
By click the button on the side of prompts, it will open a window to write prompts

## Shortcut Keys

### Link

Select a node, then hold `D` and drag cursor to another node's center, you can link all available widgets between them

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/eae1061a-c4f5-4f0c-becf-501176a7aaa2)

### Search Widgets

By press `R` when the cursor is nearby a widget, there will be a pie menu to display all nodes that has this widget

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/2dcffa51-a261-4e22-9692-00863e4faa33)

### Mask Link

Hold `F` and drag cursor to a mask node, it will automatically create a camera to genarate mask from scene

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/d97805e5-4f54-4e1a-9fe0-0b98192baab9)



## Notes
- Not every node can work perfectly in Blender, like Blender don't support any video type format
- You can enable the system console in the "Window-Toggle System Console" at the left top
- Preview images needs to have same name as the model and extension like model.ckpt.jpg

## Tested Nodes
Here are some interesting nodes we've tested on Blender

√ = works as in ComfyUI web

? = not all functions are work

× = only few or none functions are work

|Custom Node Name|Status|
|:----|:----|
|[3D-Pack](https://github.com/MrForExample/ComfyUI-3D-Pack)|√|
|[Advanced Encode](https://github.com/BlenderNeko/ComfyUI_ADV_CLIP_emb)|√|
|[Advanced ControlNet](https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet)|√|
|[AGL-ComfyUI-Translation](https://github.com/AIGODLIKE/AIGODLIKE-COMFYUI-TRANSLATION)|√|
|[AlekPet Nodes](https://github.com/AlekPet/ComfyUI_Custom_Nodes_AlekPet)|√|
|[AnimateAnyone](https://github.com/MrForExample/ComfyUI-AnimateAnyone-Evolved.git)|√|
|[AnimateDiff](https://github.com/ArtVentureX/comfyui-animatediff)|?|
|[AnimateDiff-Evolved](https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved.git)|√|
|[BiRefNet](https://github.com/viperyl/ComfyUI-BiRefNet.git)|√|
|[CLIP Seg](https://github.com/biegert/ComfyUI-CLIPSeg)|√|
|[ComfyRoll](https://github.com/RockOfFire/ComfyUI_Comfyroll_CustomNodes)|√|
|[ControlNet LLLite](https://github.com/kohya-ss/ControlNet-LLLite-ComfyUI)|√|
|[ControlNet Preprocessors](https://github.com/Fannovel16/comfy_controlnet_preprocessors)|√|
|[ControlNet Preprocessors AUX](https://github.com/Fannovel16/comfyui_controlnet_aux)|√|
|[Crystools](https://github.com/crystian/ComfyUI-Crystools.git)|√|
|[Cutoff](https://github.com/BlenderNeko/ComfyUI_Cutoff)|√|
|[Custom-Scripts](https://github.com/pythongosssss/ComfyUI-Custom-Scripts)|×|
|[cg-use-everywhere](https://github.com/chrisgoringe/cg-use-everywhere.git)|?|
|[cg-image-picker](https://github.com/chrisgoringe/cg-image-picker.git)|√|
|[Davemane42 Nodes](https://github.com/Davemane42/ComfyUI_Dave_CustomNode)|×|
|[Dagthomas Nodes](https://github.com/dagthomas/comfyui_dagthomas)|√|
|[Dynamic Thresholding](https://github.com/mcmonkeyprojects/sd-dynamic-thresholding)|√|
|[Easy Tools](https://github.com/jafshare/ComfyUI-Easy-Tools)|√|
|[Easy Use](https://github.com/yolain/ComfyUI-Easy-Use)|√|
|[Efficiency Nodes](https://github.com/LucianoCirino/efficiency-nodes-comfyui)|√|
|[EllangoK Postprocessing](https://github.com/EllangoK/ComfyUI-post-processing-nodes)|√|
|[Essentials](https://github.com/cubiq/ComfyUI_essentials.git)|√|
|[ExLlama nodes](https://github.com/Zuellni/ComfyUI-ExLlama-Nodes)|√|
|[experiments](https://github.com/comfyanonymous/ComfyUI_experiments)|√|
|[Fast Decode](https://github.com/nagolinc/ComfyUI_FastVAEDecorder_SDXL)|√|
|[FlowtyTripoSR](https://github.com/flowtyone/ComfyUI-Flowty-TripoSR.git)|√|
|[FreeU Advanced](https://github.com/WASasquatch/FreeU_Advanced)|√|
|[IPAdapter](https://github.com/laksjdjf/IPAdapter-ComfyUI)|√|
|[IPAdapter_plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus)|√|
|[Image Grid](https://github.com/LEv145/images-grid-comfy-plugin)|√|
|[Impact Pack](https://github.com/ltdrdata/ComfyUI-Impact-Pack)|?|
|[Impact Subpack](https://github.com/ltdrdata/ComfyUI-Impact-Subpack)|√|
|[Inspire Pack](https://github.com/ltdrdata/ComfyUI-Inspire-Pack)|√|
|[InstantID (cubiq)](https://github.com/cubiq/ComfyUI_InstantID.git)|√|
|[InstantID (ZHO)](https://github.com/ZHO-ZHO-ZHO/ComfyUI-InstantID.git)|√|
|[KJ Nodes](https://github.com/kijai/ComfyUI-KJNodes.git)|√|
|[LaMa Preprocessor](https://github.com/mlinmg/ComfyUI-LaMA-Preprocessor)|√|
|[Latent2RGB](https://github.com/bvhari/ComfyUI_LatentToRGB)|√|
|[LayerDiffuse](https://github.com/huchenlei/ComfyUI-layerdiffuse)|√|
|[LayerStyle](https://github.com/chflame163/ComfyUI_LayerStyle)|√|
|[LCM](https://github.com/0xbitches/ComfyUI-LCM)|√|
|[Manager](https://github.com/ltdrdata/ComfyUI-Manager)|×|
|[Masquerade Nodes](https://github.com/BadCafeCode/masquerade-nodes-comfyui)|×|
|[Math](https://github.com/evanspearman/ComfyMath.git)|√|
|[Mixlab Nodes](https://github.com/shadowcz007/comfyui-mixlab-nodes.git)|?|
|[MoonDream](https://github.com/kijai/ComfyUI-moondream.git)|√|
|[MotionCtrl](https://github.com/chaojie/ComfyUI-MotionCtrl)|√|
|[MotionCtrl-SVD](https://github.com/chaojie/ComfyUI-MotionCtrl-SVD)|√|
|[Noise](https://github.com/BlenderNeko/ComfyUI_Noise)|√|
|[Portrait Master](https://github.com/florestefano1975/comfyui-portrait-master.git)|√|
|[Power Noise Suite](https://github.com/WASasquatch/PowerNoiseSuite)|√|
|[Prompt Reader](https://github.com/receyuki/comfyui-prompt-reader-node)|√|
|[QR](https://github.com/coreyryanhanson/comfy-qr)|√|
|[OneButtonPrompt](https://github.com/AIrjen/OneButtonPrompt)|√|
|[ReActor](https://github.com/Gourieff/comfyui-reactor-node)|√|
|[Restart-Sampling](https://github.com/ssitu/ComfyUI_restart_sampling)|√|
|[Roop](https://github.com/Navezjt/ComfyUI_roop.git)|√|
|[rgthree](https://github.com/rgthree/rgthree-comfy.git)|√|
|[SD-Latent-Interposer](https://github.com/city96/SD-Latent-Interposer)|√|
|[SDXL_prompt_styler](https://github.com/twri/sdxl_prompt_styler)|√|
|[SeargeSDXL](https://github.com/SeargeDP/SeargeSDXL)|√|
|[Segment Anything](https://github.com/storyicon/comfyui_segment_anything.git)|?|
|[StabilityNodes](https://github.com/Stability-AI/stability-ComfyUI-nodes)|√|
|[TiledDiffusion](https://github.com/shiimizu/ComfyUI-TiledDiffusion)|√|
|[TiledKSampler](https://github.com/BlenderNeko/ComfyUI_TiledKSampler)|√|
|[TinyTerra](https://github.com/TinyTerra/ComfyUI_tinyterraNodes.git)|√|
|[UltimateSDUpscale](https://github.com/ssitu/ComfyUI_UltimateSDUpscale)|?|
|[Vextra Nodes](https://github.com/diontimmer/ComfyUI-Vextra-Nodes)|√|
|[VLM Nodes](https://github.com/gokayfem/ComfyUI_VLM_nodes.git)|√|
|[WAS Suite](https://github.com/WASasquatch/was-node-suite-comfyui)|?|
|[WD14-Tagger](https://github.com/pythongosssss/ComfyUI-WD14-Tagger)|√|
|[zfkun](https://github.com/zfkun/ComfyUI_zfkun.git)|√|

# Links

## User Manual

[用户手册](https://shimo.im/docs/Ee32m0w80rfLp4A2)

[UserManual](https://shimo.im/docs/JSforXF1JC8lSphG)

## Our AI website

[AIGODLIKE Community](https://www.aigodlike.com/)

## ComfyUI Package

[百度网盘](https://pan.baidu.com/s/1bnVWO9AuurPl2mn9Uc57vg?pwd=2333)

[Google Driver](https://drive.google.com/drive/folders/1Akqh3qPt-Zzi_clqkoCwCl_Xjo78FfbM?usp=sharing)

