from beet import Context, ResourcePack, Texture

from model_resolver.pack_getter import PackGetter


def beet_default(ctx: Context):
    getter = PackGetter.from_ctx(ctx)

    # normal access
    assert getter.lookups[1].assets
    print(getter.lookups[1].assets[Texture]["minecraft:item/diamond"])
    print(getter.lookups[1].assets.textures["minecraft:item/diamond"])
    print(getter.lookups[1].assets["minecraft"].textures["item/diamond"])

    print(getter.lookups[1].assets[Texture].get("minecraft:item/diamond"))
    print(getter.lookups[1].assets.textures.get("minecraft:item/diamond"))
    print(getter.lookups[1].assets["minecraft"].textures.get("item/diamond"))

    for key in getter.lookups[1].assets:
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
