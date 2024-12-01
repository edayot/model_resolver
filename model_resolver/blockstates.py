from email.mime import multipart
from typing import Any, Union, TypedDict, Optional
from pydantic import BaseModel



class VariantModel(BaseModel):
    model: str
    x: int = 0
    y: int = 0
    uvlock: bool = False
    weight: int = 1

Variant = Union[VariantModel, list[VariantModel]]


SimpleWhenCondition = dict[str, str]

HardWhenCondition = TypedDict("HardWhenCondition", {
    "OR": list[SimpleWhenCondition],
    "AND": list[SimpleWhenCondition],
}, total=False)

WhenCondition = HardWhenCondition | SimpleWhenCondition

def verify_when(when: WhenCondition, block_state: dict[str, Any]) -> bool:
    if "OR" in when:
        conditions = when["OR"]
        assert isinstance(conditions, list)
        return any([verify_when(x, block_state) for x in conditions])
    if "AND" in when:
        conditions = when["AND"]
        assert isinstance(conditions, list)
        return all([verify_when(x, block_state) for x in conditions])

    for key, value in when.items():
        if not key in block_state:
            return False
        values = str(value).split("|")
        if not any([str(block_state[key]) == x for x in values]):
            return False
    return True


class MultiPartModel(BaseModel):
    apply: Variant
    when: Optional[WhenCondition] = None

class BlockState(BaseModel):
    variants: Optional[dict[str, Variant]] = None
    multipart: Optional[list[MultiPartModel]] = None

    


