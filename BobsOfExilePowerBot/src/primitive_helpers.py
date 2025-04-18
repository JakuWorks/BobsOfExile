from typing import ItemsView


def get_items_view[K, V](d: dict[K, V]) -> ItemsView[K, V]:
    return d.items()
