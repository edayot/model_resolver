from beet import Context, ResourcePack, Texture

from model_resolver.pack_getter import PackGetter


def beet_default(ctx: Context):
    getter = PackGetter.from_ctx(ctx)

    # normal access
    print(getter.release.assets[Texture]["minecraft:item/diamond"])
    print(getter.release.assets.textures["minecraft:item/diamond"])
    print(getter.release.assets["minecraft"].textures["item/diamond"])

    print(getter.release.assets[Texture].get("minecraft:item/diamond"))
    print(getter.release.assets.textures.get("minecraft:item/diamond"))
    print(getter.release.assets["minecraft"].textures.get("item/diamond"))

    for key in getter.release.assets:
        print(key)


    # merged access
    print(getter.assets[Texture]["minecraft:item/diamond"])
    print(getter.assets.textures["minecraft:item/diamond"])
    print(getter.assets["minecraft"].textures["item/diamond"])

    print(getter.assets[Texture].get("minecraft:item/diamond"))
    print(getter.assets.textures.get("minecraft:item/diamond"))
    print(getter.assets["minecraft"].textures.get("item/diamond"))

    for key in getter.assets:
        print(key)
