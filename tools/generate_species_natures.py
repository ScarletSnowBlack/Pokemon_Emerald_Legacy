#!/usr/bin/env python3
"""Generate per-species nature pools from Smogon's Advance Strategy Dex."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import urllib.request


RPC_URL = "https://www.smogon.com/dex/_rpc/"
USER_AGENT = "Pokemon Emerald Legacy nature pool generator"
GENERATION = "rs"
NATURE_FALLBACK = (
    "Adamant",
    "Modest",
    "Jolly",
    "Timid",
    "Impish",
    "Bold",
    "Careful",
    "Calm",
)
POOL_OVERRIDES = {
    "Charmander": ("Adamant", "Timid", "Jolly", "Modest"),
}


def rpc(name: str, data: dict) -> object:
    request = urllib.request.Request(
        RPC_URL + name,
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def smogon_alias(name: str) -> str:
    alias = re.sub(r"[.']", "", name.lower()).replace(" ", "-")
    return re.sub(r"-+", "-", alias)


def species_key(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def fetch_natures(pokemon: dict) -> tuple[str, Counter, list[str]]:
    data = rpc(
        "dump-pokemon",
        {
            "gen": GENERATION,
            "alias": smogon_alias(pokemon["name"]),
            "language": "en",
        },
    ) or {}
    counts = Counter()
    order = []

    for strategy in data.get("strategies") or []:
        for moveset in strategy.get("movesets") or []:
            for nature in moveset.get("natures") or []:
                counts[nature] += 1
                order.append(nature)

    return pokemon["name"], counts, order


def ranked_natures(counts: Counter, order: list[str]) -> list[str]:
    return sorted(counts, key=lambda nature: (-counts[nature], order.index(nature)))


def get_archetype_natures(pokemon: dict) -> list[str]:
    attack = pokemon["atk"]
    defense = pokemon["def"]
    sp_attack = pokemon["spa"]
    sp_defense = pokemon["spd"]
    speed = pokemon["spe"]
    slow = speed <= 55

    if attack >= sp_attack + 15:
        return [
            "Adamant",
            "Brave" if slow else "Jolly",
            "Impish",
            "Careful",
            "Jolly" if slow else "Brave",
        ]
    if sp_attack >= attack + 15:
        return [
            "Modest",
            "Quiet" if slow else "Timid",
            "Bold",
            "Calm",
            "Timid" if slow else "Quiet",
        ]
    if defense + sp_defense >= attack + sp_attack + 25:
        return ["Bold", "Calm", "Impish", "Careful"]
    if speed >= 85:
        return ["Adamant", "Modest", "Jolly", "Timid", "Naive", "Hasty"]
    if slow:
        return ["Adamant", "Modest", "Brave", "Quiet", "Sassy", "Relaxed"]
    return ["Adamant", "Modest", "Jolly", "Timid", "Naughty", "Rash"]


def get_family(name: str, graph: dict[str, set[str]]) -> set[str]:
    family = {name}
    pending = [name]

    while pending:
        current = pending.pop()
        for relative in graph[current]:
            if relative not in family:
                family.add(relative)
                pending.append(relative)

    return family


def build_pool(
    name: str,
    pokemon_by_name: dict[str, dict],
    recommendations: dict[str, tuple[Counter, list[str]]],
    graph: dict[str, set[str]],
) -> list[str]:
    if name in POOL_OVERRIDES:
        return list(POOL_OVERRIDES[name])

    direct_counts, direct_order = recommendations[name]
    direct = ranked_natures(direct_counts, direct_order)
    family_counts = Counter()
    family_order = []

    for relative in sorted(get_family(name, graph)):
        counts, order = recommendations[relative]
        family_counts.update(counts)
        family_order.extend(order)

    familial = (
        ranked_natures(family_counts, family_order)
        if family_order
        else []
    )
    result = []

    def add(candidates: list[str] | tuple[str, ...]) -> None:
        for nature in candidates:
            if nature not in result and len(result) < 4:
                result.append(nature)

    if direct:
        add(direct)
        add(get_archetype_natures(pokemon_by_name[name]))
        add(familial)
    else:
        add(familial)
        add(get_archetype_natures(pokemon_by_name[name]))

    add(NATURE_FALLBACK)
    return result


def get_species_macros(constants_path: Path) -> list[tuple[int, str]]:
    constants = constants_path.read_text(encoding="utf-8")
    species = []

    for macro, value in re.findall(
        r"^#define (SPECIES_[A-Z0-9_]+) +(\d+)$",
        constants,
        re.MULTILINE,
    ):
        species_id = int(value)
        if 1 <= species_id <= 414 and macro != "SPECIES_EGG":
            species.append((species_id, macro))

    return sorted(species)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("src/data/pokemon/species_natures.h"),
    )
    parser.add_argument(
        "--species-constants",
        type=Path,
        default=Path("include/constants/species.h"),
    )
    args = parser.parse_args()

    basics = rpc("dump-basics", {"gen": GENERATION})
    pokemon = [
        entry
        for entry in basics["pokemon"]
        if (entry.get("oob") or {}).get("dex_number", 999) <= 386
        and entry.get("isNonstandard") == "Standard"
    ]
    pokemon_by_name = {entry["name"]: entry for entry in pokemon}
    pokemon_by_key = {species_key(entry["name"]): entry for entry in pokemon}

    with ThreadPoolExecutor(max_workers=8) as executor:
        fetched = executor.map(fetch_natures, pokemon)
    recommendations = {
        name: (counts, order)
        for name, counts, order in fetched
    }

    graph = {name: set() for name in pokemon_by_name}
    for name, entry in pokemon_by_name.items():
        for evolution in (entry.get("oob") or {}).get("evos") or []:
            if evolution in graph:
                graph[name].add(evolution)
                graph[evolution].add(name)

    lines = [
        "#define NATURE_BIT(nature) (1u << (nature))",
        "#define NATURE_POOL(a, b, c, d) \\",
        "    (NATURE_BIT(a) | NATURE_BIT(b) | NATURE_BIT(c) | NATURE_BIT(d))",
        "",
        "// Based on Smogon RS analyses. Missing slots use family roles and base stats.",
        "static const u32 sSpeciesNatureMasks[NUM_SPECIES] =",
        "{",
    ]

    for species_id, macro in get_species_macros(args.species_constants):
        if 252 <= species_id <= 276:
            name = "Unown"
        else:
            key = macro.removeprefix("SPECIES_").replace("_", "")
            if key not in pokemon_by_key:
                raise ValueError(f"No Smogon species match for {macro}")
            name = pokemon_by_key[key]["name"]

        pool = build_pool(name, pokemon_by_name, recommendations, graph)
        nature_constants = ", ".join(
            f"NATURE_{nature.upper()}"
            for nature in pool
        )
        lines.append(
            f"    [{macro:<24}] = NATURE_POOL({nature_constants}),"
        )

    lines.extend(
        [
            "};",
            "",
            "#undef NATURE_POOL",
            "#undef NATURE_BIT",
            "",
        ]
    )
    args.output.write_text("\n".join(lines), encoding="ascii")


if __name__ == "__main__":
    main()
