"""Runtime data shared across the Insnrg Pool platforms."""

from __future__ import annotations

from dataclasses import dataclass

from .coordinator import InsnrgAppCoordinator, InsnrgCoordinator


@dataclass(slots=True)
class InsnrgRuntimeData:
    """Both coordinators backing a single config entry."""

    control: InsnrgCoordinator
    app: InsnrgAppCoordinator
