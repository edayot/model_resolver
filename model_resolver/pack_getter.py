from dataclasses import dataclass
from beet import Context, DataPack, Namespace, NamespaceContainer, NamespaceFile, NamespaceProxy, Pack, ResourcePack
from typing import TYPE_CHECKING, Iterator, Mapping, Type, overload
from beet import Context
from beet.contrib.vanilla import Vanilla, Release


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


def get_pack(pack: Type[Pack], thing: Context | Release):
    if pack is ResourcePack:
        return thing.assets
    if pack is DataPack:
        return thing.data
    raise ValueError(f"Pack type {pack} is not valid")



@dataclass
class PackGetterNamespaceContainerProxy[T: NamespaceFile](Mapping[str, T]):
    context: NamespaceContainer[T]
    vanilla: NamespaceContainer[T]

    def __getitem__(self, key: str):
        return get_by_namespace_proxy(self.context, self.vanilla, key)
    
    def __iter__(self) -> Iterator[str]:
        seen = set()
        for key in self.context:
            yield key
            seen.add(key)
        for key in self.vanilla:
            if key not in seen:
                yield key
    
    def __len__(self) -> int:
        return len(set(self.context) | set(self.vanilla))


@dataclass
class PackGetterNamespaceProxy[T: NamespaceFile](Mapping[str, T]):
    context: NamespaceProxy[T]
    vanilla: NamespaceProxy[T]

    def __getitem__(self, key: str):
        return get_by_namespace_proxy(self.context, self.vanilla, key)
    
    def __iter__(self) -> Iterator[str]:
        seen = set()
        for key in self.context:
            yield key
            seen.add(key)
        for key in self.vanilla:
            if key not in seen:
                yield key

    def __len__(self) -> int:
        return len(set(self.context) | set(self.vanilla))

@dataclass
class PackGetterNamespacePackProxy:
    context: Namespace
    vanilla: Namespace

    def __getattr__(self, name):
        if not (hasattr(self.context, name) and hasattr(self.vanilla, name)):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        context_proxy = getattr(self.context, name)
        vanilla_proxy = getattr(self.vanilla, name)
        if not isinstance(context_proxy, NamespaceContainer):
            raise TypeError(f"Attribute {name} of {self.context} is not a NamespaceContainer")
        if not isinstance(vanilla_proxy, NamespaceContainer):
            raise TypeError(f"Attribute {name} of {self.vanilla} is not a NamespaceContainer")
        return PackGetterNamespaceContainerProxy(context_proxy, vanilla_proxy)

@dataclass
class PackGetterPackProxy[T: Pack](Mapping[str, Namespace]):
    """ A merged view of two packs"""
    _pack: Type[T]
    _getter: PackGetter

    @overload
    def __getitem__(self, key: str): ...

    @overload
    def __getitem__(self, key: type[NamespaceFile]): ...

    def __getitem__(self, key: type[NamespaceFile] | str): 
        context = get_pack(self._pack, self._getter.ctx)
        vanilla = get_pack(self._pack, self._getter.release)
        if isinstance(key, type):
            return PackGetterNamespaceProxy(context[key], vanilla[key])
        elif isinstance(key, str):
            return PackGetterNamespacePackProxy(context[key], vanilla[key])
        else:
            raise ValueError(f"Key {key} is not recognised")

    def __getattr__(self, name):
        context = get_pack(self._pack, self._getter.ctx)
        vanilla = get_pack(self._pack, self._getter.release)
        if not (hasattr(context, name) and hasattr(vanilla, name)):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        context_proxy = getattr(context, name)
        vanilla_proxy = getattr(vanilla, name)
        if not isinstance(context_proxy, NamespaceProxy):
            raise TypeError(f"Attribute {name} of {context} is not a NamespaceProxy")
        if not isinstance(vanilla_proxy, NamespaceProxy):
            raise TypeError(f"Attribute {name} of {vanilla} is not a NamespaceProxy")
        return PackGetterNamespaceProxy(context_proxy, vanilla_proxy)
    
    def __iter__(self):
        context = get_pack(self._pack, self._getter.ctx)
        vanilla = get_pack(self._pack, self._getter.release)
        seen = set()
        for key in context:
            yield key
            seen.add(key)
        for key in vanilla:
            if key not in seen:
                yield key

    def __len__(self) -> int:
        return len(set(self.context) | set(self.vanilla))

@dataclass
class PackGetterPackProxyDescriptor[T: Pack]:
    _pack: Type[T]
    def __get__(self, instance, owner) -> PackGetterPackProxy[T]:
        return PackGetterPackProxy(self._pack, instance) 


class PackGetter():
    ctx: Context
    release: Release

    if TYPE_CHECKING:
        assets: ResourcePack
        data: DataPack
    else:
        assets: PackGetterPackProxyDescriptor[ResourcePack] = PackGetterPackProxyDescriptor(ResourcePack)
        data:   PackGetterPackProxyDescriptor[DataPack]     = PackGetterPackProxyDescriptor(DataPack)

    def __init__(self, ctx: Context, release: Release) -> None:
        self.ctx = ctx
        self.release = release

    @classmethod
    def from_ctx(cls, ctx: Context, version: str | None = None):
        vanilla = Vanilla(ctx)
        release = vanilla.releases[version or ctx.minecraft_version]
        return cls(ctx, release)
        