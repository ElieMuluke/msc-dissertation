"""Parse the downloaded sanctions list files into a common entry shape.

Pure generator functions (no I/O side effects beyond reading the file), mirroring
``ingestion.tabular.loaders``: each yields :class:`WatchlistEntry` rows that the service
layer indexes for name lookup. File formats are documented in
``backend/data/watchlists/manifest.json``.
"""

from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

# OFAC's headerless SDN CSV uses "-0-" (with stray trailing spaces) for null fields.
_OFAC_NULL = "-0-"


@dataclass(frozen=True)
class WatchlistEntry:
    """One sanctioned individual/entity, normalised across the three source lists.

    Attributes:
        list_name: Which list the entry came from (``OFAC SDN`` / ``HMT`` / ``UN``).
        entry_id: The list's own identifier (ent_num / Group ID / DATAID).
        name: Primary display name.
        entity_type: ``individual`` / ``entity`` / ``vessel`` / ... (lowercased, list-specific).
        programs: Sanctions programme/regime tags, e.g. ``["IRAN-EO13902"]``.
        remarks: Free-text remarks/other information (truncated by the service for tool output).
    """

    list_name: str
    entry_id: str
    name: str
    entity_type: str
    programs: tuple[str, ...]
    remarks: str


def _clean_ofac(value: str) -> str:
    value = value.strip()
    return "" if value == _OFAC_NULL else value


def iter_ofac_sdn(path: Union[str, Path]) -> Iterator[WatchlistEntry]:
    """Yield entries from the OFAC SDN CSV (headerless, ``-0-`` = null).

    Columns: ent_num, SDN_Name, SDN_Type, Program, Title, Call_Sign, Vess_type,
    Tonnage, GRT, Vess_flag, Vess_owner, Remarks.
    """
    with Path(path).open(encoding="latin-1", newline="") as f:
        for fields in csv.reader(f):
            if len(fields) < 4:
                continue
            name = _clean_ofac(fields[1])
            if not name:
                continue
            yield WatchlistEntry(
                list_name="OFAC SDN",
                entry_id=_clean_ofac(fields[0]),
                name=name,
                entity_type=_clean_ofac(fields[2]).lower() or "entity",
                programs=tuple(p.strip() for p in _clean_ofac(fields[3]).split(";") if p.strip()),
                remarks=_clean_ofac(fields[-1]),
            )


def iter_hmt_conlist(path: Union[str, Path]) -> Iterator[WatchlistEntry]:
    """Yield entries from the HM Treasury/OFSI consolidated list CSV.

    Line 1 is ``Last Updated,<date>``; line 2 is the header. The primary name is split
    across ``Name 6`` (surname/single name) and ``Name 1``..``Name 5`` (forenames);
    alias rows share the same ``Group ID`` and are yielded as separate entries so alias
    names are searchable too.
    """
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        first = f.readline()  # "Last Updated,<date>" banner line — skip.
        if not first.lower().startswith("last updated"):
            f.seek(0)
        for row in csv.DictReader(f):
            forenames = " ".join(
                part for part in ((row.get(f"Name {i}") or "").strip() for i in range(1, 6)) if part
            )
            surname = (row.get("Name 6") or "").strip()
            name = " ".join(part for part in (forenames, surname) if part)
            if not name:
                continue
            regime = (row.get("Regime") or "").strip()
            yield WatchlistEntry(
                list_name="HMT",
                entry_id=(row.get("Group ID") or "").strip(),
                name=name,
                entity_type=(row.get("Group Type") or "").strip().lower() or "entity",
                programs=(regime,) if regime else (),
                remarks=(row.get("Other Information") or "").strip(),
            )


def iter_un_consolidated(path: Union[str, Path]) -> Iterator[WatchlistEntry]:
    """Yield entries from the UN Security Council consolidated list XML.

    ``INDIVIDUALS/INDIVIDUAL`` names are FIRST_NAME..FOURTH_NAME concatenated;
    ``ENTITIES/ENTITY`` names live in FIRST_NAME. Aliases (``*_ALIAS/ALIAS_NAME``)
    are yielded as separate entries so alias names are searchable too.
    """
    root = ET.parse(Path(path)).getroot()

    def text(node: Optional[ET.Element], tag: str) -> str:
        child = node.find(tag) if node is not None else None
        return (child.text or "").strip() if child is not None and child.text else ""

    def aliases(node: ET.Element, container: str) -> Iterator[str]:
        for alias in node.findall(container):
            alias_name = text(alias, "ALIAS_NAME")
            if alias_name:
                yield alias_name

    for individual in root.iterfind("INDIVIDUALS/INDIVIDUAL"):
        name = " ".join(
            part
            for part in (
                text(individual, "FIRST_NAME"),
                text(individual, "SECOND_NAME"),
                text(individual, "THIRD_NAME"),
                text(individual, "FOURTH_NAME"),
            )
            if part
        )
        entry_id = text(individual, "DATAID")
        regime = text(individual, "UN_LIST_TYPE")
        remarks = text(individual, "COMMENTS1")
        names = [name, *aliases(individual, "INDIVIDUAL_ALIAS")]
        for candidate in names:
            if candidate:
                yield WatchlistEntry(
                    list_name="UN",
                    entry_id=entry_id,
                    name=candidate,
                    entity_type="individual",
                    programs=(regime,) if regime else (),
                    remarks=remarks,
                )

    for entity in root.iterfind("ENTITIES/ENTITY"):
        entry_id = text(entity, "DATAID")
        regime = text(entity, "UN_LIST_TYPE")
        remarks = text(entity, "COMMENTS1")
        names = [text(entity, "FIRST_NAME"), *aliases(entity, "ENTITY_ALIAS")]
        for candidate in names:
            if candidate:
                yield WatchlistEntry(
                    list_name="UN",
                    entry_id=entry_id,
                    name=candidate,
                    entity_type="entity",
                    programs=(regime,) if regime else (),
                    remarks=remarks,
                )


def load_fatf_lists(path: Union[str, Path]) -> dict:
    """Load the FATF jurisdictions JSON (call-for-action + increased-monitoring + aliases).

    Returns the parsed dict as-is; the service layer builds its lookup table from it.
    See ``backend/data/watchlists/fatf_high_risk.json`` for the shape and provenance.
    """
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)
