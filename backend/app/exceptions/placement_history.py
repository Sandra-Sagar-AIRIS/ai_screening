"""AIR-504: Placement history immutability errors."""


class ImmutablePlacementHistoryError(RuntimeError):
    """Placement history rows are append-only; updates and direct deletes are not allowed."""
