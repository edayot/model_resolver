"""`minecraft:condition` with `property: minecraft:component` (data component predicates)."""

import pytest
from nbtlib import Int

from resolver_testkit import make_getter, make_item, model_node, resolve_item_model


def matches(predicate, value, components):
    node = {
        "type": "minecraft:condition",
        "property": "minecraft:component",
        "predicate": predicate,
        "value": value,
        "on_true": model_node("test:true"),
        "on_false": model_node("test:false"),
    }
    result = resolve_item_model(node, make_item(components=components))
    assert result in (["test:true"], ["test:false"])
    return result == ["test:true"]


DAMAGED = {"minecraft:damage": 5, "minecraft:max_damage": 10}


class TestCustomData:
    def test_partial_object_match(self):
        components = {"minecraft:custom_data": {"test": "airdox_", "other": 1}}
        assert matches("minecraft:custom_data", {"test": "airdox_"}, components)

    def test_snbt_string(self):
        components = {"minecraft:custom_data": {"test": "airdox_"}}
        assert matches("minecraft:custom_data", '{test:"airdox_"}', components)

    def test_mismatch(self):
        components = {"minecraft:custom_data": {"test": "other"}}
        assert not matches("minecraft:custom_data", {"test": "airdox_"}, components)


class TestDamage:
    def test_both_bounds_given(self):
        assert matches("minecraft:damage", {"damage": 5, "durability": 5}, DAMAGED)

    def test_damage_only(self):
        assert matches("minecraft:damage", {"damage": 5}, DAMAGED)

    def test_open_ended_range(self):
        assert matches("minecraft:damage", {"durability": {"min": 1}}, DAMAGED)


class TestEnchantments:
    def test_id_and_level(self):
        value = [{"enchantments": "minecraft:sharpness", "levels": 2}]
        components = {"minecraft:enchantments": {"minecraft:sharpness": 2}}
        assert matches("minecraft:enchantments", value, components)

    def test_any_enchantment_with_a_level_range(self):
        value = [{"levels": {"min": 1, "max": 255}}]
        components = {"minecraft:enchantments": {"minecraft:sharpness": 2}}
        assert matches("minecraft:enchantments", value, components)


class TestContainers:
    def test_container_contains(self):
        components = {
            "minecraft:container": [
                {"slot": 0, "item": {"id": "minecraft:stone", "count": 1}}
            ]
        }
        value = {"items": {"contains": [{"items": "minecraft:stone"}]}}
        assert matches("minecraft:container", value, components)

    def test_container_predicate_on_an_item_without_container(self):
        value = {"items": {"size": 0}}
        assert not matches("minecraft:container", value, {})

    def test_bundle_contents_size(self):
        components = {
            "minecraft:bundle_contents": [{"id": "minecraft:stone", "count": 1}]
        }
        assert matches("minecraft:bundle_contents", {"items": {"size": 1}}, components)


class TestPredicateCoverage:
    def test_unsupported_predicate_does_not_match_everything(self):
        assert not matches("minecraft:villager/variant", "minecraft:desert", DAMAGED)

    def test_fireworks_flight_duration(self):
        components = {"minecraft:fireworks": {"flight_duration": 2, "explosions": []}}
        assert matches("minecraft:fireworks", {"flight_duration": 2}, components)

    def test_jukebox_playable_song(self):
        components = {"minecraft:jukebox_playable": "minecraft:cat"}
        assert matches(
            "minecraft:jukebox_playable", {"song": "minecraft:cat"}, components
        )

    def test_potion_contents_potions(self):
        components = {"minecraft:potion_contents": {"potion": "minecraft:healing"}}
        value = {"potions": "minecraft:healing"}
        assert matches("minecraft:potion_contents", value, components)

    def test_any_component_id_checks_presence(self):
        assert not matches("minecraft:glider", {}, {})

    def test_several_predicates_can_match_the_same_enchantment(self):
        value = [
            {"enchantments": "minecraft:sharpness", "levels": 2},
            {"enchantments": "minecraft:sharpness", "levels": 2},
        ]
        components = {"minecraft:enchantments": {"minecraft:sharpness": 2}}
        assert matches("minecraft:enchantments", value, components)


class TestCustomDataNbtMatching:
    # NbtUtils.compareNbt(expected, actual, partialListMatches=true)
    def test_list_elements_match_partially(self):
        components = {"minecraft:custom_data": {"list": [{"a": 1, "b": 2}]}}
        assert matches("minecraft:custom_data", {"list": [{"a": 1}]}, components)

    def test_empty_list_only_matches_an_empty_list(self):
        components = {"minecraft:custom_data": {"list": [1]}}
        assert not matches("minecraft:custom_data", {"list": []}, components)

    def test_empty_predicate_matches_items_without_custom_data(self):
        assert matches("minecraft:custom_data", {}, {})


class TestNbtTypes:
    def test_byte_is_not_int(self):
        components = {"minecraft:custom_data": "{flag:1b}"}
        assert not matches("minecraft:custom_data", "{flag:1}", components)
        assert matches("minecraft:custom_data", "{flag:1b}", components)

    @pytest.mark.parametrize(
        "number, snbt",
        [
            (1, "1b"),
            (-128, "-128b"),
            (256, "256s"),
            (40000, "40000"),
            (2**40, f"{2**40}L"),
            (2.0, "2b"),
            (0.5, "0.5f"),
            (0.1, "0.1d"),
        ],
    )
    def test_json_numbers_take_the_narrowest_type(self, number, snbt):
        # JsonOps.convertTo: byte, short, int or long when integral, else float or double
        components = {"minecraft:custom_data": {"count": number}}
        assert matches("minecraft:custom_data", f"{{count:{snbt}}}", components)
        assert matches("minecraft:custom_data", {"count": number}, components)

    def test_json_numbers_are_not_doubles(self):
        components = {"minecraft:custom_data": {"count": 1}}
        assert not matches("minecraft:custom_data", "{count:1d}", components)
        assert not matches("minecraft:custom_data", "{count:1}", components)

    def test_json_lists_are_list_tags(self):
        # JsonOps.convertList -> NbtOps.createList, never an array
        components = {"minecraft:custom_data": {"list": [1, 2]}}
        assert matches("minecraft:custom_data", "{list:[1b, 2b]}", components)
        assert not matches("minecraft:custom_data", "{list:[B; 1b, 2b]}", components)

    def test_json_lists_can_mix_number_types(self):
        components = {"minecraft:custom_data": {"list": [1, 300]}}
        assert matches("minecraft:custom_data", {"list": [300]}, components)
        assert matches("minecraft:custom_data", "{list:[300s]}", components)

    def test_nbt_tags_in_json_keep_their_type(self):
        components = {"minecraft:custom_data": {"count": Int(0)}}
        assert matches("minecraft:custom_data", "{count:0}", components)


class TestSimpleDrawerCompactingDrawer:
    """SimpleDrawer's new_drawer item model on its compacting drawer, whose
    custom_data is plain JSON while the model's predicates are SNBT."""

    @staticmethod
    def drawer(**custom_data):
        data = {"wood_type": "simpledrawer:compacting", "variant": "normal", **custom_data}
        stored = {
            "id": "minecraft:stone",
            "count": 1,
            "components": {"minecraft:custom_data": {"simpledrawer": data}},
        }
        return {"minecraft:container": [{"slot": 0, "item": stored}]}

    @staticmethod
    def contains(custom_data):
        return {"items": {"contains": [{"predicates": {"minecraft:custom_data": custom_data}}]}}

    @pytest.mark.parametrize("slot_count", [1, 2, 3])
    def test_slot_count_selects_the_compacting_model(self, slot_count):
        components = self.drawer(slot_count=slot_count)
        value = self.contains(f"{{simpledrawer: {{slot_count: {slot_count}b }} }}")
        assert matches("minecraft:container", value, components)

    def test_other_slot_counts_do_not_match(self):
        components = self.drawer(slot_count=3)
        value = self.contains("{simpledrawer: {slot_count: 1b }}")
        assert not matches("minecraft:container", value, components)

    def test_wood_type(self):
        components = self.drawer(slot_count=3)
        value = self.contains({"simpledrawer": {"wood_type": "simpledrawer:compacting"}})
        assert matches("minecraft:container", value, components)

    def test_json_item_counts_are_bytes_not_ints(self):
        # the game reads {"0": 0} from JSON as 0b, which `{0: 0}` (an int) does not match
        value = self.contains("{simpledrawer: {items_counts: {0: 0, 1: 0}}}")
        assert not matches("minecraft:container", value, self.drawer(items_counts={"0": 0, "1": 0}))
        assert matches("minecraft:container", value, self.drawer(items_counts={"0": Int(0), "1": Int(0)}))


class TestHolderSets:
    def test_tag_entries_can_be_optional(self):
        from beet import DataPack, ItemTag

        data = DataPack()
        data.item_tags["test:gems"] = ItemTag(
            {
                "values": [
                    "minecraft:diamond",
                    {"id": "#test:missing", "required": False},
                ]
            }
        )
        components = {
            "minecraft:container": [
                {"slot": 0, "item": {"id": "minecraft:diamond", "count": 1}}
            ]
        }
        value = {"items": {"contains": [{"items": "#test:gems"}]}}
        node = {
            "type": "minecraft:condition",
            "property": "minecraft:component",
            "predicate": "minecraft:container",
            "value": value,
            "on_true": model_node("test:true"),
            "on_false": model_node("test:false"),
        }
        item = make_item(components=components)
        assert resolve_item_model(node, item, make_getter(data=data)) == ["test:true"]


class TestNestedItems:
    CONTAINER = {
        "minecraft:container": [
            {
                "slot": 0,
                "item": {
                    "id": "minecraft:stone",
                    "count": 3,
                    "components": {"minecraft:damage": 2, "minecraft:max_damage": 10},
                },
            }
        ]
    }

    def test_count_and_exact_components(self):
        value = {
            "items": {
                "contains": [
                    {
                        "items": "stone",
                        "count": {"min": 2},
                        "components": {"damage": 2},
                    }
                ]
            }
        }
        assert matches("minecraft:container", value, self.CONTAINER)

    def test_component_predicates_of_contained_items(self):
        inner = {"minecraft:damage": {"durability": {"min": 9}}}
        value = {"items": {"contains": [{"predicates": inner}]}}
        assert not matches("minecraft:container", value, self.CONTAINER)

    def test_count_entries(self):
        value = {"items": {"count": [{"test": {"items": "stone"}, "count": 1}]}}
        assert matches("minecraft:container", value, self.CONTAINER)


class TestOtherPredicates:
    def test_potion_effects(self):
        components = {
            "minecraft:potion_contents": {"potion": "minecraft:strong_poison"}
        }
        value = {"effects": {"contains": [{"minecraft:poison": {"amplifier": 1}}]}}
        assert matches("minecraft:potion_contents", value, components)
        value = {"effects": {"contains": [{"minecraft:poison": {"amplifier": 0}}]}}
        assert not matches("minecraft:potion_contents", value, components)

    def test_firework_explosion(self):
        components = {
            "minecraft:firework_explosion": {"shape": "star", "has_trail": True}
        }
        value = {"shape": "star", "has_trail": True, "has_twinkle": False}
        assert matches("minecraft:firework_explosion", value, components)

    def test_fireworks_explosions(self):
        components = {
            "minecraft:fireworks": {
                "flight_duration": 1,
                "explosions": [{"shape": "creeper"}],
            }
        }
        value = {"explosions": {"contains": [{"shape": "creeper"}]}}
        assert matches("minecraft:fireworks", value, components)

    def test_written_book(self):
        components = {
            "minecraft:written_book_content": {
                "title": {"raw": "Notes"},
                "author": "Alex",
                "pages": ["hello"],
            }
        }
        value = {
            "title": "Notes",
            "author": "Alex",
            "pages": {"contains": [{"text": "hello"}]},
        }
        assert matches("minecraft:written_book_content", value, components)

    def test_writable_book(self):
        components = {"minecraft:writable_book_content": {"pages": [{"raw": "a"}]}}
        value = {"pages": {"size": 1, "contains": ["a"]}}
        assert matches("minecraft:writable_book_content", value, components)

    def test_attribute_modifiers(self):
        modifier = {
            "type": "minecraft:attack_damage",
            "id": "test:sharp",
            "amount": 5,
            "operation": "add_value",
        }
        components = {"minecraft:attribute_modifiers": [modifier]}
        value = {
            "modifiers": {
                "contains": [
                    {"attribute": "attack_damage", "amount": {"min": 4}, "slot": "any"}
                ]
            }
        }
        assert matches("minecraft:attribute_modifiers", value, components)

    def test_trim(self):
        components = {
            "minecraft:trim": {"material": "minecraft:gold", "pattern": "minecraft:eye"}
        }
        assert matches("minecraft:trim", {"material": ["iron", "gold"]}, components)
        assert not matches("minecraft:trim", {"pattern": "minecraft:host"}, components)

    def test_villager_variant(self):
        components = {"minecraft:villager/variant": "minecraft:desert"}
        assert matches("minecraft:villager/variant", "desert", components)
