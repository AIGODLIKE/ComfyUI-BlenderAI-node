# Introduction
This is an addon for using [ComfyUI](https://github.com/comfyanonymous/ComfyUI) in Blender. 

ComfyUI : It will convert ComfyUI nodes into Blender nodes, letting you use ComfyUI inside Blender without having to switch between programs.

Blender : Based on ComfyUI, you can directly generate AI full angle materials, use cameras as real-time input sources, and combine with other ComfyUI custom nodes to achieve functions such as AI animation interpolation and style transfer.

(My dream: I hope Blender and ComfyUI can fight side by side in the future)

## Features
- 【New】AI material creation and [texture baking](https://github.com/AIGODLIKE/EasyBakeNode)

https://github.com/user-attachments/assets/564667d4-588e-47ca-9a28-d983b1f30bd2

https://github.com/user-attachments/assets/888fca0b-b081-496c-9837-7ff18264519f
  
- Converts ComfyUI nodes to Blender nodes
- Editable launch arguments in the addon's preferences, or just connect to a running ComfyUI process
- Adds some special Blender nodes like camera input or compositing data
- Draw masks with Grease pencil
- Blender-like node groups
- Queue batch processing with mission excel
- Node tree/workflow presets and node group presets
- Image previews for models in the Load Checkpoint node
- Can directly input or replace the 3D models in Blender
- Composition output perfect controlnet image
- Live preview when sampling
- Easily move images to and from Blender's image editor

Here are some workflow showcases:
You can find all these workflow presets in `ComfyUI-BlenderAI-node/presets/`
### Camera input
![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/f087f254-5486-4d9f-9a13-d327abed3e14)

### Camera input with roop

https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/cb96dd60-b93a-4f09-9ab6-043b66617313

### Import or replace AI generated meshes in the 3D Viewport

![Import Mesh](https://github.com/user-attachments/assets/6aa70423-2cbc-4631-90b2-65808a2a8736)

### Composite depth channel

![Depth Composite](https://github.com/user-attachments/assets/04f0f7cd-fc0c-4b7c-bdc2-72f5af3c437a)

### Pose characters using Blender's bones

![屏幕截图 2024-10-24 173546](https://github.com/user-attachments/assets/fc698396-7369-448a-a7d7-c07ef54aa438)

### Automatic AI gap animation(ToonCrafter)

https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/2c21173b-84e7-433c-bf2f-e61bcca7162c

# Installation

## WINDOWS 10\\11

1. **Install Blender**

First, you need to install [Blender](https://www.blender.org/download/)(We recommend Blender 3.5, 3.6.X, or 4.0).

![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/aacf1cfe-ae44-4930-9a93-c226a8408066)

2. **Install this add-on（ComfyUI BlenderAI node）**
<!--- TODO: "ComfyUI BlenderAI node" is awkward wording. Come up with a better name? -->

- Install from Blender's preferences menu

In Blender's preferences menu, under addons, you can install an addon by selecting the addon's zip file.
Blender will automatically show you the addon after it's installed; if you missed it, it's in the Node category, search for "ComfyUI".
Don't forget to enable the addon by clicking on the tickbox to the left of the addon's name!

*Note*: The zip file might not have a preview image. This is normal.

![Install](https://github.com/user-attachments/assets/24e20504-c754-41e4-b797-808d0b8373f2)


- Install manually (recommended)

This is a standard Blender add-on. You can git clone the addon to Blender's addon directory:

```
cd %USERPROFILE%\AppData\Roaming\Blender Foundation\blender\%version%\scripts\addons
git clone https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node.git --recursive
```
Then you can see the addon after refreshing the addons menu or restarting Blender.
It is in the Node category, search for "ComfyUI".
Don't forget to enable the addon by clicking on the tickbox to the left of the addon's name!

3.**AI material generation**
(Baking requires the use of the add-on EasyBakeNode)

1. Install the add-on [EasyBakeNode](https://github.com/AIGODLIKE/EasyBakeNode)
   
2. Your [ComfyUI](https://github.com/comfyanonymous/ComfyUI) is working properly

3. You need to download [Controlnet model](https://huggingface.co/lllyasviel/ControlNet-v1-1/tree/main) (At least download the following ones)and install [comfyui controlnet aux](https://github.com/Fannovel16/comfyui_controlnet_aux)
   
![img_v3_02hg_1b4afd70-a35f-40ce-b251-10d9da7b4d5g](https://github.com/user-attachments/assets/a4098e3e-881e-43e7-bbe1-5ffa19b89f73)


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

![Generate](https://github.com/user-attachments/assets/5999d8d4-f380-452d-a604-608b57928a6a)


5. **Add nodes/presets**

Like in the other Node Editors, you can use the shortcut `Shift`+`A` to bring up the Add menu to add nodes. You can also click on the "Replace Node Tree" or "Append Node Tree" buttons in the sidebar to add/append a node tree.

**For image previews and input, you must use the Blender-specific nodes this addon adds, otherwise the results may not be displayed properly! 
Using the Blender-specific nodes won't affect generation, results will still be saved as ComfyUI standard data.**

![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/22c68423-07aa-4a07-93a9-9354880276e1)

6. **Generate**

By clicking `Excute Node Tree` in n-panel, or the little red button on the right in header in node editor, current node tree will add to queue list.
You can cancel current running task by clicking `Cancel`, clear all task list by clicking `ClearTask`.

Loop execution is in advanced executing option at the side of `Excute Node Tree` button.

![Generate](https://github.com/user-attachments/assets/5999d8d4-f380-452d-a604-608b57928a6a)

## Special Nodes for Blender

### Input Image

![Input Image](https://github.com/user-attachments/assets/2158be8f-eaf8-4a69-b3d0-7de97a93c517)

- Input image from directory
- Input image list from directory
- Input image from render(Supports current and selected frames)
- Input image from viewport(Supports real-time refresh)

### Mask

![Mask](https://github.com/user-attachments/assets/8fb29634-996e-4390-81da-e33fbd56489c)

- Create a mask from Grease Pencil
- Create a mask by projecting an object on the camera
- Create a mask by projecting a collection on the camera

### Mat Image

![Mat Image](https://github.com/user-attachments/assets/65844d9a-820f-4a7d-ae5e-1c438b5724ae)

- Input texture from object
- Input textures from collection objects

### Save Image

![Save Image](https://github.com/user-attachments/assets/f431e952-9541-4a40-a288-46abd66fa859)

- Normally saves to a folder
- Can save to an image in Blender to replace it


### Multiline Textbox

![Multiline Textbox](https://github.com/user-attachments/assets/423c3b65-45fc-4726-afe4-1f73d0a5e6b7)

To improve writing long prompts, we made a button that can show all prompts in a separate textbox since Blender doesn't support multiline textboxes in nodes.
When you click the button on the side of the textbox, a window will open to write prompts in.
The first time you do this, you might need to wait. Keep your cursor over the window while typing.

## Shortcut Keys

### Link

Select a node, then hold `D` and drag the cursor to another node's center, you can link all available widgets between them

![Link](https://github.com/user-attachments/assets/ec9c8f8f-96b7-4269-8837-63017df17b3b)

### Search Widgets

By pressing `R` when the cursor is near a widget, a pie menu will display all nodes that have this widget

![Search Widgets](https://github.com/user-attachments/assets/a385f35c-bcec-4f2d-9f8b-4989530170d3)

### Mask Link

Hold `F` and drag the cursor to a mask node, it will automatically create a camera to generate mask from the scene

![Mask Link](https://github.com/user-attachments/assets/ce301a58-a322-4b34-a3cf-1394d02e3ace)

## Notes
- Not every node can work perfectly in Blender, for example nodes regarding videos
- You can enable the console under `Window`>`Toggle System Console` at the top left
- Model preview images need to have the same name as the model, including the extension, for example - `model.ckpt.jpg`
- **Do not install as extensions**

## Tested Nodes
Here are some interesting nodes we've tested in Blender

√ = works as in ComfyUI web

? = not all functions work

× = only a few or no functions work

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

[[CN]How to create and bake AI materials in Blender](https://www.bilibili.com/video/BV1NKqkY8ETU/)

[[EN]BSLIVE ComfyUI Blender AI Node Addon for Generative AI(By Jimmy Gunawan)](https://www.youtube.com/watch?v=OvrKpAVwyco)

[[EN]Generate AI Rendering with Blender ComfyUI AddOn(By Gioxyer)](https://www.youtube.com/watch?v=9rb-8D3NQ58)

[[CN]无限圣杯完全使用指南](https://www.bilibili.com/video/BV1Fo4y187HC/)

(Please feel free to contact me for recommendations)

## Our AI website

[AIGODLIKE Community](https://www.aigodlike.com/)


