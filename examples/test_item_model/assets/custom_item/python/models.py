import json
import os

def generate_model_files(x, y, z):
    template = {
        "parent": "item/generated",
        "textures": {
            "1": "custom_item:custom/white"
        },
        "elements": [
            {
                "from": [0, 0, 0],
                "to": [1, 1, 1],
                "faces": {
                    "north": {"uv": [0, 0, 16, 16], "texture": "#1", "tintindex": 0},
                    "east": {"uv": [0, 0, 16, 16], "texture": "#1", "tintindex": 0},
                    "south": {"uv": [0, 0, 16, 16], "texture": "#1", "tintindex": 0},
                    "west": {"uv": [0, 0, 16, 16], "texture": "#1", "tintindex": 0},
                    "up": {"uv": [0, 0, 16, 16], "texture": "#1", "tintindex": 0},
                    "down": {"uv": [0, 0, 16, 16], "texture": "#1", "tintindex": 0}
                }
            }
        ]
    }

    os.makedirs('assets/custom_item/models/item', exist_ok=True)

    for i in range(x + 1):
        for j in range(y + 1):
            for k in range(z + 1):
                model = template.copy()
                model['elements'][0]['from'] = [i, j, k]
                model['elements'][0]['to'] = [i + 1, j + 1, k + 1]
                filename = f'assets/custom_item/models/item/{i}_{j}_{k}.json'
                with open(filename, 'w') as f:
                    json.dump(model, f, indent=2)

generate_model_files(15, 15, 15)  # Remplacez 15 par les valeurs souhaitées pour x, y, z