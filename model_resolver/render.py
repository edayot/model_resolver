
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from beet import Context
from model_resolver.item import Item
from model_resolver.minecraft_model import MinecraftModel, DisplayOptionModel



@dataclass
class Render:
    ctx: Context

    def add_item_task(
        self,
        item: Item,
        *,
        path_ctx: Optional[str] = None,
        path_save: Optional[Path] = None,
        render_size: Optional[int] = None,
    ):
        ...
    def add_model_task(
        self,
        model: str,
        *,
        path_ctx: Optional[str] = None,
        path_save: Optional[Path | str] = None,
        render_size: Optional[int] = None,
    ):
        ...
    def add_model_dict_task(
        self,
        model: dict[str, Any] | MinecraftModel,
        *,
        path_ctx: Optional[str] = None,
        path_save: Optional[Path | str] = None,
        render_size: Optional[int] = None,
    ):
        ...
    def add_structure_task(
        self,
        structure: str,
        *,
        path_ctx: Optional[str] = None,
        path_save: Optional[Path | str] = None,
        render_size: Optional[int] = None,
        display_option: Optional[DisplayOptionModel | dict[str, Any]] = None,
    ):
        ...

