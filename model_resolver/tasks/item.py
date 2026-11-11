from dataclasses import dataclass

from typing import ClassVar, Optional
from model_resolver.tasks.model import AnimatedResultTask
from model_resolver.minecraft_model import (
    MinecraftModel,
)
from model_resolver.item_model.model import ItemModel
from model_resolver.item_model.glint import GlintStyle, has_foil
from model_resolver.item_model.transformation import Transformation
from model_resolver.item_model.tint_source import TintSource
from typing import Generator, Sequence
from model_resolver.tasks.generic_render import Animation, GenericModelRenderTask
from model_resolver.tasks.base import Task, RenderError
from model_resolver.utils import resolve_key


type ResolvedModel = tuple[MinecraftModel, list[TintSource], Optional[Transformation], Optional[GlintStyle]]


@dataclass(kw_only=True)
class ItemModelModelRenderTask(GenericModelRenderTask):
    vanilla_display_defaults: ClassVar[bool] = True
    models: Sequence[ResolvedModel]
    source: Optional[str] = None

    def resolve(self) -> Generator[Task, None, None]:
        yield self

    def run(self):
        for model, tints, transformation, glint in self.models:
            self.render_model(model, tints, self.source, transformation, glint)


@dataclass(kw_only=True)
class ItemRenderTask(GenericModelRenderTask):
    vanilla_display_defaults: ClassVar[bool] = True

    def get_parsed_item_model(self) -> ItemModel:
        assert self.item
        assert self.item.__resolved__, f"Item {self.item.id} is not resolved"
        assert self.item.components, f"Item {self.item.id} has no components"
        assert (
            "minecraft:item_model" in self.item.components
        ), f"Item {self.item.id} has no item model"
        item_model_key = self.item.components["minecraft:item_model"]
        if not item_model_key:
            raise RenderError(f"Item {self.item} does not have a model")
        item_model_key = resolve_key(item_model_key)
        if item_model_key in self.getter.assets.item_models:
            item_model = self.getter.assets.item_models[item_model_key]
        else:
            raise RenderError(f"Item model {item_model_key} not found")
        return ItemModel.model_validate(item_model.data)

    def run(self):
        parsed_item_model = self.get_parsed_item_model()
        for model in parsed_item_model.resolve(self.getter, self.item):
            model_def = model.get_model(self.getter, self.item).bake()
            self.render_model(
                model_def,
                model.get_tints(self.getter, self.item),
                source=str(self.item),
                transformation=model.transformation,
                glint=model.glint(),
            )

    def resolve(self) -> Generator[Task, None, None]:
        parsed_item_model = self.get_parsed_item_model()
        item_model_models = list(parsed_item_model.resolve(self.getter, self.item))

        animation = Animation(
            textures=[
                model.get_model(self.getter, self.item).bake().textures
                for model in item_model_models
            ],
            getter=self.getter,
            animation_framerate=self.animation_framerate,
            source=str(self.item),
            glint=has_foil(self.item) and any(model.glint() for model in item_model_models),
        )
        if not animation.is_animated:
            self.animation_mode = "multi_files"
            yield self
            return

        tasks = []

        frames = list(animation.get_frames())
        animated_path_padding = max(
            self.animated_path_padding, len(str(len(frames) - 1))
        )

        for i, (images, duration, tick) in frames:
            # get the images for the tick
            models: list[ResolvedModel] = []
            for model in item_model_models:
                model_def = model.get_model(self.getter, self.item).bake()
                model_def = model_def.model_copy()
                textures = self.get_textures(model_def, images)
                model_def.textures = textures
                models.append(
                    (
                        model_def,
                        model.get_tints(self.getter, self.item),
                        model.transformation,
                        model.glint(),
                    )
                )

            if self.path_save:
                new_path_save = self.path_save / "{i:0{animated_path_padding}}_{duration}.png".format(
                    i = i,
                    duration = duration,
                    animated_path_padding = animated_path_padding
                )
            else:
                new_path_save = None
            if self.path_ctx:
                new_path_ctx = self.path_ctx + "/{i:0{animated_path_padding}}_{duration}".format(
                    i = i,
                    duration = duration,
                    animated_path_padding = animated_path_padding
                )
            else:
                new_path_ctx = None
            if self.animation_mode == "one_file":
                new_path_save = self.path_save
                new_path_ctx = self.path_ctx

            task = ItemModelModelRenderTask(
                getter=self.getter,
                models=models,
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
                source=str(self.item),
                animation_duration=duration,
                glint_tick=tick,
            )
            yield task
            tasks.append(task)

            if self.animation_mode == "one_file":
                break
        self.tasks = tasks
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
