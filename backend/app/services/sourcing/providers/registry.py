"""Provider registry — maps provider_id → class (not singleton, DB-aware providers are instantiated per-request)."""
from __future__ import annotations

from app.services.sourcing.providers.naukri_stub import NaukriStubProvider

# Providers that don't require a DB session (instantiated once)
STATELESS_PROVIDER_CLASSES: dict[str, type] = {
    NaukriStubProvider.provider_id: NaukriStubProvider,
}

# Providers that require a DB session are instantiated in the runner with db injected.
# AirisCandidateProvider is always included; it is constructed in the runner.
DB_PROVIDER_IDS: list[str] = ["airis"]

ALL_PROVIDER_IDS: list[str] = DB_PROVIDER_IDS + list(STATELESS_PROVIDER_CLASSES.keys())
