"""Strict importer for the canonical 1,000-channel CSV catalogue."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .risk_router import ACTION_COLUMNS, ActionRisk, RiskCellError, parse_action_risk

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_CSV = PROJECT_ROOT / "data" / "saas_marketing_1000_channels_ranked - 1000 Channels.csv"
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

    @classmethod
    def load(cls, path: str | Path = CANONICAL_CSV, *, require_1000: bool = True) -> "ChannelCatalogue":
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
