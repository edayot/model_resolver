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
from model_resolver.tasks.generic_render import Animation, GenericModelRenderTask
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
        # create a webp from the images
        images = []
        for task in self.tasks:
            img = task.saved_img
            if img is None:
                continue
            images.append((img, task.path_ctx, task.path_save))
        duration_ms = 1000 / self.animation_framerate

        if self.path_ctx:
            images.sort(key=lambda x: int(x[1].split("/")[-1].split("_")[0]))
            images_duration: list[Image.Image] = []
            for x in images:
                duration = int(x[1].split("/")[-1].split("_")[1])
                for i in range(duration):
                    images_duration.append(x[0])

            data = io.BytesIO()
            res = images_duration[0]
            res.save(
                data,
                format="webp",
                append_images=images_duration[1:],
                save_all=True,
                duration=duration_ms,
                loop=0,
                disposal=2,
                lossless=True,
            )
            if not TextureWebP in self.getter._ctx.assets.extend_namespace:
                self.getter._ctx.assets.extend_namespace.append(TextureWebP)
            self.getter._ctx.assets[TextureWebP][self.path_ctx] = TextureWebP(
                data.getvalue()
            )
        elif self.path_save:
            images.sort(key=lambda x: int(x[2].name.split("_")[0]))
            images_duration: list[Image.Image] = []
            for x in images:
                duration = int(x[2].name.split("_")[1])
                for i in range(duration):
                    images_duration.append(x[0])

            res = images_duration[0]
            os.makedirs(self.path_save.parent, exist_ok=True)
            res.save(
                self.path_save,
                format="webp",
                append_images=images_duration[1:],
                save_all=True,
                duration=duration_ms,
                loop=0,
                disposal=2,
                lossless=True,
            )
        self.flush()
        for task in self.tasks:
            task.flush()


@dataclass(eq=False, repr=False)
class TextureWebP(BinaryFileBase):
    """Class representing a texture."""

    scope: ClassVar[NamespaceFileScope] = ("textures",)
    extension: ClassVar[str] = ".webp"


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
            self.animation_mode = "multi_files"
            yield self
            return

        animation = Animation(
            textures=[model.textures],
            getter=self.getter,
            animation_framerate=self.animation_framerate,
        )
        if not animation.is_animated:
            self.animation_mode = "multi_files"
            yield self
            return

        tasks = []

        for i, (images, duration) in animation.get_frames():
            # get the images for the tick
            textures = self.get_textures(model, images)
            new_model = model.model_copy()
            new_model.textures = textures
            if self.path_save:
                new_path_save = self.path_save / f"{i:03}_{duration}.png"
            else:
                new_path_save = None
            if self.path_ctx:
                new_path_ctx = self.path_ctx + f"/{i:03}_{duration}"
            else:
                new_path_ctx = None
            if self.animation_mode == "one_file":
                new_path_save = self.path_save
                new_path_ctx = self.path_ctx

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
                animation_mode=self.animation_mode,
                render_size=self.render_size,
                zoom=self.zoom,
                ensure_params=self.ensure_params,
                dynamic_textures=self.dynamic_textures,
            )
            yield task
            tasks.append(task)
            if self.animation_mode == "one_file":
                break

        if self.animation_mode == "webp":
            yield AnimatedResultTask(
                tasks=tasks,
                path_ctx=self.path_ctx,
                path_save=self.path_save,
                getter=self.getter,
                render_size=self.render_size,
                zoom=self.zoom,
                animation_mode=self.animation_mode,
                animation_framerate=self.animation_framerate,
            )
