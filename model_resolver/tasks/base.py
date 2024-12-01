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


class RenderError(Exception):
    pass


@dataclass(kw_only=True)
class Task:
    ctx: Context
    vanilla: Vanilla
    path_ctx: Optional[str] = None
    path_save: Optional[Path] = None
    render_size: int = DEFAULT_RENDER_SIZE
    zoom: float = 8

    ensure_params: bool = False
    dynamic_textures: dict[str, Image.Image] = field(default_factory=dict)

    def change_params(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(
            self.zoom,
            -self.zoom,
            -self.zoom,
            self.zoom,
            self.render_size,
            -self.render_size,
        )
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def resolve(self) -> Generator["Task", None, None]:
        yield self

    def run(self):
        pass

    def save(self, img: Image.Image):
        if self.path_ctx:
            self.ctx.assets.textures[self.path_ctx] = Texture(img)
        elif self.path_save:
            img.save(self.path_save)
