# Custom Item Resource Pack

This resource pack is a test to create custom items in 3D using custom model data in the latest snapshot 24w45a.

## Installation

1. Download the resource pack.
2. Place the resource pack in your Minecraft `resourcepacks` folder.
3. Enable the resource pack in Minecraft settings.

## Usage

You can open a GUI by opening `Custom Item/assets/custom_item/python/gui.py` to create your model.

You can also convert a Minecraft model using `Custom Item/assets/custom_item/python/conversion.py`, but you need to enter the texture and color manually in the Python code. An example, `egg.json`, is provided for testing purposes.

Example:
![Example Image 1](https://github.com/user-attachments/assets/1925cfef-a60f-40c3-b854-711f94e2e056)
![Example Image 2](https://github.com/user-attachments/assets/cc1834fd-995b-40b5-985b-b21a2d63b5b4)

## How It Works

There is one model composed of 4096 models (16x16x16), each one being a pixel cube that can be activated/deactivated and change color depending on a custom model data value.


