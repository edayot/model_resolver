from dataclasses import dataclass, field
import re
from model_resolver.item_model.item import Item
from model_resolver.utils import resolve_key
from model_resolver.minecraft_model import (
    MinecraftModel,
    resolve_model,
)
from typing import Generator
from rich import print  # noqa
from model_resolver.tasks.base import Task, RenderError
from model_resolver.tasks.generic_render import GenericModelRenderTask
from model_resolver.item_model.tint_source import TintSource
from PIL import Image
from beet import Model as BeetModel


@dataclass(kw_only=True)
class ModelRenderTask(GenericModelRenderTask):
    model: MinecraftModel
    tints: list[TintSource] = field(default_factory=list)
    item: Item = field(default_factory=lambda: Item(id="do_not_use"))

    def resolve(self) -> Generator[Task, None, None]:
        yield self

    def run(self):
        self.render_model(self.model, self.tints)


@dataclass(kw_only=True)
class ModelPathRenderTask(GenericModelRenderTask):
    model: str
    tints: list[TintSource] = field(default_factory=list)
    item: Item = field(default_factory=lambda: Item(id="do_not_use"))

    def run(self):
        if len(self.tints) > 0:
            assert self.item, "Tints are only available if you provide an item"
        model = self.get_parsed_model()
        self.render_model(model, self.tints)

    def get_parsed_model(self) -> MinecraftModel:
        model = self.getter.assets.models.get(self.model)
        if not model:
            raise RenderError(f"Model {self.model} not found")
        return MinecraftModel.model_validate(
            resolve_model(model.data, self.getter)
        ).bake()

    def resolve(self) -> Generator[Task, None, None]:
        model = self.get_parsed_model()
        if not model.textures:
            yield self
            return
        texture_path_to_frames = self.get_texture_path_to_frames(model)
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
            textures = {}
            for key, value in model.textures.items():
                if isinstance(value, Image.Image):
                    raise RenderError(f"WTF is going on")
                if resolve_key(value) in [resolve_key(k) for k in images.keys()]:
                    textures[key] = images[value]
                else:
                    textures[key] = value
            new_model = model.model_copy()
            new_model.textures = textures
            if self.path_save:
                new_path_save = self.path_save / f"{i}_{tick['duration']}.png"
            else:
                new_path_save = None
            if self.path_ctx:
                new_path_ctx = self.path_ctx + f"/{i}_{tick['duration']}"
            else:
                new_path_ctx = None
            yield ModelRenderTask(
                getter=self.getter,
                model=new_model,
                tints=self.tints,
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
