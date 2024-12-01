from model_resolver.tasks.structure import verify_when
from nbtlib import Compound, String


def test_when_condition():

    assert verify_when(
        {"west": "false"},
        Compound(
            {
                "east": String("false"),
                "waterlogged": String("false"),
                "south": String("false"),
                "north": String("false"),
                "west": String("true"),
            }
        ),
    ) == False

    assert verify_when(
        {"west": "true"},
        Compound(
            {
                "east": String("false"),
                "waterlogged": String("false"),
                "south": String("false"),
                "north": String("false"),
                "west": String("true"),
            }
        ),
    ) == True

    assert verify_when(
        {"west": "true", "east": "true"},
        Compound(
            {
                "east": String("false"),
                "waterlogged": String("false"),
                "south": String("false"),
                "north": String("false"),
                "west": String("true"),
            }
        ),
    ) == False
