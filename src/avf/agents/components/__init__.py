"""Component registry and factory for SUT module selection."""

from .factory import ComponentFactory, build_component_bundle
from .registry import ComponentBundle, ComponentDescriptor, ComponentRegistry, component_registry

__all__ = [
    "ComponentBundle",
    "ComponentDescriptor",
    "ComponentFactory",
    "ComponentRegistry",
    "build_component_bundle",
    "component_registry",
]
