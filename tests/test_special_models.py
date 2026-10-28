"""`minecraft:special` item models against the 26.3 special renderer registry."""

import pytest
from beet import BannerPattern, DataPack

from model_resolver.item_model.model import ItemModelSpecial
from model_resolver.item_model.special import SpecialModel, SpecialModelPlayerHead
from resolver_testkit import make_getter, make_item


def special(data):
    return SpecialModel.model_validate(data).special_model


def build(data, components=None, getter=None):
    return special(data).get_model(
        getter or make_getter(), make_item(components=components)
    )


def texture_ids(model):
    ids = set()
    for value in model.get("textures", {}).values():
        if isinstance(value, str):
            ids.add(value)
        elif isinstance(value, tuple):
            ids.update(texture for texture, _ in value)
    return ids


# minimal valid payloads for every type in SpecialModelRenderers (26.3)
REGISTRY_26_3 = {
    "banner": {"color": "white"},
    "bell": {},
    "book": {"open_angle": 45, "page1": 0.3, "page2": 0.7},
    "chest": {"texture": "minecraft:normal"},
    "conduit": {},
    "copper_golem_statue": {
        "pose": "standing",
        "texture": "minecraft:textures/entity/copper_golem/copper_golem.png",
    },
    "decorated_pot": {},
    "end_cube": {"effect": "portal"},
    "head": {"kind": "zombie"},
    "player_head": {},
    "shield": {},
    "shulker_box": {"texture": "minecraft:shulker"},
    "trident": {},
}


@pytest.mark.parametrize("kind", REGISTRY_26_3)
def test_every_26_3_special_type_parses(kind):
    special({"type": f"minecraft:{kind}", **REGISTRY_26_3[kind]})


@pytest.mark.parametrize("kind", REGISTRY_26_3)
def test_every_26_3_special_type_has_geometry(kind):
    model = build({"type": f"minecraft:{kind}", **REGISTRY_26_3[kind]})
    assert model.get("elements")


@pytest.mark.parametrize("pose", ["standing", "sitting", "running", "star"])
def test_copper_golem_statue_uses_its_entity_texture(pose):
    model = build(
        {
            "type": "minecraft:copper_golem_statue",
            "pose": pose,
            "texture": "minecraft:textures/entity/copper_golem/copper_golem.png",
        }
    )
    assert model.get("elements")
    assert "minecraft:entity/copper_golem/copper_golem" in texture_ids(model)


class TestTextures:
    def test_chest(self):
        model = build({"type": "minecraft:chest", "texture": "minecraft:copper"})
        assert texture_ids(model) == {"minecraft:entity/chest/copper"}

    def test_shulker_box(self):
        model = build(
            {"type": "minecraft:shulker_box", "texture": "minecraft:shulker_black"}
        )
        assert texture_ids(model) == {"minecraft:entity/shulker/shulker_black"}

    def test_head_texture_override(self):
        model = build(
            {
                "type": "minecraft:head",
                "kind": "skeleton",
                "texture": "minecraft:skeleton/stray",
            }
        )
        assert "minecraft:entity/skeleton/stray" in texture_ids(model)

    @pytest.mark.parametrize(
        "decorations",
        [
            {
                "back": "minecraft:archer_pottery_sherd",
                "front": {"id": "minecraft:prize_pottery_sherd"},
            },
            [
                "minecraft:archer_pottery_sherd",
                "minecraft:brick",
                "minecraft:brick",
                "minecraft:prize_pottery_sherd",
            ],
        ],
        ids=["26.3_object", "legacy_list"],
    )
    def test_decorated_pot_sherds(self, decorations):
        model = build(
            {"type": "minecraft:decorated_pot"},
            {"minecraft:pot_decorations": decorations},
        )
        textures = model["textures"]
        assert (
            textures["north"] == "minecraft:entity/decorated_pot/archer_pottery_pattern"
        )
        assert (
            textures["south"] == "minecraft:entity/decorated_pot/prize_pottery_pattern"
        )
        assert (
            model["textures"]["east"]
            == "minecraft:entity/decorated_pot/decorated_pot_side"
        )


class TestBannerPatterns:
    def test_vanilla_pattern(self):
        components = {
            "minecraft:banner_patterns": [
                {"pattern": "minecraft:rhombus", "color": "cyan"}
            ]
        }
        model = build({"type": "minecraft:banner", "color": "white"}, components)
        assert "minecraft:entity/banner/rhombus" in texture_ids(model)

    def test_data_pack_pattern_uses_its_asset_id(self):
        data = DataPack()
        data.banner_patterns["test:my_pattern"] = BannerPattern(
            {"asset_id": "test:fancy", "translation_key": "block.test.fancy"}
        )
        components = {
            "minecraft:banner_patterns": [
                {"pattern": "test:my_pattern", "color": "red"}
            ]
        }
        model = build(
            {"type": "minecraft:banner", "color": "white"},
            components,
            make_getter(data=data),
        )
        assert "test:entity/banner/fancy" in texture_ids(model)

    def test_inline_pattern(self):
        pattern = {"asset_id": "test:fancy", "translation_key": "block.test.fancy"}
        components = {
            "minecraft:banner_patterns": [{"pattern": pattern, "color": "red"}]
        }
        model = build({"type": "minecraft:banner", "color": "white"}, components)
        assert "test:entity/banner/fancy" in texture_ids(model)


def player_texture(profile=None):
    head = special({"type": "minecraft:player_head"})
    assert isinstance(head, SpecialModelPlayerHead)
    components = {} if profile is None else {"minecraft:profile": profile}
    return head.get_player_texture(make_getter(), make_item(components=components))


def test_player_head_without_profile_is_steve():
    # DefaultPlayerSkin.getDefaultSkin
    assert player_texture() == "minecraft:entity/player/slim/steve"


class TestOfflinePlayerHeads:
    # unit tests can't download, like a profile that can't be resolved in game:
    # DefaultPlayerSkin.get(uuid) picks one of the 18 default skins
    def test_known_uuid(self):
        assert (
            player_texture({"id": [0, 0, 0, 1]}) == "minecraft:entity/player/slim/ari"
        )

    def test_string_uuid(self):
        uuid = "00000000-0000-0000-0000-000000000001"
        assert player_texture({"id": uuid}) == "minecraft:entity/player/slim/ari"

    def test_name_uses_the_offline_player_uuid(self):
        from model_resolver.item_model.special import default_skin, offline_player_uuid

        assert (
            str(offline_player_uuid("Notch")) == "b50ad385-829d-3141-a216-7e7d7539ba7f"
        )
        assert player_texture("Notch") == default_skin(offline_player_uuid("Notch"))

    def test_properties_without_a_skin(self):
        import base64
        import json

        value = base64.b64encode(json.dumps({"textures": {}}).encode()).decode()
        profile = {
            "name": "Notch",
            "properties": [{"name": "textures", "value": value}],
        }
        from model_resolver.item_model.special import default_skin, offline_player_uuid

        assert player_texture(profile) == default_skin(offline_player_uuid("Notch"))


def test_player_head_profile_texture_patch():
    head = special({"type": "minecraft:player_head"})
    assert isinstance(head, SpecialModelPlayerHead)
    item = make_item(
        components={
            "minecraft:profile": {"texture": "minecraft:entity/player/wide/alex"}
        }
    )
    assert (
        head.get_player_texture(make_getter(), item)
        == "minecraft:entity/player/wide/alex"
    )


def test_special_rendering_disabled_gives_an_empty_model():
    node = ItemModelSpecial.model_validate(
        {
            "type": "minecraft:special",
            "base": "minecraft:item/chest",
            "model": {"type": "minecraft:conduit"},
        }
    )
    model = node.get_model(make_getter(special_rendering=False), make_item())
    assert model.elements == []
