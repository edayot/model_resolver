import io
from OpenGL.GL import *  # type: ignore
from OpenGL.GLUT import *  # type: ignore
from OpenGL.GLU import *  # type: ignore

from beet import Texture
from dataclasses import dataclass, field
from model_resolver.utils import (
    DEFAULT_RENDER_SIZE,
    PackGetterV2,
)
from typing import Literal, Optional, Generator
from pathlib import Path
from PIL import Image


class RenderError(Exception):
    pass


type AnimationType = Literal[
    "multi_files",
    "webp",
    "one_file",
]


@dataclass(kw_only=True)
class Task:
    getter: PackGetterV2
    path_ctx: Optional[str] = None
    path_save: Optional[Path] = None
    render_size: int = DEFAULT_RENDER_SIZE
    zoom: float = 8

    animation_mode: AnimationType = "multi_files"
    animation_framerate: int = 20
    saved_img: Optional[Image.Image] = None

    @property
    def duration_coef(self):
        if self.animation_framerate % 20 != 0 and self.animation_framerate > 0:
            raise TypeError(f"animation_frame must be a positive multiple of 20")
        return self.animation_framerate // 20

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
        self.animation_mode = "multi_files"
        yield self

    def run(self):
        pass

    def flush(self):
        """
        Function called after the save function.
        meant to be overridden by subclasses to free up resources.
        """
        self.saved_img = None

    def save(self, img: Image.Image):
        if self.path_ctx and self.animation_mode in ["one_file", "multi_files"]:
            data = io.BytesIO()
            img.save(data, format="png")
            self.getter._ctx.assets.textures[self.path_ctx] = Texture(data.getvalue())
        elif self.path_save and self.animation_mode in ["one_file", "multi_files"]:
            os.makedirs(self.path_save.parent, exist_ok=True)
            img.save(self.path_save)
        elif self.animation_mode == "webp":
            self.saved_img = img
            return
        self.flush()
