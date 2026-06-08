from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, Mapping, Protocol, Optional, Sequence, Type, overload, cast

from beet import LATEST_MINECRAFT_VERSION, Context, DataPack, Namespace, NamespaceContainer, NamespaceFile, NamespaceProxy, Pack, ResourcePack
from beet.contrib.vanilla import Vanilla, Release

from model_resolver.utils import ModelResolverOptions


class PackGetterProtocol(Protocol):
    @property
    def assets(self) -> Optional[ResourcePack]: ...
    
    @property
    def data(self) -> Optional[DataPack]: ...


@dataclass
class PackGetterLookup:
    assets: Optional[ResourcePack] = None
    data: Optional[DataPack] = None


@overload
def get_by_namespace_proxy[T: NamespaceFile](context: NamespaceProxy[T], vanilla: NamespaceProxy[T], key: str) -> T: ...
@overload
def get_by_namespace_proxy[T: NamespaceFile](context: NamespaceContainer[T], vanilla: NamespaceContainer[T], key: str) -> T: ...

def get_by_namespace_proxy[T: NamespaceFile](context: NamespaceProxy[T] | NamespaceContainer[T], vanilla: NamespaceProxy[T] | NamespaceContainer[T], key: str) -> T:
    res = context.get(key)
    if res is None:
        res = vanilla.get(key)
        if res is None:
            raise KeyError(key)
    return res


@overload
def get_by_lookup_order[T: NamespaceFile](lookups: list[NamespaceProxy[T]], key: str) -> T: ...
@overload
def get_by_lookup_order[T: NamespaceFile](lookups: list[NamespaceContainer[T]], key: str) -> T: ...

def get_by_lookup_order[T: NamespaceFile](lookups: list[NamespaceProxy[T]] | list[NamespaceContainer[T]], key: str) -> T:
    for lookup in lookups:
        res = lookup.get(key)
        if res is not None:
            return res
    raise KeyError(key)


def iter_lookup_keys(lookups: Sequence[Mapping[str, object]]) -> Iterator[str]:
    seen: set[str] = set()
    for lookup in lookups:
        for key in lookup:
            if key in seen:
                continue
            seen.add(key)
            yield key


def get_pack[T: Pack](pack: Type[T], thing: PackGetterProtocol) -> T:
    if pack is ResourcePack:
        return cast(T, thing.assets or ResourcePack())
    if pack is DataPack:
        return cast(T, thing.data or DataPack())
    raise ValueError(f"Pack type {pack} is not valid")



@dataclass
class PackGetterNamespaceContainerProxy[T: NamespaceFile](Mapping[str, T]):
    lookups: list[NamespaceContainer[T]]

    def __getitem__(self, key: str):
        return get_by_lookup_order(self.lookups, key)
    
    def __iter__(self) -> Iterator[str]:
        return iter_lookup_keys(self.lookups)
    
    def __len__(self) -> int:
        return len({key for lookup in self.lookups for key in lookup})


@dataclass
class PackGetterNamespaceProxy[T: NamespaceFile](Mapping[str, T]):
    lookups: list[NamespaceProxy[T]]

    def __getitem__(self, key: str):
        return get_by_lookup_order(self.lookups, key)
    
    def __iter__(self) -> Iterator[str]:
        return iter_lookup_keys(self.lookups)

    def __len__(self) -> int:
        return len({key for lookup in self.lookups for key in lookup})

@dataclass
class PackGetterNamespacePackProxy:
    lookups: list[Namespace]

    def __getattr__(self, name):
        namespace_lookups = []
        for lookup in self.lookups:
            if not hasattr(lookup, name):
                raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
            lookup_proxy = getattr(lookup, name)
            if not isinstance(lookup_proxy, NamespaceContainer):
                raise TypeError(f"Attribute {name} of {lookup} is not a NamespaceContainer")
            namespace_lookups.append(lookup_proxy)
        return PackGetterNamespaceContainerProxy(namespace_lookups)

@dataclass
class PackGetterPackProxy[T: Pack](Mapping[str, Namespace]):
    """A merged view of packs, resolved in lookup order."""
    _pack: Type[T]
    _getter: PackGetter

    def _lookups(self) -> list[T]:
        return [get_pack(self._pack, getattr(self._getter, lookup)) for lookup in self._getter.lookups]

    @overload
    def __getitem__(self, key: str): ...

    @overload
    def __getitem__(self, key: type[NamespaceFile]): ...

    def __getitem__(self, key: type[NamespaceFile] | str): 
        lookups = self._lookups()
        if isinstance(key, type):
            return PackGetterNamespaceProxy([lookup[key] for lookup in lookups])
        elif isinstance(key, str):
            return PackGetterNamespacePackProxy([lookup[key] for lookup in lookups])
        else:
            raise ValueError(f"Key {key} is not recognised")

    def __getattr__(self, name):
        namespace_lookups = []
        for lookup in self._lookups():
            if not hasattr(lookup, name):
                raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
            lookup_proxy = getattr(lookup, name)
            if not isinstance(lookup_proxy, NamespaceProxy):
                raise TypeError(f"Attribute {name} of {lookup} is not a NamespaceProxy")
            namespace_lookups.append(lookup_proxy)
        return PackGetterNamespaceProxy(namespace_lookups)
    
    def __iter__(self):
        seen: set[str] = set()
        for lookup in self._lookups():
            for key in lookup:
                if key in seen:
                    continue
                seen.add(key)
                yield key

    def __len__(self) -> int:
        return len({key for lookup in self._lookups() for key in lookup})

@dataclass
class PackGetterPackProxyDescriptor[T: Pack]:
    _pack: Type[T]
    def __get__(self, instance, owner) -> PackGetterPackProxy[T]:
        return PackGetterPackProxy(self._pack, instance) 


class PackGetter():
    _ctx: Context
    _vanilla: Release
    _static_lookup: PackGetterLookup
    opts: ModelResolverOptions
    lookups: list[str]

    if TYPE_CHECKING:
        assets: ResourcePack
        data: DataPack
    else:
        assets: PackGetterPackProxyDescriptor[ResourcePack] = PackGetterPackProxyDescriptor(ResourcePack)
        data:   PackGetterPackProxyDescriptor[DataPack]     = PackGetterPackProxyDescriptor(DataPack)

    def __init__(self, 
        ctx: Context, 
        vanilla: Release, 
        static_lookup: PackGetterLookup, 
        opts: ModelResolverOptions, 
        lookups: list[str]
    ) -> None:
        self.lookups = lookups
        self._ctx = ctx
        self._vanilla = vanilla
        self._static_lookup = static_lookup
        self.opts = opts


    @classmethod
    def from_context(cls, ctx: Context, version: str | None = None):
        opts = ctx.validate("model_resolver", ModelResolverOptions)
        vanilla = Vanilla(ctx)
        minecraft_version = version or opts.minecraft_version or ctx.minecraft_version
        if minecraft_version == "latest":
            minecraft_version = LATEST_MINECRAFT_VERSION
        release = vanilla.releases[minecraft_version]
        static_models = Path(__file__).parent / "static_models"
        static_lookup = PackGetterLookup(assets=ResourcePack(path=static_models))        
        return cls(ctx, release, static_lookup, opts, ["_ctx", "_static_lookup", "_vanilla", ])
        