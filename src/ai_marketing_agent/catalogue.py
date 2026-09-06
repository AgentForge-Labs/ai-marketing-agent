"""Strict importer for the canonical 1,000-channel CSV catalogue."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Optional

from .risk_router import ACTION_COLUMNS, ACTIONS_WITHOUT_COLUMNS, ActionRisk, RiskCellError, parse_action_risk

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_CSV = PROJECT_ROOT / "data" / "saas_marketing_1000_channels_ranked - 1000 Channels.csv"
PILOT_CELLS = PROJECT_ROOT / "data" / "pilot_action_cells.json"
REQUIRED_BASE_COLUMNS = frozenset({"#", "Site", "Domain", "Channel Type"})
EXPECTED_ACTION_RISK_MODEL_PREFIX = "action-medium-v1:"


class CatalogueValidationError(ValueError):
    """Raised when the canonical catalogue cannot safely drive runtime routing."""


@dataclass(frozen=True, slots=True)
class Channel:
    rank: int
    site: str
    domain: str
    channel_type: str
    action_risks: Mapping[str, ActionRisk]
    raw: Mapping[str, str]


class ChannelCatalogue:
    def __init__(self, channels: tuple[Channel, ...], source: Path) -> None:
        self.channels = channels
        self.source = source
        self._by_rank = {channel.rank: channel for channel in channels}
        by_domain: dict[str, list[Channel]] = {}
        for channel in channels:
            by_domain.setdefault(self._normalize_domain(channel.domain), []).append(channel)
        self._by_domain = {domain: tuple(matches) for domain, matches in by_domain.items()}

    def __len__(self) -> int:
        return len(self.channels)

    def __iter__(self):
        return iter(self.channels)

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        value = domain.strip().lower().rstrip(".")
        return value[4:] if value.startswith("www.") else value

    @staticmethod
    def pilot_raw_cells(overrides_path: Optional[Path] = PILOT_CELLS) -> dict[str, dict[str, str]]:
        """Raw pilot cell strings per domain (provenance for storage import)."""
        if overrides_path is None or not overrides_path.exists():
            return {}
        try:
            raw = json.loads(overrides_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(raw, dict):
            return {}
        return {
            ChannelCatalogue._normalize_domain(str(domain)): dict(cells)
            for domain, cells in raw.items()
            if not str(domain).startswith("_") and isinstance(cells, dict)
        }

    @staticmethod
    def _load_pilot_cells(overrides_path: Optional[Path]) -> dict[str, dict[str, ActionRisk]]:
        """Reviewed per-domain cells for actions without CSV columns (#33).

        Format: {"domain": {"register": "<cell>", "login": "<cell>"}} using the
        exact canonical cell grammar (validated by parse_action_risk).
        """
        if overrides_path is None or not overrides_path.exists():
            return {}
        try:
            raw = json.loads(overrides_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CatalogueValidationError(f"cannot read pilot cells {overrides_path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise CatalogueValidationError("pilot cells must be an object")
        out: dict[str, dict[str, ActionRisk]] = {}
        for domain, cells in raw.items():
            if str(domain).startswith("_"):
                continue  # _note and other metadata keys
            if not isinstance(cells, dict):
                raise CatalogueValidationError(f"pilot cells for {domain!r} must be an object")
            parsed: dict[str, ActionRisk] = {}
            for action, cell in cells.items():
                if action not in ACTIONS_WITHOUT_COLUMNS:
                    raise CatalogueValidationError(
                        f"pilot cells only allow {sorted(ACTIONS_WITHOUT_COLUMNS)}, got {action!r}")
                try:
                    parsed[action] = parse_action_risk(cell)
                except RiskCellError as exc:
                    raise CatalogueValidationError(
                        f"pilot cell {domain!r}/{action}: {exc}") from exc
            out[ChannelCatalogue._normalize_domain(str(domain))] = parsed
        return out

    @classmethod
    def load(cls, path: str | Path = CANONICAL_CSV, *, require_1000: bool = True,
             overrides_path: Optional[Path] = PILOT_CELLS) -> "ChannelCatalogue":
        source = Path(path)
        try:
            with source.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
        except OSError as exc:
            raise CatalogueValidationError(f"cannot read canonical catalogue {source}: {exc}") from exc

        if len(rows) < 5:
            raise CatalogueValidationError("catalogue is missing metadata/header/data rows")

        header = rows[3]
        if not header or len(set(header)) != len(header):
            raise CatalogueValidationError("catalogue header is empty or contains duplicate columns")

        required = REQUIRED_BASE_COLUMNS.union(ACTION_COLUMNS.values()).union({"Action Risk Model"})
        missing = required.difference(header)
        if missing:
            raise CatalogueValidationError(f"catalogue is missing required columns: {', '.join(sorted(missing))}")

        width = len(header)
        channels: list[Channel] = []
        for csv_line, row in enumerate(rows[4:], start=5):
            if len(row) != width:
                raise CatalogueValidationError(
                    f"line {csv_line}: expected {width} columns, found {len(row)}"
                )
            record = dict(zip(header, row, strict=True))
            try:
                rank = int(record["#"])
            except (TypeError, ValueError) as exc:
                raise CatalogueValidationError(f"line {csv_line}: invalid rank {record.get('#')!r}") from exc

            model = record["Action Risk Model"].strip()
            if not model.startswith(EXPECTED_ACTION_RISK_MODEL_PREFIX):
                raise CatalogueValidationError(
                    f"line {csv_line} rank {rank}: unsupported Action Risk Model {model!r}"
                )

            action_risks: dict[str, ActionRisk] = {}
            for action, column in ACTION_COLUMNS.items():
                try:
                    action_risks[action] = parse_action_risk(record[column])
                except RiskCellError as exc:
                    raise CatalogueValidationError(
                        f"line {csv_line} rank {rank} {record['Site']!r}, column {column!r}: {exc}"
                    ) from exc

            channels.append(
                Channel(
                    rank=rank,
                    site=record["Site"].strip(),
                    domain=record["Domain"].strip(),
                    channel_type=record["Channel Type"].strip(),
                    action_risks=MappingProxyType(action_risks),
                    raw=MappingProxyType(record),
                )
            )

        expected_ranks = list(range(1, len(channels) + 1))
        actual_ranks = [channel.rank for channel in channels]
        if actual_ranks != expected_ranks:
            raise CatalogueValidationError("catalogue ranks must be strictly contiguous starting at 1")
        if require_1000 and len(channels) != 1000:
            raise CatalogueValidationError(f"canonical catalogue must contain exactly 1,000 channels, found {len(channels)}")

        pilot = cls._load_pilot_cells(overrides_path)
        if pilot:
            merged: list[Channel] = []
            for channel in channels:
                extra = pilot.get(cls._normalize_domain(channel.domain))
                if extra:
                    risks = dict(channel.action_risks)
                    risks.update(extra)
                    merged.append(replace(channel, action_risks=MappingProxyType(risks)))
                else:
                    merged.append(channel)
            channels = merged

        return cls(tuple(channels), source)

    def by_rank(self, rank: int) -> Channel | None:
        return self._by_rank.get(rank)

    def by_domain(self, domain: str) -> tuple[Channel, ...]:
        return self._by_domain.get(self._normalize_domain(domain), ())

    def require_unique_domain(self, domain: str) -> Channel:
        matches = self.by_domain(domain)
        if not matches:
            raise KeyError(f"channel domain not found: {domain}")
        if len(matches) != 1:
            raise KeyError(f"channel domain is not unique: {domain} ({len(matches)} matches)")
        return matches[0]
