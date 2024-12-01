from functools import cached_property
import random
from OpenGL.GL import *  # type: ignore
from OpenGL.GLUT import *  # type: ignore
from OpenGL.GLU import *  # type: ignore

from beet import Context, Texture, Atlas, run_beet
from dataclasses import dataclass, field
from model_resolver.item_model.item import Item
from model_resolver.utils import (
    LightOptions,
    ModelResolverOptions,
    resolve_key,
    DEFAULT_RENDER_SIZE,
)
from model_resolver.vanilla import Vanilla
from model_resolver.minecraft_model import (
    DisplayOptionModel,
    ItemModelNamespace,
    MinecraftModel,
    ElementModel,
    RotationModel,
    FaceModel,
    resolve_model,
)
from model_resolver.item_model.model import ItemModel
from model_resolver.item_model.tint_source import TintSource
from typing import Optional, Generator
from pathlib import Path
from PIL import Image
from model_resolver.tasks.generic_render import GenericModelRenderTask
from model_resolver.tasks.base import Task, RenderError


@dataclass(kw_only=True)
class ItemModelModelRenderTask(GenericModelRenderTask):
    models: list[tuple[MinecraftModel, list[TintSource]]]

    def resolve(self) -> Generator[Task, None, None]:
        yield self

    def run(self):
        for model, tints in self.models:
            self.render_model(model, tints)


@dataclass(kw_only=True)
class ItemRenderTask(GenericModelRenderTask):

    def get_parsed_item_model(self) -> ItemModel:
        assert self.item
        item_model_key = self.item.components["minecraft:item_model"]
        if not item_model_key:
            raise RenderError(f"Item {self.item} does not have a model")
        if item_model_key in self.ctx.assets[ItemModelNamespace]:
            item_model = self.ctx.assets[ItemModelNamespace][item_model_key]
        elif item_model_key in self.vanilla.assets[ItemModelNamespace]:
            item_model = self.vanilla.assets[ItemModelNamespace][item_model_key]
        else:
            raise RenderError(f"Item model {item_model_key} not found")
        return ItemModel.model_validate(item_model.data)

    def run(self):
        parsed_item_model = self.get_parsed_item_model()
        for model in parsed_item_model.resolve(self.ctx, self.vanilla, self.item):
            model_def = model.get_model(self.ctx, self.vanilla, self.item).bake()
            self.render_model(model_def, model.tints)

    def resolve(self) -> Generator[Task, None, None]:
        parsed_item_model = self.get_parsed_item_model()
        item_model_models = list(
            parsed_item_model.resolve(self.ctx, self.vanilla, self.item)
        )
        texture_path_to_frames = {}
        for model in item_model_models:
            model_def = model.get_model(self.ctx, self.vanilla, self.item).bake()
            texture_path_to_frames.update(self.get_texture_path_to_frames(model_def))
        if len(texture_path_to_frames) == 0:
            yield self
            return
        ticks_grouped = self.get_tick_grouped(texture_path_to_frames)

        for i, tick in enumerate(ticks_grouped):
            # get the images for the tick
            images = {}
            for texture_path, index in tick["tick"].items():
                texture = self.get_texture(texture_path)
                if not texture:
                    raise RenderError(f"WTF")
                img: Image.Image = texture.image
                cropped = img.crop(
                    (0, index * img.width, img.width, (index + 1) * img.width)
                )
                images[texture_path] = cropped

            models: list[tuple[MinecraftModel, list[TintSource]]] = []
            for model in item_model_models:
                model_def = model.get_model(self.ctx, self.vanilla, self.item).bake()
                model_def = model_def.model_copy()
                textures = {}
                for key, value in model_def.textures.items():
                    if isinstance(value, Image.Image):
                        raise RenderError(f"WTF is going on")
                    if resolve_key(value) in images:
                        textures[key] = images[value]
                    else:
                        textures[key] = value
                model_def.textures = textures
                models.append((model_def, model.tints))

            if self.path_save:
                new_path_save = self.path_save / f"{i}_{tick['duration']}.png"
            else:
                new_path_save = None
            if self.path_ctx:
                new_path_ctx = self.path_ctx + f"/{i}_{tick['duration']}"
            else:
                new_path_ctx = None
            yield ItemModelModelRenderTask(
                ctx=self.ctx,
                vanilla=self.vanilla,
                models=models,
                item=self.item,
                do_rotate_camera=self.do_rotate_camera,
                offset=self.offset,
                center_offset=self.center_offset,
                additional_rotations=self.additional_rotations,
                path_ctx=new_path_ctx,
                path_save=new_path_save,
                render_size=self.render_size,
                zoom=self.zoom,
                ensure_params=self.ensure_params,
                dynamic_textures=self.dynamic_textures,
            )
