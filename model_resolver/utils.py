import json
import os
import re
import subprocess
from beet import LATEST_MINECRAFT_VERSION, Context
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator
from typing import TYPE_CHECKING, Any, Literal, Optional, Self, get_args
from beet import Context
from functools import lru_cache

from pydantic import BaseModel
import logging

from beet.contrib.vanilla import Vanilla

log = logging.getLogger("model_resolver")

DEFAULT_RENDER_SIZE = 256


def resolve_key(key: str) -> str:
    return f"minecraft:{key}" if ":" not in key else key


ID_PATTERN = re.compile(r"[a-z0-9_.-]+(/[a-z0-9_./-]*)*")


def namespaced(value: Any) -> Any:
    """Add the minecraft namespace to every string that is an id without one.

    Applied to both sides of a comparison, it makes "stone" equal minecraft:stone the way
    decoding them as ids does, and changes nothing else.
    """
    if isinstance(value, str):
        return f"minecraft:{value}" if ID_PATTERN.fullmatch(value) else value
    if isinstance(value, list):
        return [namespaced(x) for x in value]
    if isinstance(value, dict):
        return {key: namespaced(x) for key, x in value.items()}
    return value


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison


def clamp[T: (SupportsRichComparison)](minimum: T, x: T, maximum: T) -> T:
    return max(minimum, min(x, maximum))


def literal_values(cls: type[BaseModel], field: str) -> tuple[Any, ...]:
    info = cls.model_fields.get(field)
    return get_args(info.annotation) if info else ()


def validate_dispatched[T: BaseModel](data: Any, classes: list[type[T]], what: str) -> T:
    """Validate `data` with the class its `type` (and `property`) selects, like a dispatch codec.

    Classes registered later win, so subclasses can replace built-in implementations.
    """
    if not isinstance(data, dict):
        raise ValueError(f"Invalid {what}, expected an object: {data!r}")
    candidates = [cls for cls in reversed(classes) if data.get("type") in literal_values(cls, "type")]
    if not candidates:
        raise ValueError(f"Unknown {what} type {data.get('type')!r}")
    if any("property" in cls.model_fields for cls in candidates):
        candidates = [
            cls for cls in candidates if data.get("property") in literal_values(cls, "property")
        ]
        if not candidates:
            raise ValueError(f"Unknown {what} property {data.get('property')!r} for {data['type']!r}")
    errors: list[ValidationError] = []
    for cls in candidates:
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            errors.append(e)
    raise ValueError(f"Invalid {what} {data['type']!r}: {errors[0]}")


class LightOptions(BaseModel):
    """Light options."""

    minecraft_light_power: float = 0.6727302277118515
    minecraft_ambient_light: float = 0.197261163686041
    minecraft_light_position: list[float] = [
        -0.42341569107908505,
        -0.6577205642540358,
        0.4158725999762756,
        0.0,
    ]


_warned_options: set[str] = set()


class ModelResolverOptions(BaseModel):
    """Model resolver options."""

    use_cache: bool = False
    minecraft_version: str = "latest"
    special_rendering: bool = False
    colorize_blocks: bool = True
    preferred_minecraft_generated: Literal["misode/mcmeta", "java"] = "misode/mcmeta"
    transparent_missingno: bool = True
    render_size: Optional[int] = None
    """Size of the renders that don't set one, DEFAULT_RENDER_SIZE when unset."""

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def warn_unknown_options(self) -> Self:
        # beet validates the options again on every ctx.validate, warn once per key
        for key in self.model_extra or {}:
            if key not in _warned_options:
                _warned_options.add(key)
                log.warning(f"Unknown model_resolver option {key!r} is ignored")
        return self



@lru_cache
def get_default_components(ctx: Context) -> dict[str, Any]:
    from model_resolver.pack_getter import PackGetter
    getter = PackGetter.from_context(ctx)
    version = getter.opts.minecraft_version
    if version == "latest":
        version = LATEST_MINECRAFT_VERSION
    prefered = getter.opts.preferred_minecraft_generated
    # TODO: if java is not found, fallback to misode/mcmeta
    if prefered == "java":
        # test if java is available
        try:
            subprocess.run(
                ["java", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            log.warning("Java not found, falling back to misode/mcmeta")
            prefered = "misode/mcmeta"
    match prefered:
        case "misode/mcmeta":
            url = f"https://raw.githubusercontent.com/misode/mcmeta/refs/tags/{version}-summary/item_components/data.json"
            log.info(url)
            path = ctx.cache["model_resolver_components"].download(url)
            with open(path) as file:
                components = json.load(file)
            return {resolve_key(key): value for key, value in components.items()}
        case "java":
            jar = getter._vanilla.cache.download(
                getter._vanilla.info.data["downloads"]["server"]["url"]
            )
            cache = ctx.cache["model_resolver_components"]
            path = cache.get_path("minecraft_reports")
            if not path.is_dir():
                os.makedirs(path, exist_ok=True)
                subprocess.run(
                    [
                        "java",
                        "-DbundlerMainClass=net.minecraft.data.Main",
                        "-jar",
                        jar,
                        "--reports",
                    ],
                    cwd=path,
                    check=True,
                )
            items_json = path / "generated" / "reports" / "items.json"
            if items_json.exists():
                with open(items_json) as file:
                    components = json.load(file)
                return {
                    resolve_key(key): value["components"]
                    for key, value in components.items()
                }
            # examples/load_vanilla/.beet_cache/model_resolver_components/0x0/generated/reports/minecraft/components/item
            components = {}
            for item in (path / "generated" / "reports" / "minecraft" / "components" / "item").glob("*.json"):
                with open(item) as file:
                    components[resolve_key(item.name.removesuffix(".json"))] = json.load(file)["components"]
            return components
        case _:
            raise ValueError(f"Unknown preferred_minecraft_generated: {prefered}")
