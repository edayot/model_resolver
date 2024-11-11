import json

def regenerate_test_json(x, y, z):
    models = []
    for i in range(x + 1):
        for j in range(y + 1):
            for k in range(z + 1):
                model_entry = {
                    "type": "minecraft:condition",
                    "property": "minecraft:custom_model_data",
                    "index": i * (y + 1) * (z + 1) + j * (z + 1) + k,
                    "on_true": {
                        "type": "minecraft:model",
                        "model": f"custom_item:item/{i}_{j}_{k}",
                        "tints": [
                            {
                                "type": "minecraft:custom_model_data",
                                "index": i * (y + 1) * (z + 1) + j * (z + 1) + k,
                                "default": 0
                            }
                        ]
                    },
                    "on_false": {
                        "type": "minecraft:model",
                        "model": "minecraft:block/air"
                    }
                }
                models.append(model_entry)

    test_json = {
        "model": {
            "type": "minecraft:composite",
            "models": models
        }
    }

    with open('assets/custom_item/items/test.json', 'w') as f:
        json.dump(test_json, f, indent=2)

regenerate_test_json(15, 15, 15)  # Remplacez 15 par les valeurs souhaitées pour x, y, z