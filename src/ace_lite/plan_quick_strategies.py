"""Intent and domain strategy facade for plan_quick optimization."""

from __future__ import annotations

from ace_lite.plan_quick_strategies_boost import (
    BoostResult,
    BoostStrategy,
    BoostStrategyRegistry,
)
from ace_lite.plan_quick_strategies_domain import (
    DomainMatch,
    DomainStrategy,
    DomainStrategyRegistry,
)
from ace_lite.plan_quick_strategies_intent import (
    IntentStrategy,
    IntentStrategyRegistry,
)
from ace_lite.plan_quick_strategies_shared import (
    DOC_ENTRYPOINT_BASENAMES,
    DOC_PREFERRED_PREFIXES,
    DOC_PRIMARY_NAME_MARKERS,
    DOC_SECONDARY_NAME_MARKERS,
    QUERY_DOC_SYNC_MARKERS,
    QUERY_LATEST_MARKERS,
    QUERY_ONBOARDING_MARKERS,
    NormalizationUtils,
    QueryFlags,
    _extract_path_date,
    _extract_req_ids,
)

__all__ = [
    "DOC_ENTRYPOINT_BASENAMES",
    "DOC_PREFERRED_PREFIXES",
    "DOC_PRIMARY_NAME_MARKERS",
    "DOC_SECONDARY_NAME_MARKERS",
    "QUERY_DOC_SYNC_MARKERS",
    "QUERY_LATEST_MARKERS",
    "QUERY_ONBOARDING_MARKERS",
    "BoostResult",
    "BoostStrategy",
    "BoostStrategyRegistry",
    "DomainMatch",
    "DomainStrategy",
    "DomainStrategyRegistry",
    "IntentStrategy",
    "IntentStrategyRegistry",
    "NormalizationUtils",
    "QueryFlags",
    "_extract_path_date",
    "_extract_req_ids",
]
