from dataclasses import dataclass, field
import io
import os
from model_resolver.item_model.item import Item
from model_resolver.minecraft_model import (
    MinecraftModel,
    resolve_model,
)
from typing import ClassVar, Generator
from rich import print  # noqa
from model_resolver.tasks.base import Task, RenderError
from model_resolver.tasks.generic_render import GenericModelRenderTask
from model_resolver.item_model.tint_source import TintSource
from PIL import Image
from beet import BinaryFileBase, NamespaceFileScope


@dataclass(kw_only=True)
class ModelRenderTask(GenericModelRenderTask):
    model: MinecraftModel
    tints: list[TintSource] = field(default_factory=list)
    item: Item = field(default_factory=lambda: Item(id="do_not_use"))

    def resolve(self) -> Generator[Task, None, None]:
        yield self

    def run(self):
        self.render_model(self.model, self.tints)

    def flush(self):
        super().flush()
        self.model = MinecraftModel()
        self.tints = []
        self.item = Item(id="do_not_use")


@dataclass(kw_only=True)
class AnimatedResultTask(Task):
    tasks: list[Task] = field(default_factory=list)

    def save(self, _: Image.Image):
        # create a gif from the images
        images = []
        for task in self.tasks:
            img = task.saved_img
            if img is None:
                continue
            images.append((img, task.path_ctx, task.path_save))

        if self.path_ctx:
            images.sort(key=lambda x: int(x[1].split("/")[-1].split("_")[0]))
            images_duration = []
            for x in images:
                duration = int(x[1].split("/")[-1].split("_")[1])
                for i in range(duration):
                    images_duration.append(x[0])

            data = io.BytesIO()
            res = images_duration[0]
            res.save(
                data,
                format="gif",
                append_images=images_duration[1:],
                save_all=True,
                duration=50,
                loop=0,
                disposal=2,
            )
            if not TextureGif in self.getter._ctx.assets.extend_namespace:
                self.getter._ctx.assets.extend_namespace.append(TextureGif)
            self.getter._ctx.assets[TextureGif][self.path_ctx] = TextureGif(
                data.getvalue()
            )
        elif self.path_save:
            images.sort(key=lambda x: int(x[2].name.split("_")[0]))
            images_duration = []
            for x in images:
                duration = int(x[2].name.split("_")[1])
                for i in range(duration):
                    images_duration.append(x[0])
            res = images_duration[0]
            os.makedirs(self.path_save.parent, exist_ok=True)
            res.save(
                self.path_save,
                format="gif",
                append_images=images_duration[1:],
                save_all=True,
                duration=50,
                loop=0,
                disposal=2,
            )
        self.flush()
        for task in self.tasks:
            task.flush()


@dataclass(eq=False, repr=False)
class TextureGif(BinaryFileBase):
    """Class representing a texture."""

    scope: ClassVar[NamespaceFileScope] = ("textures",)
    extension: ClassVar[str] = ".gif"


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
            self.animated_as_gif = False
            yield self
            return
        texture_path_to_frames, texture_interpolate = self.get_texture_path_to_frames(
            model
        )
        if len(texture_path_to_frames) == 0:
            self.animated_as_gif = False
            yield self
            return

        ticks_grouped = self.get_tick_grouped(
            texture_path_to_frames, texture_interpolate
        )

        tasks = []

        for i, tick in enumerate(ticks_grouped):
            # get the images for the tick
            images = self.get_images(tick, texture_interpolate)
            textures = self.get_textures(model, images)
            new_model = model.model_copy()
            new_model.textures = textures
            if self.path_save:
                new_path_save = self.path_save / f"{i:03}_{tick.duration}.png"
            else:
                new_path_save = None
            if self.path_ctx:
                new_path_ctx = self.path_ctx + f"/{i:03}_{tick.duration}"
            else:
                new_path_ctx = None
            task = ModelRenderTask(
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
                animated_as_gif=self.animated_as_gif,
                render_size=self.render_size,
                zoom=self.zoom,
                ensure_params=self.ensure_params,
                dynamic_textures=self.dynamic_textures,
            )
            yield task
            tasks.append(task)

        if self.animated_as_gif:
            yield AnimatedResultTask(
                tasks=tasks,
                path_ctx=self.path_ctx,
                path_save=self.path_save,
                getter=self.getter,
                render_size=self.render_size,
                zoom=self.zoom,
            )
