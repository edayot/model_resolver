"""Animated textures (.png.mcmeta) and atlas sources."""

import pytest
from beet import Atlas, ResourcePack, Texture, TextureMcmeta
from PIL import Image

from model_resolver.render import Render
from model_resolver.tasks.generic_render import Animation
from resolver_testkit import make_getter


def frame_color(index):
    return (index * 40 + 10, 0, 0, 255)


def sprite_sheet(size, frame_size):
    """Paint frame k of a row-major grid of frames in frame_color(k)."""
    width, height = size
    frame_width, frame_height = frame_size
    columns = width // frame_width
    image = Image.new("RGBA", size)
    for k in range(columns * (height // frame_height)):
        x, y = (k % columns) * frame_width, (k // columns) * frame_height
        image.paste(frame_color(k), (x, y, x + frame_width, y + frame_height))
    return image


def play(image, animation):
    """(frame image, duration in ticks, red channel) for every frame model_resolver emits."""
    assets = ResourcePack()
    assets.textures["test:block/anim"] = Texture(image)
    assets.textures_mcmeta["test:block/anim"] = TextureMcmeta({"animation": animation})
    played = Animation(
        textures=[{"x": "test:block/anim"}],
        getter=make_getter(assets),
        animation_framerate=20,
    ).get_frames()
    result = []
    for _, (images, duration) in played:
        frame = images["test:block/anim"].convert("RGBA")
        pixel = frame.getpixel((0, 0))
        assert isinstance(pixel, tuple)
        result.append((frame, duration, pixel[0]))
    return result


def frames(image, animation):
    """(frame size, duration in ticks, frame index) for every frame model_resolver emits."""
    return [
        (frame.size, duration, (red - 10) // 40)
        for frame, duration, red in play(image, animation)
    ]


class TestAnimation:
    def test_vertical_strip(self):
        image = sprite_sheet((16, 48), (16, 16))
        assert frames(image, {"frametime": 2}) == [
            ((16, 16), 2, 0),
            ((16, 16), 2, 1),
            ((16, 16), 2, 2),
        ]

    def test_explicit_frames_with_times(self):
        image = sprite_sheet((16, 48), (16, 16))
        animation = {"frames": [{"index": 2, "time": 3}, 0]}
        assert frames(image, animation) == [((16, 16), 3, 2), ((16, 16), 1, 0)]

    def test_frame_object_without_time(self):
        image = sprite_sheet((16, 48), (16, 16))
        animation = {"frametime": 2, "frames": [{"index": 1}, 0]}
        assert frames(image, animation) == [((16, 16), 2, 1), ((16, 16), 2, 0)]

    def test_horizontal_strip(self):
        image = sprite_sheet((48, 16), (16, 16))
        assert frames(image, {}) == [
            ((16, 16), 1, 0),
            ((16, 16), 1, 1),
            ((16, 16), 1, 2),
        ]

    def test_explicit_frame_height(self):
        image = sprite_sheet((16, 32), (16, 8))
        assert frames(image, {"height": 8}) == [((16, 8), 1, k) for k in range(4)]

    def test_grid_of_frames(self):
        image = sprite_sheet((32, 32), (16, 16))
        animation = {"width": 16, "height": 16}
        assert frames(image, animation) == [((16, 16), 1, k) for k in range(4)]


def bare_render(assets):
    # resolve_altas only needs the getter and the dynamic texture table
    render = Render.__new__(Render)
    render.getter = make_getter(assets)
    render.dynamic_textures = {}
    return render


def trim_assets():
    assets = ResourcePack()
    gray = Image.new("RGBA", (2, 1))
    gray.putdata([(10, 10, 10, 255), (99, 99, 99, 255)])
    assets.textures["minecraft:trims/items/helmet_trim"] = Texture(gray)
    assets.textures["minecraft:palettes/trim_base"] = Texture(
        Image.new("RGB", (1, 1), (10, 10, 10))
    )
    assets.textures["minecraft:palettes/trim/gold"] = Texture(
        Image.new("RGB", (1, 1), (200, 150, 50))
    )
    return assets


def paletted(**extra):
    return Atlas(
        {
            "sources": [
                {
                    "type": "minecraft:paletted_permutations",
                    "textures": ["minecraft:trims/items/helmet_trim"],
                    "palette_key": "minecraft:trim_base",
                    "permutations": {"gold": "minecraft:trim/gold"},
                    **extra,
                }
            ]
        }
    )


class TestAtlases:
    def test_single_source_with_sprite_name(self):
        assets = ResourcePack()
        assets.textures["test:raw/thing"] = Texture(Image.new("RGBA", (1, 1)))
        render = bare_render(assets)
        render.resolve_altas(
            "minecraft:blocks",
            Atlas(
                {
                    "sources": [
                        {
                            "type": "single",
                            "resource": "test:raw/thing",
                            "sprite": "test:thing",
                        }
                    ]
                }
            ),
        )
        assert "test:thing" in render.dynamic_textures

    def test_paletted_permutation(self):
        render = bare_render(trim_assets())
        render.resolve_altas("minecraft:items", paletted())
        image = render.dynamic_textures["minecraft:trims/items/helmet_trim_gold"]
        pixels = [image.getpixel((x, 0)) for x in range(image.width)]
        assert pixels == [(200, 150, 50, 255), (99, 99, 99, 255)]

    def test_paletted_permutation_separator(self):
        render = bare_render(trim_assets())
        render.resolve_altas("minecraft:items", paletted(separator="-"))
        assert "minecraft:trims/items/helmet_trim-gold" in render.dynamic_textures

    def test_directory_source_with_a_different_prefix(self):
        assets = ResourcePack()
        assets.textures["test:custom_textures/foo"] = Texture(Image.new("RGBA", (1, 1)))
        render = bare_render(assets)
        render.resolve_altas(
            "minecraft:blocks",
            Atlas(
                {
                    "sources": [
                        {
                            "type": "directory",
                            "source": "custom_textures",
                            "prefix": "custom/",
                        }
                    ]
                }
            ),
        )
        assert "test:custom/foo" in render.dynamic_textures


def reds_per_tick(image, animation):
    return [red for _, duration, red in play(image, animation) for _ in range(duration)]


class TestInterpolation:
    def test_blends_towards_the_next_frame(self):
        image = sprite_sheet((16, 32), (16, 16))
        reds = reds_per_tick(image, {"frametime": 4, "interpolate": True})
        # mix(current, next, subFrame / time), frame 0 is red 10 and frame 1 red 50
        assert reds == pytest.approx([10, 20, 30, 40, 50, 40, 30, 20], abs=1)

    def test_repeated_frame_entries_blend_entry_by_entry(self):
        image = sprite_sheet((16, 32), (16, 16))
        animation = {"frametime": 2, "interpolate": True, "frames": [0, 0, 1]}
        reds = reds_per_tick(image, animation)
        # entry 0 blends 0 -> 0, entry 1 blends 0 -> 1, entry 2 blends 1 -> 0
        assert reds == pytest.approx([10, 10, 10, 30, 50, 30], abs=1)


def palette_render(keys, targets, pixels):
    """Map a 1-row texture through a paletted permutation built from 1-row palettes."""
    assets = ResourcePack()
    for name, colors in (("test:palettes/key", keys), ("test:palettes/gold", targets)):
        palette = Image.new("RGBA", (len(colors), 1))
        palette.putdata(colors)
        assets.textures[name] = Texture(palette)
    texture = Image.new("RGBA", (len(pixels), 1))
    texture.putdata(pixels)
    assets.textures["test:thing"] = Texture(texture)
    render = bare_render(assets)
    render.resolve_altas(
        "minecraft:items",
        Atlas(
            {
                "sources": [
                    {
                        "type": "minecraft:paletted_permutations",
                        "textures": ["test:thing"],
                        "palette_key": "test:key",
                        "permutations": {"gold": "test:gold"},
                    }
                ]
            }
        ),
    )
    image = render.dynamic_textures["test:thing_gold"]
    return [image.getpixel((x, 0)) for x in range(image.width)]


class TestPaletteMapping:
    # PaletteMapping.create / apply
    def test_last_entry_wins_for_a_repeated_key(self):
        keys = [(10, 10, 10, 255), (10, 10, 10, 255)]
        targets = [(200, 0, 0, 255), (0, 200, 0, 255)]
        assert palette_render(keys, targets, [(10, 10, 10, 255)]) == [(0, 200, 0, 255)]

    def test_transparent_key_entries_are_skipped(self):
        keys = [(10, 10, 10, 255), (0, 0, 0, 0)]
        targets = [(200, 150, 50, 255), (255, 0, 255, 255)]
        assert palette_render(keys, targets, [(0, 0, 0, 255)]) == [(0, 0, 0, 255)]

    def test_target_alpha_is_multiplied_in(self):
        keys = [(10, 10, 10, 255)]
        targets = [(200, 150, 50, 128)]
        assert palette_render(keys, targets, [(10, 10, 10, 255)]) == [
            (200, 150, 50, 128)
        ]

    def test_transparent_pixels_are_left_alone(self):
        keys = [(10, 10, 10, 255)]
        targets = [(200, 150, 50, 255)]
        assert palette_render(keys, targets, [(10, 10, 10, 0)]) == [(10, 10, 10, 0)]


class TestOtherAtlasSources:
    def test_unstitch(self):
        assets = ResourcePack()
        assets.textures["test:sheet"] = Texture(sprite_sheet((32, 16), (16, 16)))
        render = bare_render(assets)
        source = {
            "type": "minecraft:unstitch",
            "resource": "test:sheet",
            "divisor_x": 2,
            "divisor_y": 1,
            "regions": [
                {"sprite": "test:right", "x": 1, "y": 0, "width": 1, "height": 1}
            ],
        }
        render.resolve_altas("minecraft:blocks", Atlas({"sources": [source]}))
        image = render.dynamic_textures["test:right"]
        assert image.size == (16, 16)
        assert image.getpixel((0, 0)) == frame_color(1)

    def test_filter_removes_the_sprites_added_before_it(self):
        render = bare_render(trim_assets())
        filtered = paletted()
        filtered.data["sources"].append(
            {"type": "minecraft:filter", "pattern": {"path": "helmet"}}
        )
        render.resolve_altas("minecraft:items", filtered)
        assert "minecraft:trims/items/helmet_trim_gold" not in render.dynamic_textures

    def test_directory_sources_of_other_atlases_are_not_mapped(self):
        # gui, particle and painting sprites can't be used by models
        assets = ResourcePack()
        assets.textures["minecraft:gui/sprites/icon"] = Texture(
            Image.new("RGBA", (1, 1))
        )
        render = bare_render(assets)
        source = {"type": "directory", "source": "gui/sprites", "prefix": ""}
        render.resolve_altas("minecraft:gui", Atlas({"sources": [source]}))
        assert render.dynamic_textures == {}


def test_higher_framerates_repeat_each_tick():
    from model_resolver.tasks.model import AnimatedResultTask

    task = AnimatedResultTask.__new__(AnimatedResultTask)
    task.animation_framerate = 40
    ticks = ["a", "b"]
    assert task.resample(ticks) == ["a", "a", "b", "b"]  # type: ignore
    task.animation_framerate = 10
    assert task.resample(["a", "b", "c", "d"]) == ["a", "c"]  # type: ignore


class TestRenderComparison:
    def png(self, pixels, size=(10, 10)):
        import io

        image = Image.new("RGBA", size)
        image.putdata(pixels)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_rounding_noise_is_tolerated(self):
        from render_compare import compare_images

        base = [(100, 100, 100, 255)] * 100
        noisy = [(101, 99, 100, 255)] * 100
        assert compare_images(self.png(base), self.png(noisy)).ok

    def test_a_real_change_is_not(self):
        from render_compare import compare_images

        base = [(100, 100, 100, 255)] * 100
        changed = [(100, 100, 100, 255)] * 90 + [(0, 0, 0, 0)] * 10
        diff = compare_images(self.png(base), self.png(changed))
        assert not diff.ok
        assert diff.silhouette == pytest.approx(0.1)
