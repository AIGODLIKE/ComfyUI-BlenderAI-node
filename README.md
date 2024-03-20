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
git clone https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node.git
```
Then you can see the addont after refresh addon menu or reboot Blender.
And don't forget to enable the addon by click the cube at the tilte's left

# Usage

1. **Set the "ComfyUI Path" to your ComfyUI directory**

![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/5d081ee7-0b2a-4871-bdf9-ada05bb12831)


2. **Set the "Python Path" if you're not using the standard ComfyUI file directory**

The default (empty) path is:
```
├── run_nvidia.bat
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


## Notes
- Not every node can work perfectly in Blender, like Blender don't support any video type format
- You can enable the system console in the "Window-Toggle System Console" at the left top
- Preview images needs to have same name as the model and extension like model.ckpt.jpg

# Links

## User Manual

[用户手册](https://shimo.im/docs/Ee32m0w80rfLp4A2)

[UserManual](https://shimo.im/docs/JSforXF1JC8lSphG)

## Our AI website

[AIGODLIKE Community](https://www.aigodlike.com/)

## ComfyUI Package

[百度网盘](https://pan.baidu.com/s/1bnVWO9AuurPl2mn9Uc57vg?pwd=2333)

[Google Driver](https://drive.google.com/drive/folders/1Akqh3qPt-Zzi_clqkoCwCl_Xjo78FfbM?usp=sharing)

