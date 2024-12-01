from OpenGL.GL import *  # type: ignore
from OpenGL.GLUT import *  # type: ignore
from OpenGL.GLU import *  # type: ignore

from dataclasses import dataclass, field
from model_resolver.utils import resolve_key
from model_resolver.minecraft_model import (
    DisplayOptionModel,
    RotationModel,
)
from typing import Optional, Any, TypedDict, Union
from pydantic import BaseModel, Field
from rich import print  # noqa
from functools import cached_property
import random
from model_resolver.tasks.base import Task, RenderError
from model_resolver.tasks.model import ModelPathRenderTask


class PaletteModel(BaseModel):
    Name: str
    Properties: dict[str, str] = Field(default_factory=dict)


class BlockModel(BaseModel):
    state: int
    pos: tuple[int, int, int]
    nbt: Optional[dict[str, Any]] = None


class StructureDataModel(BaseModel):
    DataVersion: int
    size: tuple[int, int, int]
    palette_: Optional[list[PaletteModel]] = Field(alias="palette", default=None)
    palettes: Optional[list[list[PaletteModel]]] = None
    blocks: list[BlockModel]
    entities: Any

    @cached_property
    def palette(self) -> list[PaletteModel]:
        if self.palette_:
            return self.palette_
        if self.palettes:
            return random.choice(self.palettes)
        raise RenderError("No palette found")


class VariantModel(BaseModel):
    model: str
    x: int = 0
    y: int = 0
    uvlock: bool = False
    weight: int = 1


Variant = Union[VariantModel, list[VariantModel]]


SimpleWhenCondition = dict[str, str]

HardWhenCondition = TypedDict(
    "HardWhenCondition",
    {
        "OR": list[SimpleWhenCondition],
        "AND": list[SimpleWhenCondition],
    },
    total=False,
)

WhenCondition = HardWhenCondition | SimpleWhenCondition


def verify_when(when: WhenCondition, block_state: dict[str, Any]) -> bool:
    if "OR" in when:
        conditions = when["OR"]
        assert isinstance(conditions, list)
        return any([verify_when(x, block_state) for x in conditions])
    if "AND" in when:
        conditions = when["AND"]
        assert isinstance(conditions, list)
        return all([verify_when(x, block_state) for x in conditions])

    for key, value in when.items():
        if not key in block_state:
            return False
        values = str(value).split("|")
        if not any([str(block_state[key]) == x for x in values]):
            return False
    return True


class MultiPartModel(BaseModel):
    apply: Variant
    when: Optional[WhenCondition] = None


class BlockState(BaseModel):
    variants: Optional[dict[str, Variant]] = None
    multipart: Optional[list[MultiPartModel]] = None


@dataclass(kw_only=True)
class StructureRenderTask(Task):
    structure_key: str
    display_option: DisplayOptionModel = field(
        default_factory=lambda: DisplayOptionModel(
            rotation=(30, 225, 0), translation=(0, 0, 0), scale=(0.625, 0.625, 0.625)
        )
    )
    zoom: int = 128
    do_rotate_camera: bool = True

    @cached_property
    def structure(self):
        key = resolve_key(self.structure_key)
        if key in self.ctx.data.structures:
            data = self.ctx.data.structures[key].data
        elif key in self.vanilla.data.structures:
            data = self.vanilla.data.structures[key].data
        else:
            raise RenderError(f"Structure {key} not found")
        return StructureDataModel.model_validate(data)

    def rotate_camera(self):
        if not self.do_rotate_camera:
            return
        # transform the vertices
        scale = self.display_option.scale or [1, 1, 1]
        translation = self.display_option.translation or [0, 0, 0]
        rotation = self.display_option.rotation or [0, 0, 0]

        # reset the matrix
        glLoadIdentity()
        glTranslatef(-translation[0], translation[1], -translation[2])
        glRotatef(-rotation[0], 1, 0, 0)
        glRotatef(rotation[1] + 180, 0, 1, 0)
        glRotatef(rotation[2], 0, 0, 1)
        glScalef(scale[0], scale[1], scale[2])

    def run(self):
        self.rotate_camera()
        sx, sy, sz = self.structure.size
        center = (-sx / 2, -sy / 2, -sz / 2)
        for block in self.structure.blocks:
            self.render_block(block, center)

    def render_block(self, block: BlockModel, center: tuple[float, float, float]):
        palleted = self.structure.palette[block.state]

        if palleted.Name in self.ctx.assets.blockstates:
            block_state = self.ctx.assets.blockstates[palleted.Name].data
        elif palleted.Name in self.vanilla.assets.blockstates:
            block_state = self.vanilla.assets.blockstates[palleted.Name].data
        else:
            raise RenderError(f"Blockstate {palleted.Name} not found")

        block_state = BlockState.model_validate(block_state)
        if block_state.variants:
            if "" in block_state.variants:
                variant = block_state.variants[""]
            else:
                parsed_dict: dict[str, dict[str, str]] = {}
                for key in block_state.variants.keys():
                    parsed_key: dict[str, str] = {}
                    key_split = key.split(",")
                    for key_split_part in key_split:
                        state, value = key_split_part.split("=")
                        parsed_key[state] = value
                    parsed_dict[key] = parsed_key
                variant = None
                for key, parsed_key in parsed_dict.items():
                    if all(
                        [
                            parsed_key.get(x, object())
                            == palleted.Properties.get(x, object())
                            for x in parsed_key.keys()
                        ]
                    ):
                        variant = block_state.variants[key]
                        break
                if variant is None:
                    raise RenderError("Variant not found")
            self.render_variant(variant, block, center, palleted)
        elif block_state.multipart:
            for part in block_state.multipart:
                if not part.when:
                    self.render_variant(part.apply, block, center, palleted)
                else:
                    if verify_when(part.when, palleted.Properties):
                        self.render_variant(part.apply, block, center, palleted)

    def render_variant(
        self,
        variant: Variant,
        block: BlockModel,
        center: tuple[float, float, float],
        palleted: PaletteModel,
    ):
        if isinstance(variant, list):
            resolved_variant = random.choices(
                variant, weights=[x.weight for x in variant]
            )[0]
        else:
            resolved_variant = variant
        if resolve_key(resolved_variant.model) == "minecraft:block/air":
            return

        rots = [
            RotationModel(
                origin=(8, 8, 8), axis="x", angle=resolved_variant.x, rescale=False
            ),
            RotationModel(
                origin=(8, 8, 8), axis="y", angle=-resolved_variant.y, rescale=False
            ),
        ]
        task = ModelPathRenderTask(
            ctx=self.ctx,
            vanilla=self.vanilla,
            render_size=self.render_size,
            model=resolved_variant.model,
            dynamic_textures=self.dynamic_textures,
            do_rotate_camera=False,
            additional_rotations=rots,
            offset=(block.pos[0] * 16, block.pos[1] * 16, block.pos[2] * 16),
            center_offset=center,
        )
        task.run()
