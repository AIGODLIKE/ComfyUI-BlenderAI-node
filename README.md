# ComfyUI-BlenderAI-node
Add-on for using [ComfyUI](https://github.com/comfyanonymous/ComfyUI) in Blender.
## NOTE 

If you want to use the latest version, please use the [develop](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/tree/develop) branch.
## Function Introduction
1. Automatically convert Comfyui nodes to Blender nodes, enabling Blender to directly generate images using ComfyUI（As long as your ComfyUI can run）
2. Multiple Blender dedicated nodes(For example, directly inputting camera rendered images, compositing data, etc. into COMFYUI)
3. Operation optimization (such as one click drawing mask)
4. Node group presets
5. Queue batch processing
## How to install(Only on WINDOWS 10\11)

1. **Install Blender**

Firstly, you need to install a [Blender](https://www.blender.org/download/)(Suggest Blender 3.5 or 3.6.X, previous versions or 4.0 have not been tested).
![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/aacf1cfe-ae44-4930-9a93-c226a8408066)

2. **Install add-on（ComfyUI BlenderAI node）**

ComfyUI BlenderAI node is a standard Blender add-on. Just download the compressed package and install it like any other add-ons.
![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/2263fb70-5f85-43a1-a9c3-668620c976f6)

Or you can try

      cd %USERPROFILE%\AppData\Roaming\Blender Foundation\blender\
      git clone https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node.git


3. **Settings add-on**

Set the already configured COMFYUI path，and select the startup mode based on VRAM
![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/a0058178-dcf0-4b23-8e79-3e4ae1267286)

## How to use

1. Starting the COMFYUI service

Switch to the ComfyUI workspace, use the shortcut key "N" to open the panel, and click to enable the COMFYUI service (note - this service will not automatically start with Blender startup, as it is not necessary to start COMFYUI at all times)
![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/eef864fb-ee69-4432-970e-8ebf6f4916e6)

2. Add nodes/presets

Like other Blender nodes, you can use the shortcut keys "Shift+A" to bring up the creation menu. You can also click on the "Replace Node Tree" button or "Append Node Tree" button on the right to add/append a node tree. In summary, you should create a node tree like COMFYUI
**Image preview and input must use Blender specially designed nodes, otherwise the calculation results may not be displayed properly (using Blender specially designed nodes does not affect the data, it will automatically be saved as COMFYUI standard data)**
![image](https://github.com/AIGODLIKE/ComfyUI-BlenderAI-node/assets/116185401/588c9e85-306e-4d34-8f73-af9a9230a236)

## Manual

[中文](README.md) [EN](README_EN.md)

[工具手册](https://shimo.im/docs/Ee32m0w80rfLp4A2)

[AIGODLIKE社区](www.aigodlike.com)

## COMFYUI Integration Package

Please upgrade to the latest COMFYUI

[百度网盘](https://pan.baidu.com/s/1bnVWO9AuurPl2mn9Uc57vg?pwd=2333)

[Google Driver](https://drive.google.com/drive/folders/1Akqh3qPt-Zzi_clqkoCwCl_Xjo78FfbM?usp=sharing)

