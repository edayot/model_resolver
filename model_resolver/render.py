from OpenGL.GL import *  # type: ignore
from OpenGL.GLUT import *  # type: ignore
from OpenGL.GLU import *  # type: ignore
from model_resolver.minecraft_model import DisplayOptionModel
from model_resolver.my_glut_init import glutInit

from beet import Context, Atlas
from dataclasses import dataclass, field
from model_resolver.item_model.item import Item
from model_resolver.tasks.item import ItemRenderTask
from model_resolver.tasks.model import ModelPathRenderTask
from model_resolver.tasks.structure import StructureRenderTask
from model_resolver.utils import (
    LightOptions,
    ModelResolverOptions,
    PackGetterV2,
    resolve_key,
    DEFAULT_RENDER_SIZE,
    log,
)
from typing import Any, Literal, Optional, TypedDict
from pathlib import Path
from PIL import Image
from rich import print  # noqa

from model_resolver.tasks.base import AnimationType, Task, RenderError


class AtlasDict(TypedDict):
    type: str
    textures: list[str]
    palette_key: str
    permutations: dict[str, str]


@dataclass
class Render:
    ctx: Context

    tasks: list[Task] = field(default_factory=list)
    tasks_index: int = 0
    light: LightOptions = field(default_factory=LightOptions)
    dynamic_textures: dict[str, Image.Image] = field(default_factory=dict)
    default_render_size: int = DEFAULT_RENDER_SIZE
    random_seed: int = 143221

    def __post_init__(self):
        self.getter = PackGetterV2.from_context(self.ctx)

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
    ):
        if render_size is None:
            render_size = self.default_render_size
        if isinstance(path_save, str):
            path_save = Path(path_save)
        self.tasks.append(
            ItemRenderTask(
                getter=self.getter,
                item=item.fill(self.ctx),
                path_ctx=path_ctx,
                path_save=path_save,
                render_size=render_size,
                animation_mode=animation_mode,
                animation_framerate=animation_framerate,
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
    ):
        if render_size is None:
            render_size = self.default_render_size
        if isinstance(path_save, str):
            path_save = Path(path_save)
        self.tasks.append(
            ModelPathRenderTask(
                getter=self.getter,
                model=model,
                path_ctx=path_ctx,
                path_save=path_save,
                render_size=render_size,
                animation_mode=animation_mode,
                animation_framerate=animation_framerate,
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
    ):
        kwargs: dict[Literal["display_option"], DisplayOptionModel] = {}
        if render_size is None:
            render_size = self.default_render_size
        if isinstance(path_save, str):
            path_save = Path(path_save)
        if isinstance(display_option, dict):
            kwargs["display_option"] = DisplayOptionModel(**display_option)
        elif isinstance(display_option, DisplayOptionModel):
            kwargs["display_option"] = display_option
        self.tasks.append(
            StructureRenderTask(
                getter=self.getter,
                structure_key=structure,
                path_ctx=path_ctx,
                path_save=path_save,
                render_size=render_size,
                random_seed=self.random_seed,
                animation_mode=animation_mode,
                animation_framerate=animation_framerate,
                **kwargs,
            )
        )

    def resolve_dynamic_textures(self):
        # first, resolve all vanilla altas
        cache = self.ctx.cache.get("model_resolver_dynamic_textures")
        assert cache
        opts = self.ctx.validate("model_resolver", ModelResolverOptions)
        if "dynamic_textures" in cache.json and opts.use_cache:
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
            self.resolve_altas(key, atlas)
        if not opts.use_cache:
            return
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
        new_image = Image.new("RGBA", texture.size)
        texture = texture.convert("RGBA")
        palette = palette.convert("RGB")
        color_palette = color_palette.convert("RGB")
        for x in range(texture.width):
            for y in range(texture.height):
                pixel = texture.getpixel((x, y))
                if not isinstance(pixel, tuple):
                    raise ValueError("Texture is not RGBA")
                color = pixel[:3]
                alpha = pixel[3]
                # if the color is in palette_key, replace it with the color from color_palette
                found = False
                for i in range(palette.width):
                    for j in range(palette.height):
                        if palette.getpixel((i, j)) == color:
                            new_color = color_palette.getpixel((i, j))
                            if not isinstance(new_color, tuple):
                                raise ValueError("Color palette is not RGB")
                            new_image.putpixel((x, y), new_color + (alpha,))
                            found = True
                            break
                    if found:
                        break
                if not found:
                    new_image.putpixel((x, y), pixel)
        return new_image

    def resolve_altas(self, key: str, atlas: Atlas):
        for source in atlas.data["sources"]:
            if resolve_key(source["type"]) != "minecraft:paletted_permutations":
                continue
            source: AtlasDict
            for texture in source["textures"]:
                for variant, color_palette_path in source["permutations"].items():
                    self.resolve_altas_texture(
                        texture, variant, source, color_palette_path
                    )

    def resolve_altas_texture(
        self, texture: str, variant: str, source: AtlasDict, color_palette_path: str
    ):
        new_texture_path = f"{texture}_{variant}"
        new_texture_path = resolve_key(new_texture_path)

        palette_key = resolve_key(source["palette_key"])
        if palette_key in self.getter.assets.textures:
            palette = self.getter.assets.textures[palette_key].image
        else:
            raise RenderError(f"Palette {palette_key} not found")

        color_palette_key = resolve_key(color_palette_path)
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

    def run(self):
        self.resolve_dynamic_textures()
        glutInit()
        glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA | GLUT_DEPTH)  # type: ignore
        glutInitWindowSize(512, 512)
        glutInitWindowPosition(100, 100)
        glutCreateWindow(b"Isometric View")
        glutHideWindow()
        glutSetOption(GLUT_ACTION_ON_WINDOW_CLOSE, GLUT_ACTION_GLUTMAINLOOP_RETURNS)
        glClearColor(0.0, 0.0, 0.0, 0.0)

        # Enable lighting
        glLightfv(GL_LIGHT0, GL_POSITION, self.light.minecraft_light_position)
        glLightfv(GL_LIGHT0, GL_AMBIENT, [self.light.minecraft_ambient_light] * 4)
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [self.light.minecraft_light_power] * 4)

        glLightfv(GL_LIGHT1, GL_POSITION, [0.0, 0.0, 10.0, 0.0])
        glLightfv(GL_LIGHT1, GL_DIFFUSE, [1.0] * 4)

        new_tasks = []
        for task in self.tasks:
            new_tasks.extend(task.resolve())
        self.tasks = new_tasks

        glutDisplayFunc(self.display)
        glutIdleFunc(self.display)
        glutReshapeFunc(self.reshape)

        glutMainLoop()

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
        glEnable(GL_CULL_FACE)
        glCullFace(GL_FRONT)
        glEnable(GL_BLEND)
        glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA)

        glEnable(GL_ALPHA_TEST)
        glAlphaFunc(GL_GREATER, 0)
        glEnable(GL_COLOR_MATERIAL)

        glEnable(GL_NORMALIZE)
        glEnable(GL_LIGHTING)

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
        self.current_task.run()

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
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

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
