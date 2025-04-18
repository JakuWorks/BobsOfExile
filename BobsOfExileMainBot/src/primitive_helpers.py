from typing import Any, KeysView
from collections import deque


def have_same_keys[A](dict1: dict[Any, Any], dict2: dict[A, Any]) -> bool:
    dict2_k: KeysView[A] = dict2.keys()
    for k1 in dict1.keys():
        if k1 not in dict2_k:
            return False
    return True


def deque_pop_many[T](d: deque[T], pops: int) -> list[T]:
    popped: list[T] = []
    for _ in range(pops):
        popped.append(d.pop())
    return popped

    
def deque_pop_left_many[T](d: deque[T], pops: int) -> list[T]:
    popped: list[T] = []
    for _ in range(pops):
        popped.append(d.popleft())
    return popped
