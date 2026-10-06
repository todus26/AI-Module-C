from core.normalize import normalize

CATALOG: dict[str, list[tuple[str, str]]] = {
    "채소": [
        ("양파", "개"), ("대파", "대"), ("감자", "개"), ("고구마", "개"), ("당근", "개"),
        ("애호박", "개"), ("오이", "개"), ("양배추", "통"), ("무", "개"), ("시금치", "단"),
        ("콩나물", "봉"), ("숙주", "봉"), ("부추", "단"), ("버섯", "팩"), ("토마토", "개"),
        ("김치", "팩"),
    ],
    "육류": [
        ("돼지고기", "g"), ("소고기", "g"), ("닭고기", "g"), ("베이컨", "줄"),
        ("햄", "캔"), ("소시지", "개"),
    ],
    "해산물": [
        ("오징어", "마리"), ("새우", "마리"), ("고등어", "마리"), ("참치", "캔"),
        ("어묵", "장"), ("미역", "봉"),
    ],
    "유제품·계란": [("계란", "개"), ("우유", "ml"), ("치즈", "장"), ("버터", "g")],
    "곡류·면": [
        ("밥", "공기"), ("국수", "인분"), ("스파게티면", "인분"), ("라면", "봉"),
        ("당면", "g"), ("떡", "g"), ("식빵", "장"),
    ],
    "두부·가공식품": [("두부", "모"), ("순두부", "봉")],
}

CATEGORIES: list[str] = [*CATALOG, "기타"]
UNITS: list[str] = [
    "개", "g", "kg", "ml", "L", "모", "봉", "팩", "캔", "단", "마리", "장", "공기",
    "인분", "대", "줄", "통",
]

STAPLES: list[str] = [
    "소금", "후추", "식용유", "참기름", "간장", "국간장", "설탕", "고춧가루", "다진 마늘",
    "고추장", "된장", "깨", "물", "맛술", "식초", "올리고당", "부침가루", "케첩", "마요네즈",
]
_STAPLE_KEYS = {normalize(s) for s in STAPLES}

_DEFAULTS = {normalize(n): (cat, unit) for cat, rows in CATALOG.items() for n, unit in rows}


def default_for(name: str) -> tuple[str, str]:
    """재료명으로 기본 분류와 단위를 찾는다. 목록에 없으면 ('기타', '개')."""
    return _DEFAULTS.get(normalize(name), ("기타", "개"))


def is_staple(name: str) -> bool:
    return normalize(name) in _STAPLE_KEYS


def catalog_keys() -> set[str]:
    return set(_DEFAULTS)
