"""Component factory facade for constructing SUT component bundles."""

from __future__ import annotations

from avf.contracts import ComponentConfig

from .registry import ComponentBundle, ComponentRegistry, component_registry


class ComponentFactory:
    """Build component bundles from validated ComponentConfig values."""

    def __init__(self, registry: ComponentRegistry = component_registry) -> None:
        self.registry = registry

    def build(self, config: ComponentConfig) -> ComponentBundle:
        return self.registry.resolve(config)


def build_component_bundle(config: ComponentConfig) -> ComponentBundle:
    return ComponentFactory().build(config)
