def override(_left: list[str], right: list[str]) -> list[str]:
    return right


def merge_dict[K, V](left: dict[K, V], right: dict[K, V]) -> dict[K, V]:
    return {**left, **right}


def append_unique(left: list[str], right: list[str]) -> list[str]:
    return [*left, *(item for item in right if item not in left)]
