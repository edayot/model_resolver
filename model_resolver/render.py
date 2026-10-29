from OpenGL.GL import *  # pyright: ignore[reportWildcardImportFromLibrary]
from OpenGL.GLUT import *  # pyright: ignore[reportWildcardImportFromLibrary]
from OpenGL.GLU import *  # pyright: ignore[reportWildcardImportFromLibrary]
from model_resolver.minecraft_model import DisplayOptionModel, MinecraftModel
from model_resolver.my_glut_init import glutInit

import math
import re
import numpy as np
from beet import Context, Atlas
from dataclasses import dataclass, field
from model_resolver.item_model.item import Item
from model_resolver.tasks.item import ItemRenderTask
from model_resolver.tasks.model import ModelPathRenderTask, ModelRenderTask
from model_resolver.tasks.structure import StructureRenderTask
from model_resolver.utils import (
    LightOptions,
    ModelResolverOptions,
    resolve_key,
    DEFAULT_RENDER_SIZE,
    log,
)
from model_resolver.pack_getter import PackGetter
from typing import Any, Literal, Optional, TypedDict
from pathlib import Path
from PIL import Image

from model_resolver.tasks.base import AnimationType, Task, RenderError
from model_resolver.tasks.generic_render import GlTextures, set_default_blend


def unpremultiply(image: Image.Image) -> Image.Image:
    """The framebuffer holds colors multiplied by their alpha (see set_default_blend),
    PNGs store them straight."""
    data = np.asarray(image.convert("RGBA")).astype(np.float32)
    alpha = data[..., 3:4]
    rgb = np.where(alpha > 0, data[..., :3] * 255 / np.maximum(alpha, 1), 0)
    data[..., :3] = np.clip(np.floor(rgb + 0.5), 0, 255)
    return Image.fromarray(data.astype(np.uint8), "RGBA")


class AtlasDict(TypedDict, total=False):
    type: str
    textures: list[str]
    palette_key: str
    permutations: dict[str, str]
    separator: str
    resource: str
    sprite: str
    source: str
    prefix: str
    pattern: dict[str, str]


class AppendList[T: Any](list[T]):
    def append[U](self, object: U) -> U:
        super().append(object) # pyright: ignore[reportArgumentType]
        return object


@dataclass
class Render:
    ctx: Context

    tasks: AppendList[Task] = field(default_factory=AppendList)
    tasks_index: int = 0
    light: LightOptions = field(default_factory=LightOptions)
    dynamic_textures: dict[str, Image.Image] = field(default_factory=dict)
    default_render_size: int = DEFAULT_RENDER_SIZE
    default_animated_path_padding: int = 3
    random_seed: int = 143221

    def __post_init__(self):
        self.getter = PackGetter.from_context(self.ctx)
        if self.getter.opts.render_size is not None:
            self.default_render_size = self.getter.opts.render_size

    def __repr__(self):
        return f"<Render of {len(self.tasks)} tasks>"

    @property
    def current_task(self):
        return self.tasks[self.tasks_index]

    def add_item_task(
        self,
        item: Item,
        *,
        path_ctx: Optional[str] = None,
        path_save: Optional[Path] = None,
        render_size: Optional[int] = None,
        animation_mode: AnimationType = "multi_files",
        animation_framerate: int = 20,
        animated_path_padding: Optional[int] = None,
        display_context: Optional[str] = None,
    ):
        """Render an item. `display_context` is where it is shown (gui by default, fixed,
        ground, head, thirdperson_righthand...), it selects the display transform and the
        value of `select display_context`."""
        if render_size is None:
            render_size = self.default_render_size
        if isinstance(path_save, str):
            path_save = Path(path_save)
        if animated_path_padding is None:
            animated_path_padding = self.default_animated_path_padding
        if display_context is not None:
            # a copy: the same Item can be rendered in several contexts
            item = item.model_copy(update={"display_context": display_context})
        return self.tasks.append(
            ItemRenderTask(
                getter=self.getter,
                item=item.fill(self.ctx),
                path_ctx=path_ctx,
                path_save=path_save,
                render_size=render_size,
                animation_mode=animation_mode,
                animation_framerate=animation_framerate,
                animated_path_padding=animated_path_padding,
            )
        )

    def add_model_task(
        self,
        model: str,
        *,
        path_ctx: Optional[str] = None,
        path_save: Optional[Path | str] = None,
        render_size: Optional[int] = None,
        animation_mode: AnimationType = "multi_files",
        animation_framerate: int = 20,
        animated_path_padding: Optional[int] = None,
        biome: str | dict[str, Any] = "minecraft:plains",
    ):
        """Render a model on its own. The model of a block is tinted like that block in
        `biome` (an id or a worldgen/biome object)."""
        if render_size is None:
            render_size = self.default_render_size
        if isinstance(path_save, str):
            path_save = Path(path_save)
        if animated_path_padding is None:
            animated_path_padding = self.default_animated_path_padding
        return self.tasks.append(
            ModelPathRenderTask(
                getter=self.getter,
                model=model,
                biome=biome,
                path_ctx=path_ctx,
                path_save=path_save,
                render_size=render_size,
                animation_mode=animation_mode,
                animation_framerate=animation_framerate,
                animated_path_padding=animated_path_padding,
            )
        )

    def add_model_dict_task(
        self,
        model: dict[str, Any] | MinecraftModel,
        *,
        path_ctx: Optional[str] = None,
        path_save: Optional[Path | str] = None,
        render_size: Optional[int] = None,
        animation_mode: AnimationType = "multi_files",
        animation_framerate: int = 20,
        animated_path_padding: Optional[int] = None,
    ):
        if render_size is None:
            render_size = self.default_render_size
        if isinstance(path_save, str):
            path_save = Path(path_save)
        if isinstance(model, dict):
            model = MinecraftModel.model_validate(model)
        if animated_path_padding is None:
            animated_path_padding = self.default_animated_path_padding
        return self.tasks.append(
            ModelRenderTask(
                getter=self.getter,
                model=model,
                path_ctx=path_ctx,
                path_save=path_save,
                render_size=render_size,
                animation_mode=animation_mode,
                animation_framerate=animation_framerate,
                animated_path_padding=animated_path_padding,
            )
        )

    def add_structure_task(
        self,
        structure: str,
        *,
        path_ctx: Optional[str] = None,
        path_save: Optional[Path | str] = None,
        render_size: Optional[int] = None,
        animation_mode: AnimationType = "one_file",
        animation_framerate: int = 20,
        display_option: Optional[DisplayOptionModel | dict[str, Any]] = None,
        animated_path_padding: Optional[int] = None,
        biome: str | dict[str, Any] = "minecraft:plains",
    ):
        """Render a structure. `biome` (an id, or a worldgen/biome object) colors its grass,
        foliage and water."""
        kwargs: dict[Literal["display_option"], DisplayOptionModel] = {}
        if render_size is None:
            render_size = self.default_render_size
        if isinstance(path_save, str):
            path_save = Path(path_save)
        if isinstance(display_option, dict):
            kwargs["display_option"] = DisplayOptionModel(**display_option)
        elif isinstance(display_option, DisplayOptionModel):
            kwargs["display_option"] = display_option
        if animated_path_padding is None:
            animated_path_padding = self.default_animated_path_padding
        return self.tasks.append(
            StructureRenderTask(
                getter=self.getter,
                structure_key=structure,
                path_ctx=path_ctx,
                path_save=path_save,
                render_size=render_size,
                random_seed=self.random_seed,
                animation_mode=animation_mode,
                animation_framerate=animation_framerate,
                animated_path_padding=animated_path_padding,
                biome=biome,
                **kwargs,
            )
        )

    def resolve_dynamic_textures(self):
        log.info(f"Resolving dynamic textures")
        # first, resolve all vanilla altas
        cache = self.ctx.cache.get("model_resolver_dynamic_textures")
        assert cache
        opts = self.ctx.validate("model_resolver", ModelResolverOptions)
        if "dynamic_textures" in cache.json and opts.use_cache:
            log.info("Using cached dynamic textures")
            for key, path in cache.json["dynamic_textures"].items():
                self.dynamic_textures[key] = Image.open(path)
            return
        # clear the dynamic textures
        if opts.use_cache:
            cache.clear()
        # construct the dynamic textures
        atlases = {
            **{key: value for key, value in self.getter.assets.atlases.items()},
        }
        for key, atlas in atlases.items():
            log.info(f"Creating atlas {key}")
            self.resolve_altas(key, atlas)
        if not opts.use_cache:
            return
        log.info("Caching dynamic textures")
        # construct the cache
        cache.json["dynamic_textures"] = {}
        for key, value in self.dynamic_textures.items():
            path = cache.get_path(f"{key}.png")
            with open(path, "wb") as f:
                value.save(f, "PNG")
            cache.json["dynamic_textures"][key] = str(path)

    def apply_palette(
        self, texture: Image.Image, palette: Image.Image, color_palette: Image.Image
    ) -> Image.Image:
        """PaletteMapping: the key palette's colors (read row by row, the last one wins and
        transparent ones are skipped) map to the target palette's colors and alpha."""
        keys = np.asarray(palette.convert("RGBA")).reshape(-1, 4).tolist()
        targets = np.asarray(color_palette.convert("RGBA")).reshape(-1, 4).tolist()
        if len(keys) != len(targets):
            raise RenderError(f"PaletteMapping has different sizes: {len(keys)} != {len(targets)}")
        mapping: dict[tuple[int, ...], list[int]] = {}
        for key, target in zip(keys, targets):
            if key[3] != 0:
                mapping[tuple(key[:3])] = target
        data = bytearray(texture.convert("RGBA").tobytes())
        for k in range(0, len(data), 4):
            alpha = data[k + 3]
            if alpha == 0:
                continue
            target = mapping.get(tuple(data[k : k + 3]))
            if target is not None:
                data[k : k + 4] = bytes((*target[:3], alpha * target[3] // 255))
        return Image.frombytes("RGBA", texture.size, bytes(data))

    def resolve_altas(self, key: str, atlas: Atlas):
        """Add the sprites an atlas defines under another name than their texture to dynamic_textures."""
        added: list[str] = []
        for source in atlas.data["sources"]:
            source: dict[str, Any]

            source_type = resolve_key(source["type"])
            # Handle single texture mapping
            if source_type == "minecraft:single":
                resource = resolve_key(source["resource"])
                sprite = resolve_key(source.get("sprite", source["resource"]))
                if resource in self.getter.assets.textures:
                    self.dynamic_textures[sprite] = self.getter.assets.textures[resource].image
                    added.append(sprite)
            elif source_type == "minecraft:directory":
                # the other atlases hold gui, particle or painting sprites that models can't use
                if resolve_key(key) in ("minecraft:blocks", "minecraft:items"):
                    added.extend(self.resolve_atlas_directory(source["source"], source["prefix"]))
            elif source_type == "minecraft:paletted_permutations":
                separator = source.get("separator", "_")
                for texture in source["textures"]:
                    for variant, color_palette_path in source["permutations"].items():
                        added.append(
                            self.resolve_altas_texture(
                                texture, variant, source, color_palette_path, separator
                            )
                        )
            elif source_type == "minecraft:unstitch":
                added.extend(self.resolve_atlas_unstitch(source))
            elif source_type == "minecraft:filter":
                # removes the sprites added before it
                pattern = source["pattern"]
                for sprite in added:
                    namespace, path = sprite.split(":", 1)
                    if re.search(pattern.get("namespace", ""), namespace) and re.search(
                        pattern.get("path", ""), path
                    ):
                        self.dynamic_textures.pop(sprite, None)
            else:
                log.warning(f"Unknown atlas source {source_type} in {key}")

    def resolve_atlas_directory(self, source: str, prefix: str) -> list[str]:
        """DirectoryLister: textures/<source>/<path>.png becomes the sprite <prefix><path>."""
        added = []
        directory = source.rstrip("/") + "/"
        for texture in self.getter.assets.textures:
            namespace, path = resolve_key(texture).split(":", 1)
            if not path.startswith(directory):
                continue
            sprite = f"{namespace}:{prefix}{path.removeprefix(directory)}"
            if sprite != resolve_key(texture):
                self.dynamic_textures[sprite] = self.getter.assets.textures[texture].image
                added.append(sprite)
        return added

    def resolve_atlas_unstitch(self, source: dict[str, Any]) -> list[str]:
        """Unstitcher: cut regions out of a texture, in units of the image size / divisor."""
        resource = resolve_key(source["resource"])
        if resource not in self.getter.assets.textures:
            log.warning(f"Missing sprite: {resource}")
            return []
        image: Image.Image = self.getter.assets.textures[resource].image
        x_scale = image.width / source.get("divisor_x", 1.0)
        y_scale = image.height / source.get("divisor_y", 1.0)
        added = []
        for region in source["regions"]:
            x, y = math.floor(region["x"] * x_scale), math.floor(region["y"] * y_scale)
            width = math.floor(region["width"] * x_scale)
            height = math.floor(region["height"] * y_scale)
            sprite = resolve_key(region["sprite"])
            self.dynamic_textures[sprite] = image.crop((x, y, x + width, y + height))
            added.append(sprite)
        return added

    def resolve_altas_texture(
        self,
        texture: str,
        variant: str,
        source: dict[str, Any],
        color_palette_path: str,
        separator: str = "_",
    ) -> str:
        new_texture_path = f"{texture}{separator}{variant}"
        new_texture_path = resolve_key(new_texture_path)

        palette_key = resolve_key(source["palette_key"])
        namespace, path = palette_key.split(":", 1)
        palette_key = f"{namespace}:palettes/{path}"
        if palette_key in self.getter.assets.textures:
            palette = self.getter.assets.textures[palette_key].image
        else:
            raise RenderError(f"Palette {palette_key} not found")

        color_palette_key = resolve_key(color_palette_path)
        namespace, path = color_palette_key.split(":", 1)
        color_palette_key = f"{namespace}:palettes/{path}"
        if color_palette_key in self.getter.assets.textures:
            color_palette: Image.Image = self.getter.assets.textures[
                color_palette_key
            ].image
        else:
            raise RenderError(f"Color palette {color_palette_key} not found")

        grayscale_key = resolve_key(texture)
        if grayscale_key in self.getter.assets.textures:
            grayscale = self.getter.assets.textures[grayscale_key].image
        else:
            raise RenderError(f"Grayscale {grayscale_key} not found")

        img = self.apply_palette(grayscale, palette, color_palette)

        self.dynamic_textures[new_texture_path] = img
        return new_texture_path

    def run(self):
        self.resolve_dynamic_textures()
        glutInit()
        glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA | GLUT_DEPTH)  # type: ignore
        glutInitWindowSize(512, 512)
        glutInitWindowPosition(100, 100)
        glutCreateWindow(b"Model Resolver window")
        glutHideWindow()
        glutSetOption(GLUT_ACTION_ON_WINDOW_CLOSE, GLUT_ACTION_GLUTMAINLOOP_RETURNS)
        glClearColor(0.0, 0.0, 0.0, 0.0)

        # Enable lighting
        glLightfv(GL_LIGHT0, GL_POSITION, self.light.minecraft_light_position)
        glLightfv(GL_LIGHT0, GL_AMBIENT, [self.light.minecraft_ambient_light] * 4)
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [self.light.minecraft_light_power] * 4)

        glLightfv(GL_LIGHT1, GL_POSITION, [0.0, 0.0, 10.0, 0.0])
        glLightfv(GL_LIGHT1, GL_DIFFUSE, [1.0] * 4)

        new_tasks = AppendList[Task]()
        for task in self.tasks:
            new_tasks.extend(task.resolve())
        self.tasks = new_tasks

        glutDisplayFunc(self.display)
        glutIdleFunc(self.display)
        glutReshapeFunc(self.reshape)

        try:
            glutMainLoop()
        finally:
            self.ctx.inject(GlTextures).clear()

    def reshape(self, width: int, height: int):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        zoom = 8
        glOrtho(zoom, -zoom, -zoom, zoom, 512, -512)
        glMatrixMode(GL_MODELVIEW)

    def display(self):
        if self.tasks_index >= len(self.tasks):
            glutLeaveMainLoop()
            return
        try:
            log.debug(f"Rendering task ({self.tasks_index}/{len(self.tasks)})...")
            x = self.real_display()
        except:
            glutLeaveMainLoop()
            raise
        self.tasks_index += x
        if self.tasks_index >= len(self.tasks):
            glutLeaveMainLoop()
            log.debug(f"Rendering task ended")
            return

    def real_display(self):
        if not self.current_task.ensure_params:
            self.current_task.ensure_params = True
            self.current_task.change_params()
            return 0

        glClearColor(0.0, 0.0, 0.0, 0.0)  # Set clear color to black with alpha 0
        glEnable(GL_DEPTH_TEST)
        # like vanilla's pipelines, so coplanar quads drawn later win (generated item layers)
        glDepthFunc(GL_LEQUAL)
        glEnable(GL_CULL_FACE)
        glCullFace(GL_FRONT)
        glEnable(GL_BLEND)
        set_default_blend()

        glEnable(GL_ALPHA_TEST)
        glAlphaFunc(GL_GREATER, 0)
        glEnable(GL_COLOR_MATERIAL)

        # faces are lit on the CPU like Minecraft's shaders (GuiLighting)
        glDisable(GL_LIGHTING)

        # Create a framebuffer object (FBO) for off-screen rendering
        fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, fbo)

        depth_buffer = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, depth_buffer)
        glRenderbufferStorage(
            GL_RENDERBUFFER,
            GL_DEPTH_COMPONENT,
            self.current_task.render_size,
            self.current_task.render_size,
        )
        glFramebufferRenderbuffer(
            GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depth_buffer
        )
        render_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, render_texture)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            self.current_task.render_size,
            self.current_task.render_size,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            None,
        )
        glFramebufferTexture2D(
            GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, render_texture, 0
        )
        # Check framebuffer status
        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            raise RenderError("Framebuffer is not complete")

        # Render the scene
        glViewport(0, 0, self.current_task.render_size, self.current_task.render_size)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)  # type: ignore

        self.current_task.dynamic_textures = self.dynamic_textures
        try:
            self.current_task.run()
        finally:
            self.ctx.inject(GlTextures).release_transient()

        pixel_data = glReadPixels(
            0,
            0,
            self.current_task.render_size,
            self.current_task.render_size,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
        )
        img = Image.frombytes(
            "RGBA",
            (self.current_task.render_size, self.current_task.render_size),
            pixel_data,  # type: ignore
        )
        img = unpremultiply(img.transpose(Image.Transpose.FLIP_TOP_BOTTOM))

        # Save the image
        self.current_task.save(img)

        # Release resources
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glDeleteTextures([render_texture])
        glDeleteRenderbuffers(1, [depth_buffer])
        glDeleteFramebuffers(1, [fbo])
        glDisable(GL_COLOR_MATERIAL)
        glDisable(GL_NORMALIZE)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)

        return 1
