# Introduction
This is an addon for using [ComfyUI](https://github.com/comfyanonymous/ComfyUI) in Blender. It will convert ComfyUI nodes into Blender nodes, letting you use ComfyUI inside Blender without having to switch between programs.
## Features

- Converts ComfyUI nodes to Blender nodes
- Edit launch arguments in the n-menu (sidebar)/addon preferences, or just connect to a running ComfyUI process
- Support for Blender nodes like camera input or compositing data
- Draw masks with Grease pencil
- Blender-like node groups
- Queue batch processing with mission excel
- Node tree/workflow presets and node group presets
- Image previews for models in the Load Checkpoint node
- Can directly input or replace the 3D models in Blender
- By using composite can output perfect controlnet image

Here are some workflow showcases:
You can find all these workflow presets in `ComfyUI-BlenderAI-node/presets/`

### Camera input
![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/f087f254-5486-4d9f-9a13-d327abed3e14)

### Camera input with roop

https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/cb96dd60-b93a-4f09-9ab6-043b66617313

### Import or replace AI generated meshes in the 3D Viewport

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/92b2913f-f20b-4e6c-85b6-e9f60a7b58f1)

### Composite depth channel

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/2386dc4d-6faa-4054-83e7-93f49a27962a)

### Pose characters using Blender's bones

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/484c12bf-55b8-4baf-92df-e422fd900cbf)

# Installation

## WINDOWS 10\\11

1. **Install Blender**

First, you need to install [Blender](https://www.blender.org/download/)(Recommend Blender 3.5, 3.6.X, or previous 4.0).

![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/aacf1cfe-ae44-4930-9a93-c226a8408066)

2. **Install this add-on（ComfyUI BlenderAI node）**
<!--- TODO: "ComfyUI BlenderAI node" is awkward wording. Come up with a better name? -->

- Install from Blender's preferences menu

In Blender's preferences menu, under addons, you can install an addon by selecting the addon's zip file.
Blender will automatically show you the addon after it's installed; if you missed it, it's in the Node category, search for "ComfyUI".
Don't forget to enable the addon by clicking on the tickbox to the left of the addon's name!

*Note*: The zip file might not have a preview image. This is normal.

![Pasted image 20240319183259](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/7772234d-6d7c-40da-9a32-ee918ca719fb)


- Install manually (recommended)

This is a standard Blender add-on. You can git clone the addon to Blender's addon directory:

```
cd %USERPROFILE%\AppData\Roaming\Blender Foundation\blender\%version%\scripts\addons
git clone https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node.git --recursive
```
Then you can see the addon after refreshing the addons menu or restarting Blender.
It is in the Node category, search for "ComfyUI".
Don't forget to enable the addon by clicking on the tickbox to the left of the addon's name!

## Linux
If you're using Linux, assuming you have some experience:

1. Install [Blender](https://www.blender.org/download/)
2. Create and activate a Python venv
3. Install [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
4. `cd /home/**YOU**/.config/blender/**BLENDER.VERSION**/scripts/addons`
4. `git clone https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node.git --recursive`
5. Set your ComfyUI path and your venv /bin/ path in the addon's preferences

Some things will not work on Linux, or might break!

# Usage

1. **Prepare ComfyUI**

You can download ComfyUI from here: [ComfyUI Releases](https://github.com/comfyanonymous/ComfyUI/releases)

Or you can build one yourself as long as you follow this path structure:

```
├── ComfyUI
│   ├── main.py
│   ...
├── python_embeded
│   ├── python.exe
│   ...
```

2. **Set the "ComfyUI Path" to your ComfyUI directory**

![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/5d081ee7-0b2a-4871-bdf9-ada05bb12831)


3. **Set the "Python Path" if you're not using the standard ComfyUI file directory**

The default (empty) path is:
```
├── ComfyUI
├── python_embeded
│   ├── python.exe  <-- Here
```

If you're using a virtual environment named `venv`, the executable is in `venv/Scripts/python.exe`.

4.  **Open the ComfyUI Node Editor**

Switch to the ComfyUI Node Editor, press N to open the sidebar/n-menu, and click the `Launch/Connect to ComfyUI` button to launch ComfyUI or connect to it.
Or, switch the "Server Type" in the addon's preferences to remote server so that you can link your Blender to a running ComfyUI process.
![Pasted image 20240319185542](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/e46c3a5a-ff32-4503-8228-f101c91c6664)


5. **Add nodes/presets**

Like in the other Node Editors, you can use the shortcut `Shift`+`A` to bring up the Add menu to add nodes. You can also click on the "Replace Node Tree" or "Append Node Tree" buttons in the sidebar to add/append a node tree.
**For image previews and input, you must use the Blender-specific nodes this addon adds, otherwise the results may not be displayed properly! 
Using the Blender-specific nodes won't affect generation, results will still be saved as ComfyUI standard data.**

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

- Create a mask from Grease Pencil
- Create a mask by projecting an object on the camera
- Create a mask by projecting a collection on the camera

### Mat Image

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/8fff5b65-9c7f-4053-8bc6-ea16184774ad)

- Input texture from object
- Input textures from collection objects

### Save Image

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/edbc273d-40cd-482b-835f-fb8b69812684)

- Normally saves to a folder
- Can save to an image in Blender to replace it


### Multiline Textbox

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/bdc796c0-7dec-4c5d-922e-17860941a23e)

To improve writing long prompts, we made a button that can show all prompts in a separate textbox since Blender doesn't support multiline textboxes in nodes.
When you click the button on the side of the textbox, a window will open to write prompts in.
The first time you do this, you might need to wait. Keep your cursor over the window while typing.

## Shortcut Keys

### Link

Select a node, then hold `D` and drag the cursor to another node's center, you can link all available widgets between them

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/eae1061a-c4f5-4f0c-becf-501176a7aaa2)

### Search Widgets

By pressing `R` when the cursor is near a widget, a pie menu will display all nodes that have this widget

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/2dcffa51-a261-4e22-9692-00863e4faa33)

### Mask Link

Hold `F` and drag the cursor to a mask node, it will automatically create a camera to genarate mask from the scene

![image](https://github.com/DorotaLuna/ComfyUI-BlenderAI-node/assets/122320001/d97805e5-4f54-4e1a-9fe0-0b98192baab9)



## Notes
- Not every node can work perfectly in Blender, for example nodes regarding videos
- You can enable the console under `Window`>`Toggle System Console` at the top left
- Model preview images need to have the same name as the model, including the extension, for example - `model.ckpt.jpg`

## Tested Nodes
Here are some interesting nodes we've tested in Blender

√ = works as in ComfyUI web

? = not all functions work

× = only few or no functions work

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

# Change Log
See [Change Log](./CHANGE_LOG.md).

# Links
## Tutorial
[[EN]BSLIVE ComfyUI Blender AI Node Addon for Generative AI(By Jimmy Gunawan)](https://www.youtube.com/watch?v=OvrKpAVwyco)

[[EN]Generate AI Rendering with Blender ComfyUI AddOn(By Gioxyer)](https://www.youtube.com/watch?v=9rb-8D3NQ58)

[[CN]无限圣杯完全使用指南](https://www.bilibili.com/video/BV1Fo4y187HC/)

(Please feel free to contact me for recommendations)

## Our AI website

[AIGODLIKE Community](https://www.aigodlike.com/)


