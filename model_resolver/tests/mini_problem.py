from model_resolver.cli import main as main_run
from PIL import Image, ImageColor
import numpy as np
import scipy.optimize as opt
import os

TOP_COLOR = "#fcfcfc"
LEFT_COLOR = "#a4a4a4"
RIGHT_COLOR = "#656565"
TOP_COO = (48, 24)
LEFT_COO = (28, 54)
RIGHT_COO = (68, 54)


def get_params(x: list):
    return {
        "minecraft_light_power": x[0],
        "minecraft_ambient_light": x[1],
        "minecraft_light_position": [x[2], x[3], x[4], 0.0],
    }


def calc_distance(img: Image.Image, coo: tuple[int, int], color: str):
    color = ImageColor.getcolor(color, "RGB")
    dist = 0
    color_coo = img.getpixel(coo)
    for i in range(3):
        dist += abs(color_coo[i] - color[i])
    return dist


def calc_distances(img: Image.Image):
    img = img.convert("RGB")
    return (
        calc_distance(img, TOP_COO, TOP_COLOR)
        + calc_distance(img, LEFT_COO, LEFT_COLOR)
        + calc_distance(img, RIGHT_COO, RIGHT_COLOR)
    )


def run(x: list):
    out = "/home/erwan/Documents/dev/model_resolver/model_resolver/tests/mini_problem/render.png"
    try:
        os.remove(out)
    except FileNotFoundError:
        pass
    main_run(
        render_size=96,
        load_dir="/home/erwan/Documents/dev/model_resolver/model_resolver/tests/mini_problem",
        output_dir=None,
        __special_filter__={"debug:block/all_white": out},
        __light__=get_params(x),
    )
    img = Image.open(out)
    return calc_distances(img)


def main():
    x0 = [
        0.6727302277118515,
        0.197261163686041,
        -0.42341569107908505,
        -0.6577205642540358,
        0.4158725999762756,
    ]
    run(x0)
    return
    res = opt.minimize(run, x0, method="nelder-mead")
    print(res)
    print(get_params(res.x))


if __name__ == "__main__":
    main()
