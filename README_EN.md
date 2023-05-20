## Blender Open Source AI Tools Infinite Grail Node

[中文](README.md) [EN](README_EN.md)

[Manual](https://shimo.im/docs/Ee32m0w80rfLp4A2)

[AIGODLIKE Community](www.aigodlike.com)

# Chapter One: Preface

#### Introduction

> The Infinity Grail Tool is a blender AI tool developed by"只剩一瓶辣椒酱-幻之境开发小组"(a development team from China)based on the STABLE DIFFUISON ComfyUI core, which will be available to blender users in an open source & free fashion.

### Download Address

## [Blender Infinity Grail Node (ComfyUI Edition)](https://pan.baidu.com/s/1bnVWO9AuurPl2mn9Uc57vg?pwd=2333)
Video Tutorial

## [Google Driver](https://drive.google.com/drive/folders/1Akqh3qPt-Zzi_clqkoCwCl_Xjo78FfbM?usp=sharing)

#### Complete Collection Of Bilibili (Under Update)

# [Blender x ComfyUI Node-Style AI Painting Adventure -00 Installation and Deployment (including Full Blood Version integration Pack)](https://www.bilibili.com/video/BV1Fo4y187HC/)
Chapter Two: Introduction to All Nodes

Editor:谷缘芷月、只剩一瓶辣椒酱、王也道长OS

## Sampling

### K Sampler

![图片](.img/7c794344dd6e7f7dfb8d9922db6aef0593600b9f48b4036857b868a1b83e8e72.jpg)



K Sampler can add the noise to the latent space and then gradually remove the noise to regenerate the latent space.

#### Seed

* Specifies the random seed to generate the noise
* < Node random every run > The random seed of this sampler changes randomly every run after it is turned on
* < Random All > The random seeds of all samplers change with each run after it is enabled
#### Steps

* Specifies the number of times to remove noise
#### **CFG**

* Control the effect of prompt on sampling
#### Sampler

* Specifies the sampler to use
#### Scheduler

* Specifies the scheduler to use,to adjust the degree of noise removal each time
    * karras：Nonlinear sampling
    * normal：Equidistant interval sampling
    * simple：Approximate equidistant interval sampling is the simplest scheduler
    * ddim_uniform：Official effect, recommended in combination with ddim
* Normally, only karras is used
#### Denoise

* Specifies the amount of noise to be added, generally applicable to graph generation graphs.
#### Correlation Node

* [Checkpoint Simple Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-KF2C 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [CLIP Text Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-jthz 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [VAE Decode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-T9uA 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [K Sampler Advanced](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-IJ7C 《无限圣杯AI节点(ComfyUI)使用者手册》)
### K Sampler Advanced 

![图片](.img/64f3dc5d110e2282fc57d59d021493a918f06256beca86c94664620e9cc1d1ee.jpg)



#### Add Noise

* Whether the switch adds noise
#### Noise

* Specifies the random seed to generate the noise
* < Node random every run > The random seed of this sampler changes randomly every run after it is turned on
* < Random All > The random seeds of all samplers change with each run after it is enabled
#### Starting At Step

* Specifies the number of steps to start adding noise
#### Add Noise

* Specifies the number of steps to end adding noise
#### Return Residual Noise

* Specifies whether to fully return undenoised waves, as reflected in the return noise screen
#### Correlation Node

* [Checkpoint Simple Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-KF2C 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [CLIP Text Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-jthz 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [VAE Decoder](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-T9uA 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [K Sampler](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-UvgV 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Loader

### Checkpoint Simple Loader

Able to load model, U-net, VAE encoder/decoder in checkpoint(safetensor) file, outputs as model, CLIP, VAE.

#### Special Instructions

* The loader automatically recognizes the size and version of the model, but it is not entirely accurate.
* The default is not to limit CLIP depth, you can use <CLIP Set Last Layer > to limit CLIP
#### Correlation Node

* [Checkpoint Simple Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-rwwQ 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Inverse CLIPcheckpoint loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-0ACT 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Diffusion Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-6ZiQ 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [CLIP Text Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-jthz 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [CLIP Set Last Layer](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-OFAv 《无限圣杯AI节点(ComfyUI)使用者手册》)
### **VAE L**oader

![图片](.img/b85410899096c4fcc3cbcf162010b50bf6e24e1e53c992dae2795f6774ed2be4.jpg)



It is able to load VAE.

#### Correlation Node

* [VAE Decode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-T9uA 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [VAE Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-FJ4Q 《无限圣杯AI节点(ComfyUI)使用者手册》)
### LoRA Loader

![图片](.img/d2131b75854759a999e62fc7fae6af382245ba3e1cfa4de664b080d1e39f73cb.jpg)



It is able to load The LoRA model.

#### Special Instructions

* Can load LoHA, LoCON, LoKR and other models.
#### Correlation Node

* [Checkpoint Simple Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-KF2C 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [CLIP Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-4xjf 《无限圣杯AI节点(ComfyUI)使用者手册》)
### CLIP Loader

![图片](.img/e6291cb07c2b3906f1dbc317bb8de70585c9169e446a6af3fcb917ad4399d70e.jpg)



It is able to load CLIP model.

#### Correlation Node

* [CLIP Text Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-jthz 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Inverse CLIPcheckpoint Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-0ACT 《无限圣杯AI节点(ComfyUI)使用者手册》)
### **ControlNet**Loader

![图片](.img/7ea7263635156594a039b2fb9709e8e243b2f5c3b8cc812ef36def3ab9e0b486.jpg)



It is able to load ControlNet model

#### Correlation Node

* [ControlNet Apply](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-x81Z 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Different ControlNet Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-cw0Z 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Different ControlNet Loader

![图片](.img/e2818b8979f0477e981d9c20c885e44ea9d5223e3072fbe61ede825a74822174.jpg)



Another loader capable of loading the ControlNet model.

#### Correlation Node

* [ControlNet Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-ZBu4 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Style Model Loader

It is able to load style models.

#### Correlation Node

* [Style Model Apply](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-jOYQ 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [CLIP Visual Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-Gh0K 《无限圣杯AI节点(ComfyUI)使用者手册》)
### **CLIP**Visual Loader

![图片](.img/03ff077ab97cd570a8f1cca612f78d15fd2aa921aab0cf1f4d46b0b0bab31404.jpg)



It is able to load Clip Visual model

#### Correlation Node

* [CLIP Visual Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-Gh0K 《无限圣杯AI节点(ComfyUI)使用者手册》)
#### Using Examples 

![图片](.img/a5eac30ddffa1602c37aaee94cc9cf1ab2d8345f5fd59b7dc1ebd24954ea0d1b.jpg)



### unCLIP Checkpoint Loader

![图片](.img/2ef0db47586ef65e5fb64f3199b88d935da53c3a8cc87247837a305ad3d624b0.jpg)



It is able to load the model in the Safecheckpoint file, the CLIP text layer, the VAE encoding/decoder and the CLIP visual layer, and the output is the model, CLIP, VAE and visual CLIP.

#### Correlation Node

* [Checkpoint Simple Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-KF2C 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [CLIP Text Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-jthz 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [CLIP Visual Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-Gh0K 《无限圣杯AI节点(ComfyUI)使用者手册》)
#### Using Examples

![图片](.img/bb29d86dba999bab434baf2007ab03a5ce220cdcdeb84db57864805f0d8a5587.jpg)



### **GLIGEN**Loader

![图片](.img/60c795cb3926a67fa559475e8e85445a76435e70a2d829a8e11decc19825c269.jpg)



It is able to load GLIGEN model.

#### Correlation Node

* [GLIGEN Text Box Apply](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-f2Ff 《无限圣杯AI节点(ComfyUI)使用者手册》)
#### Using Examples

![图片](.img/bb7b12ff7d909bbc32d7c0fbdc189ff8bff4b571a06ec711662f5dbc326bca39.jpg)



### Hypernetwork Loader

![图片](.img/486b13c789dbe5caa3579892fc838df79dd8f95dad11f8d1b5ff22632f101c12.jpg)



It is able to load Hypernetwork。

#### Correlation Node

* [Checkpoint Simple Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-KF2C 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [K Sampler](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-UvgV 《无限圣杯AI节点(ComfyUI)使用者手册》)
#### Using Examples

![图片](.img/c48f848893a23c07a64668453b8efd5828df28ac63e8071d10d1eee7589baf97.jpg)



## Condition

### Style Model

### Style Model Apply

![图片](.img/84513f5e0b6b290c9346741a66272ccbfd557897ee629358b55d9c3ca7f571e7.jpg)



Apply the visual CLIP to the condition.

#### Special Instructions

* When other style conditions already exist in the upstream node, the style is superimposed with the upstream style.
* CLIP visual encoding is required.
#### Correlation Node

* [CLIP Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-4xjf 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Visual Style Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-Bg14 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [CLIP Visual Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-Gh0K 《无限圣杯AI节点(ComfyUI)使用者手册》)
#### Using Examples

![图片](.img/14a01a28e7aede1cbebe440705f8dc8ecf38220a4ecf141369eb703ed64171f3.jpg)



### GLIGEN Language Based Image Generation

#### GLIGEN Text Box Apply

## ![图片](.img/36934526d2bcf18e7173b377f5e7164fee8bcfd07a7980464c393d538dd700b3.jpg)



This node restricts the specified text in the condition to the specified location.

#### Width And Height

* Specifies the area size.
#### XY

* Specifies the area location, with the coordinates being the upper-left corner.
#### Special Instructions

* Can be used superimposed to control the range of each prompt
* If a condition exists upstream of the node tree, the condition is applied to the upstream node
* When a condition is applied simultaneously on different scales, it can produce unpredictable results
#### Correlation Node

* [CLIP Text Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-jthz 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Checkpoint Simple Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-KF2C 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [GLIGEN Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-chaq 《无限圣杯AI节点(ComfyUI)使用者手册》)
#### Using Examples

![图片](.img/6e0adebd09cbc8c9cddcc8e3ed8ec4c803dc36041870c3c30c9d69ba55c0d3e8.jpg)



### CLIP Text Encode

![图片](.img/fbf53293f0f69c204d5e2db7a3df238758ecf6dfaa755ddf26dd3a0231dad0ff.jpg)



This node encodes the text content as a condition.

#### Text

* Be able to read Texture Inversion | Embedding，The use method is"embedding:embdding_name"
* When multiple embedding needs to be read,use“embedding:emb_1,embedding:emb_2”
#### Correlation Node

* [Checkpoint Simple Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-KF2C 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [K Sampler](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-deRh 《无限圣杯AI节点(ComfyUI)使用者手册》)
### CLIP Set Last Layer

![图片](.img/b0685d1d24f6c299f3c616a3b9dd1db70bef57f6cab039bcdcb562e4cba04915.jpg)



This node is able to limit the depth of the CLIP

#### Stop At Clip Layer

* When the value is -1, there is no limit
* When the value is -2, stop before the last layer
* When the value is -3, stop before the last 2 layers
#### Special Instructions

This node can cause the model to produce unpredictable results,some prompt may depend on this setting.

#### Correlation node

* [Checkpoint Simple Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-KF2C 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Text Encoder](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-jthz 《无限圣杯AI节点(ComfyUI)使用者手册》)
#### Using Examples

![图片](.img/fab20aa2f2a87a7391e21618202604446f67a07d13c64475972caea3b53aa3d9.jpg)



### Conditioning Average

![图片](.img/b9bd56b70bb359bc871bccaa0bf6be3ccf1c372288b6e508ca9cc08a0172c7e2.jpg)



Average the two conditions by strength.

#### Condition To Strength

* Specify the mixing strength value. The smaller the value, the stronger the conditional source effect
#### Special Instructions

* If Condition Source contains multiple sets of conditions, only the first set of conditions is used
### Conditioning Combine

![图片](.img/ecf54424703f00722c1d9d9b55b720c501f77b67bd4dc48e2ef1e6e26db57653.jpg)



Combine two conditions.

#### Special Instructions

* It is a simply combination.
* Usually used in conjunction with < conditional region >.
* The combined conditions are output separately, different from the effect of entering a set of conditions at the same time.
#### Correlation Node

* [CLIP Text Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-jthz 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Conditioning Set Area](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-msbm 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Conditioning Set Area

![图片](.img/6040f6207fbaf09b0e1a1df220c213f4b73403e5830fb97e964baedd2229b113.jpg)



Constraints are sampled in a specified area, and weights can be set.

#### Width And Height

* Specified area size.
#### XY

* Specified position,coordinates for the "sampling from" the top left corner of the latent first pixel.
#### Strength

* Designated Limit Strength
#### Special Instructions

* The function of this node is not to restrict the condition area
* If there is a region without any conditions, the calculation returns the noise
* If a condition exists on the upstream node, the condition overrides the upstream condition
#### Correlation Node

* [CLIP Text Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-jthz 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Conditioning Set Mask](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-KiX1 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Conditioning Set Mask

![图片](.img/2b9cb1703d3252e55e747d537c5082897a8845ae724e8d4af3c7c2f8af9a38ca.jpg)



Through the mask limit the condition sampling in the specified area, and the weight can be set.

#### Strength

* Specified Conditional Strength.
#### Set Condition Area

* Select whether to generate only in mask.
#### Special Instructions

* The function of this node is not to restrict the condition area.
*  there is a region without any conditions, the calculation returns the noise.
* If a condition exists on the upstream node, the condition overrides the upstream condition.
#### Correlation Node

* [Conditioning Set Area](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-msbm 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Conditioning Combine](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-0pZn 《无限圣杯AI节点(ComfyUI)使用者手册》)
#### Using Examples

![图片](.img/c46d653d9662d9fe81aee9225cbe6b824d38ee158af90105e4f6385755d4797e.jpg)



### CLIP Visual Encoder

![图片](.img/ee3bdc090994424fdb17efad5a261103433c442e9da16f1ce0ee70c461227dc2.jpg)



Visual CLIP is used to encode images.

#### Correlation Node

* [unCLIP Checkpoint Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-0ACT 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [CLIP Visual Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-USpG 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [unCLIP Conditioning](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-XZD8 《无限圣杯AI节点(ComfyUI)使用者手册》)
#### Using Examples

![图片](.img/65ff72176c1f1b5fb0ad4187e4ff57bde0d85d29a9dae836692186d69d5531fd.jpg)



### unCLIP Conditioning

![图片](.img/221d0f711482c5f0441ecd024d0a2f31d56f26eacd91f9a3467abad28bb7d303.jpg)



The visual CLIP encoded output image is applied to the condition.

#### Special Instructions

* This node applies only to the unCLIP model.
#### Correlation Node

* [CLIP Text Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-jthz 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [CLIP Visual Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-Gh0K 《无限圣杯AI节点(ComfyUI)使用者手册》)
#### Using Examples

![图片](.img/6371f5a99674976de1370b462f8b8f721645287febe73dc119e85de839ea13d0.jpg)



### ControlNet Apply

![图片](.img/9a471088d2afbc11b75b6d45047caa3fa44bdfea64c1867ff9f702059105671e.jpg)



Apply ControlNet to conditions.

#### Correlation Node

* [ControlNet Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-ZBu4 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [CLIP Text Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-jthz 《无限圣杯AI节点(ComfyUI)使用者手册》)
#### Using Examples

![图片](.img/2585efac3d4a74aa4781c1337cbd8928e8f43e07c4faf2afa854a5389ab2ed88.jpg)



## Latent Space

### Internal Complement Drawing

### VAE Encode For Inpaint

![图片](.img/88cc024b66104bb62e8686326a022dea5f715139000d17ffa135b9eae5e030fe.jpg)



The encoded image is latent, and areas with a color value greater than 0.5 in the mask become the target of internal filling.

#### Special Instructions

* The mask input is stretched to the size of the input image.
#### Correlation Node

* [VAE Decode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-T9uA 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [K Sampler](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-UvgV 《无限圣杯AI节点(ComfyUI)使用者手册》)
#### Using Example![图片](.img/a7721e66d513014aba3c55d8837547a5ed900503441ac7cc500cdea3416d0b53.jpg)



![图片](.img/a7721e66d513014aba3c55d8837547a5ed900503441ac7cc500cdea3416d0b53.jpg)



### Set latent Noise Mask

![图片](.img/c95c8b819e8fa5629d24ba49b7cd148e6e6ecad4d0a9e00784d1ca47a5db6b04.jpg)



With noise overlay latent, the content outside the mask is replaced by noise.

#### Special Instructions

* The noise that is replaced affects the generation of the rest of the content
* If the upstream node already has a noise mask, the noise replaces the upstream noise
#### Correlation Node

* [VAE Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-FJ4Q 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [K Sampler](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-UvgV 《无限圣杯AI节点(ComfyUI)使用者手册》)
### 
### Batch

### Latent From Batch

![图片](.img/164d8b82ba765b75aba34e67585b2a1cf87aa72dfe1bd65d13c67ea98d101090.jpg)



Select the node latent, the amount determined by < batch size >.

#### Batch Index

* Choose the latent on the field, 0 denotes the first one.
#### Correlation Node

* [Empty Latent Image](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-OpNE 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [VAE Decode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-T9uA 《无限圣杯AI节点(ComfyUI)使用者手册》)
#### Using Examples

![图片](.img/2fe16792efbbb56b29085db381f59d8d4524cee45ee3f26f9ba20df0f00518e6.jpg)



### Repeat Latent Batch

![图片](.img/b6ea9d3e30939cd235ddc5d35bb95534b2e4b97b83a708d078931d241d12b638.jpg)



Copy batches a specified number of times.

#### Amount

* Specifies the number of times to copy
* Keep the batch order when copying
* lat_1, lat_2  →  lat_1, lat_2, lat_1, lat_2
### Rebatch Latents

![图片](.img/7dc4cfcc222f811060bcff26757f8927308cac938b3fc409a575783be9c04bf2.jpg)



Respecify the batch size.

#### Batch Size

* Respecify the batch size in each batch
* When the total amount of the original lot is greater than the target amount, the original lot is split into a batch sequence of the specified size
* When the total quantity of the original batch is not greater than the target quantity, output the original batch quantity
#### Special Instructions

* The number of batches output by this node is calculated simultaneously, rather than individually
#### Using Examples

![图片](.img/7034cafb4fe7591e42b56b128810c7e7db8a99ddfc3d28d5a84e14f56874e8bd.jpg)



### Transformation

### Latent Rotate

![图片](.img/36b1a01190e2e2c3f2986e1da12643e46fc7f5fce34688df9bcc2e448dadfe44.jpg)



Rotate latent.

#### Rotation

* Rotate the specified angle clockwise.
#### Correlation Node

* [VAE Decode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-T9uA 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [K Sampler](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-UvgV 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Latent Flip

![图片](.img/4d3c611d38744280b10a17a545be718795333fcca64d12fdb875d330ddf3eb70.jpg)



Flip latent。

#### Correlation Node

* [VAE Decode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-T9uA 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [K Sampler](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-UvgV 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Latent Crop

![图片](.img/4d2a93c49aad41bda3fce626f08a8cc812ef9d848733e8ddb6e423783f406c3c.jpg)



Crop latent.

#### Width And Height

* Specifies the size of latent to be pruned out.
#### XY

* Specified position,coordinates for the "sampling from" the top left corner of the latent first pixel.
#### Special Instructions

* The output latent becomes the new latent instead of overwriting the external content with empty latent
#### Correlation Node

* [VAE Decode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-T9uA 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [K Sampler](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-UvgV 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Latent Composite](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-DRGK 《无限圣杯AI节点(ComfyUI)使用者手册》)
### VAE Decode

![图片](.img/bf13f0ec8c0d9c937a040818e56357d3d228b230297d28a42be95b2507f403f2.jpg)



Decode the latent into an image.

#### Correlation Node

* [Checkpoint Simple Loader](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-KF2C 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [VAE Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-FJ4Q 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [VAE Decode Tiled](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-v4pB 《无限圣杯AI节点(ComfyUI)使用者手册》)
### VAE Encode

![图片](.img/66dcd1261fdbee6754c08d02c48e84fb3d9e82f3b78ba956490262b8011fac95.jpg)



Encode the image to latent.

#### Correlation Node

* [K Sampler](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-UvgV 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [VAE Decode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-T9uA 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [VAE Decode Tiled](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-yuDk 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Empty Latent Image

![图片](.img/bd0aadeecf1bbbc54d82dcb9b9338400eb686d21588e71140249ca2588f14df7.jpg)



Generate an empty latent.

#### Width And Height

* Specify the latent size.
#### Batch Size

* Specifies the number of latent generated simultaneously.
#### Special Instructions

* The latent generated at the same time feeds directly to the downstream node,the first latent is automatically selected when <VAE decode > is used.
* The use of latent random species in the same cohort is incremental,for example, 123, 124, 125.
#### Correlation Node

* [Latent Composite](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-DRGK 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Obtain Latent From The Batch](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-19QR 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Latent Upscale

![图片](.img/fa339d50d9cf458164c8239013feb26530c1e49c883107bc3121e0d1e737f9bf.jpg)



Using the image processing algorithm to scale latent, you can specify the size after scaling.

### Upscale Method

* Nearest - Exact: Copy the pixel closest to the original image.
* Bilinear: Select 4 pixels connected in the original image and interpolate between 2 points.
* Area: The same as "nearest - exact".
* area：和临近-精确相同
#### Width and Height

* Specifies the size of latent to scale to.
#### Crop

* Whether to crop the original image.
* If not opened, the latent stretches to match the target width and height.
#### Correlation Node

* [Image Scale](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-PieC 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Latent Composite

![图片](.img/5705ff43f4c62fec2f1190841c01bc4853003d77d3094f8810045070e582be74.jpg)



Composite "sample from" to "sample to".

#### XY

* Specified position,coordinates for the "sampling from" the top left corner of the latent first pixel.
#### Special Instructions

Blend two latent based on the color value of the mask,the output is (1-mask) *destination+mask*source.

#### Correlation Node

* [Empty Latent Image](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-OpNE 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [K Sampler](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-UvgV 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Latent Composite Masked](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-KXj5 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Latent Composite Masked

![图片](.img/9476396a8fe30965ba3293be1233effc3b5f0ce7e3fa5aff84952a4ed0895022.jpg)



Similar to <Latent Composite>,eclosion is not available, masks can be used.

#### XY

* Specified position,coordinates for the "sampling from" the top left corner of the latent first pixel.
#### Special Instructions

* The two latent values were mixed based on the color value of the mask and the output was （1-mask）*destination+mask*source.
#### Correlation Node

* [Empty Latent Image](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-DRGK 《无限圣杯AI节点(ComfyUI)使用者手册》)
## Image Scale

![图片](.img/0b51023497fcc684027ded80b0587837137a1c3f68b1a83c3903efe1a5ceacbb.jpg)



Scale the image using an image processing algorithm,ability to specify the size after scaling.

#### Amplification Method

* Nearest - Exact: Copy the pixel closest to the original image.
* Bilinear: Select 4 pixels connected in the original image and interpolate between 2 points.
* Area: The same as "Nearest - Exact".
#### Width and Height

* Specifies the size to which the image is to be scaled
#### Crop

* Whether to crop the original image
* If not enabled, the image will be stretched to fit the target width and height
#### Correlation Node

* [Image Upscale With Model](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-5JVV 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Image Upscale With Model

![图片](.img/f0c8a99644bb9e04aaf29f6866531bf51e448ce75b7dc7bba27fc7e029660937.jpg)



Upscale the image using a upscale model.

#### Correlation Node

* [Image Scale](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-PieC 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Post-Processing

### Image Blend

![图片](.img/58e913e73fef27669da42f04766351e9e6d7821a226138f4e9e0c0da0d78a72a.jpg)



Using the algorithm to blend two images.

### Blend Mode

* Soft Light:
    * img2 <= 0.5,
    * img1 - (1 - 2 * img2) * img1 * (1 - img1),
    * img2 > 0.5,
    * (1 - 2 * img2)* img1 * (1 - img1) + img1^2
* Overlay:
    * img1 <= 0.5,
    * 2 * img1 * img2,
    * img1 > 0.5
    * 1 - 2 * (1 - img1) * (1 - img2)
* Screen：1 - (1 - img1) * (1 - img2)
* Multiply：img1 * img2
* Normal：img2
### Image Blur

![图片](.img/61d2cee3e86eb14736b20d2516a449f48d6368df384ea5ffea26feebdc7708ee.jpg)



Use algorithms to blur images.

#### Blur Radius

* The larger the value, the stronger the blur effect
#### Sigma Coefficient

* The larger the value, the greater the blur range.
### Image Quantize

![图片](.img/b85b4eadfc7e5138d360a22c0d02e286823626ef4c7e66521596e3eb6dac1a2c.jpg)



Use an algorithm to quantify the image.

#### Colors

* Specifies the number of colors used to represent the image
#### Dither

* Whether to reduce the ribbon by adding a small amount of noise
### Image Sharpen

![图片](.img/92d8730cd87de8013684693e82f92cd9cb1dbcb42fb7b7e310e6f7b4ccd2d64b.jpg)



Use algorithms to sharpen images.

#### Sharpen Radius

* The greater the value, the greater the sharpening range
#### Alpha

* The greater the value, the greater the sharpening intensity
### Save Image

![图片](.img/53b96393639bef816a39081928bafeb078d45163281e475011a2f55761209b3d.jpg)



Save the image on the web side.

#### Correlation Node

* [Save](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-zU1U 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Preview Image

![图片](.img/5f64a9aa62a17650d7801d6dae2d9fce271fa180277dd45ac881b309a559903a.jpg)



Preview the image on the web side.

blender interface not applicable.

#### Correlation Node

* [Preview](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-3UOO 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Load Image

![图片](.img/59f23ad561ed17ab4986bfc3b7e40585bc3a957305b544d64b792c498698ae0d.jpg)



Load the image on the web side.

blender interface not applicable.

#### Correlation Node

* [Input Image](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-2J6R 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Image Invert

![图片](.img/6ab29e23842e27165a8d64bc500123e774752326ff955ea6bac1c847420483e5.jpg)



Set all colors in the image to invert.

### Image Pad For Outpaint

![图片](.img/1e098231b18dbfc6e4a5d984187546e2e737a7ef9d4f0fbd5040c8cec38087bc.jpg)



Image extension node suitable for supplementary painting.

Image output complement is 0, the original image unchanged; Mask output is 1, the original image is 0.

#### Up, Down, Left, Right

* Extend outward in the specified direction.
## Mask

### Load Image Mask

![图片](.img/9d71a05296ce7e309e3c655ba339e13978fdfac7ad59a854277945de800d0071.jpg)



Load the mask on the web side.

blender interface not applicable.

#### Correlation Node

* [Mask](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-SBvb 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Mask To Image

![图片](.img/a065a868891eec871032c16c41d785daf318ca3ea025eae6a67cbaa2bd512bdb.jpg)



Convert the mask to a image.

###  Image To Mask

![图片](.img/055bed2a2c37811286ff75c840962346db1e272e1f6c458f77d9da523deefb3b.jpg)



Convert the image to a mask according to the specified channel,masks are 0-1 grayscale maps that do not retain color.

### Solid Mask

![图片](.img/a3a4a1c649e62963d04e033ed2b808b5bd4f6a7480f91a1b032d4d9cc635f0cf.jpg)



Generates a solid mask.

#### Value

* Specifies the mask color value.
#### Width And Height

* Specifies the mask size.
### Invert Mask

![图片](.img/95d11dc4ba5e9e40b30c1be26875115a6d3e89c4edeb9891c31e5db749de86a6.jpg)



Invert the mask color value.

The output is (1-value).

### Crop Mask

![图片](.img/85fa799f0f15682fad3ea49090a494c9451050cacff78ac31306bc8ab77e524c.jpg)



Crop the mask.

#### XY

* Specified position,coordinates for the "sampling from" the top left corner of the latent first pixel.
#### Width And Height

* Specifies the size of the mask to crop out.
###  Mask Composite

![图片](.img/edeccc2a8f5201a580bb225038918773dfb77adde929843ad30595eba9b274d1.jpg)



Mix the two masks according to the algorithm.

#### XY

* Specified position,coordinates for the "sampling from" the top left corner of the latent first pixel.
#### Operation

* multiply：target * source
* add：target + source
* substract：target - source
### Feather Mask

![图片](.img/620f369a3b37da921481eeac95b7af406067687707f45e9ed48342eb919e7f01.jpg)



Feather from edge to center.

#### Up, Down, Left ,Right

* The amount of feathering in the specified direction.
#### Special Instructions

* Feathering is feathering from the original color value to 0.
## Test

### VAE Decode Tiled

![图片](.img/03fd51b9eab042cb88e504dca6be1479b66e7b7e4496482ef05df122d482d5d0.jpg)



Similar to <VAE Decode >. It takes longer, has lower quality, and requires less VRAM.

#### Correlation Node

* [VAE Decode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-T9uA 《无限圣杯AI节点(ComfyUI)使用者手册》)
### VAE Encode Tiled

![图片](.img/cc62a62196fd97efb5999107d6bdc50dfb7bef4d08e4ee63961a37f7ca4f3dce.jpg)



Similar to <VAE Encode>. It takes longer, has lower quality, and requires less VRAM.

#### Correlation Node

* [VAE Encode](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-FJ4Q 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Tome Patch Model

![图片](.img/028193e2ba5442da8b73686217be6aa774641814e932c685bbfee45329065b7a.jpg)



Use extra tokens in the "Tome model" to speed up generation.

#### Ratio

* Indicates the ratio of the combined tokens.
### Load Latent

![图片](.img/5513e4bea319f0e5d35b00fc6b6eaba7496afe2f14d5f38c9eac453280969f1d.jpg)



Load the latent space on the web side.

blender interface not applicable.

### Save Latent

![图片](.img/f59e30a354a775ba57f666fadd29f6b34b5337c5b7d815c56970d98679e7b10e.jpg)



Save the latent space on the web side.

## Advanced

## Loader

### **Checkpoint**Loader

![图片](.img/bf4475fcdb0110145114ed9f5d8fedab9668762950a8d087ede01432a1fdb548.jpg)



The node that will load the model, U-net and VAE encoding/decoder from the Safecheckpoint file, and output them as the model, CLIP and VAE, is capable of defining the configuration file of the model.

This node is not recommended unless you understand the model you are working with.

### Diffusers Loader

![图片](.img/f4def1ad3e2485bfe94ef51f3820630008cfc849714d0a7de9c3013cd35a92b7.jpg)



Ability to load diffusers models.

## Preprocessor

### Edge Line

### Canny Edge Preprocessor

![图片](.img/f35faf5547c28ac40d4e22e9f323b468b16e11a1692cf990761c0ab3d4578829.jpg)



The Canny algorithm is used to process the image.

#### Low And High Threshold

* Low Threshold : Control the weak edge detection threshold
* High Threshold : Control the strong edge detection threshold
#### L2 Gradient

* Select whether to use L2 operation.
* L2 is more accurate than L1, but it reduces the speed of calculation.
### M-LSD Preprocessor

![图片](.img/c493b8a8d49850902ba6163f76a0dec1cd2d26b11b6b90e498aad7cd078ade56.jpg)



Using the M - LSD algorithm to process the image.

#### Score Threshold

* Control the threshold of detection lines. Lines with confidence lower than the threshold will not be detected as edges
#### Distance Threshold

* Control the threshold of line distance. When the distance between lines is lower than the threshold, it will be merged
### HED Preprocessor

![图片](.img/abe1e8b2cfb2c7dbc9389af5024e33f0ee55547d047b4000dddabd7cec239721.jpg)



Use HED algorithm to process images.

#### Version

* Selection algorithm version
#### Safe

* Choose whether to increase the stability of the line, specifically for clearer lines
### Scribble Preprocessor

![图片](.img/2ac878e3dbed4c75598bf5d46672151eb27b8395a3205e7dedff2764c128bf5c.jpg)



Use Scribble algorithm to process images.

### FakeScribble Preprocessor

![图片](.img/8d7bfe21898e2a0d35d48ac70995a253c81742df09ab3c146ed68c52276fb799.jpg)



Use FakeScribble algorithm to process images.

### Binary Preprocessor

![图片](.img/b601d421b8491005ab52e017775232a5c3b815c2c2c72671a168800646199576.jpg)



Use Binary algorithm to process images.

#### Threshold

* Pixels with a color value above the threshold are treated as 1, and pixels with a color value below the threshold are treated as 0
* When the threshold is 0, the effect is the same as 255
### PiDiNet Preprocessor

![图片](.img/2054231e4f48216cbdd786213b62fbca0a80122a1405c4a578d7f32ed380211d.jpg)



Use PiDiNet algorithm to process images.

#### Increase Stability

* Choose whether to increase the stability of the line, specifically for clearer lines.
### Normal Depth Map

### Midas-DepthMap Preprocessor

![图片](.img/f93ef4e800eafc1274d4e48be068d26983573d90d404ff61848fee2258500e68.jpg)



Using Midas DepthMap algorithm processing image.

#### A

* The Angle of inclination of the depth projection onto the image
#### Background Threshold

* Specifies the threshold for removing the background
#### Correlation Node

* [Leres-DepthMap Preprocessor](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-ag5w 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Zoe-DepthMap Preprocessor](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-1jyt 《无限圣杯AI节点(ComfyUI)使用者手册》)
### MiDaS-NormalMap Preprocessor

## ![图片](.img/9c1741a7597b58c8638a0024abfd43f38e614b84c72845a48b79b69f6c1b1cff.jpg)



Using Midas NormalMap algorithm processing image.

#### A

* Specifies the rotation Angle of the normal graph
#### Background Threshold

* Specifies the threshold for removing the background
#### Correlation Node

* [BAE-NormalMap Preprocessor](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-SAg2 《无限圣杯AI节点(ComfyUI)使用者手册》)
### LeRes-DepthMap Preprocessor

## ![图片](.img/b088a22485874f818c36f1bf34f46d766c538ab2f07f989dab9bddd435edac5e.jpg)



Using LeRes DepthMap algorithm processing image.

#### Removal Nearest

* Specifies the threshold at which the identified depth nearest is removed, as if the portion larger than this value is replaced by 1.
#### Remove Background

* Specifies the threshold for removing the recognized depth background, as if the parts less than this value are replaced by 0.
#### Correlation Node

* [Midas-DepthMap Preprocessor](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-5J2z 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Zoe-DepthMap Preprocessor](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-1jyt 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Zoe-DepthMap Preprocessor

## ![图片](.img/02060f6a6f478126488fb5849870062b61364be48750220c57da8ef85da66d84.jpg)



Using Zoe DepthMap algorithm processing image.

#### Correlation Node

* [Midas-DepthMap Preprocessor](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-5J2z 《无限圣杯AI节点(ComfyUI)使用者手册》)
* [Leres-DepthMap Preprocessor](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-ag5w 《无限圣杯AI节点(ComfyUI)使用者手册》)
### BAE-NormalMap Preprocessor

![图片](.img/5a0e83a1410e01c1b766b2b618bbb9e8a35212539b9cbec43e415f6919682d01.jpg)



Using BAE NormalMap algorithm processing image.

#### Correlation Node

* [Midas-NormalMap Preprocessor](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-eWIz 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Pose

### Openpose Preprocessor

![图片](.img/90fa759fb5b51d5ea4b71ff0dbcd53d7cd39f6d22d467fe24a6c14807b800778.jpg)



Using Openpose algorithm processing image.

#### Detection

* Select whether to detect the corresponding part
#### Version

* Selection algorithm version
#### Correlation Node

* [MediaPipe-HandPose Preprocessor](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-IWSt 《无限圣杯AI节点(ComfyUI)使用者手册》)
### MediaPipe-HandPose Preprocessor

![图片](.img/20433aa5ce0aaba64245e68b3c4cbe4d90c3d115bc142e1c18a0f26a98a0d848.jpg)



Using MediaPipe HandPose algorithm processing image.

### Detection Posture

* Select whether to detect torso posture.
### Detecting Hand

* Choose whether to test the hand.
#### Correlation Node

* [Openpose Preprocessor](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-18Qf 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Semantic Segmentation

### SemSeg Preprocessor

![图片](.img/b0e23941bcb91e8075b9f2d637d0e195e711a6a527ce2ddc34b0dc1a7ead3a9a.jpg)



Using SemSeg algorithm processing image.

### Face Mesh

### MediaPipe-FaceMesh Preprocessor

![图片](.img/c3ec9b37c735ff93a5720784b5e11cb0c487108dba34b750b919a1f96ee28e7e.jpg)



Using MediaPipe HandPose algorithm processing image.

#### Maximum Faces

* Specifies the maximum number of faces to detect.
#### Minimum Confidence

* Specifies the minimum threshold for determining the face.
### Color Style

### Color Preprocessor

![图片](.img/a6b29d4019ac4f49d6dd56952dafcead5f5beefeee069d109124292c41a79675.jpg)



Using Color algorithm processing image.

### Tile Preprcessor

![图片](.img/e36d0a0dcfa5412b2281b89ac7b137ccda4cbc3d3e8c56c96fb0594c8618f198.jpg)



## Blender

### Input

![图片](.img/4b4899a9d97add3c4e052cba9bbae2f680425e243d47813a1e37fa13c8782082.jpg)



Load images in blender interface.

Not applicable to the web side.

#### Input Mode

* Input : Directly input the picture and process it into a recognizable form
* Render: The input image may contain render elements or transparent channels that require secondary preprocessing
#### Correlation Node

* [Load Image](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-XDch 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Mask

![图片](.img/40b37b4401d446811b352e0c3d73f4212b627dbac880377f2b56f9c04ba65725.jpg)



Load the mask in blender interface.

Not applicable to the web side.

#### Special Instructions

* Objects in the scene can be selected to enter the mask directly
#### Correlation Node

* [Load Image Mask](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-CHEo 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Save

![图片](.img/96f2a29174ae85d0b9784a3325d3cc567f3d5bba1113a03827071d8a81e6535d.jpg)



Save the image in blender interface.

Not applicable to the web side.

#### Correlation Node

* [Save](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-fLas 《无限圣杯AI节点(ComfyUI)使用者手册》)
### Preview

![图片](.img/b8820bfbe437b1b3959d15c33b215a3d7b1699532c22e7fa3200305bfc00f473.jpg)



Preview the image in blender interface.

Not applicable to the web side.

#### Special Instructions

* Preview images do not contain image metadata
* The preview folder is emptied at each startup
#### Correlation Node

* [Preview](https://shimo.im/docs/Ee32m0w80rfLp4A2#anchor-djAA 《无限圣杯AI节点(ComfyUI)使用者手册》)
