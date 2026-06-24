from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field


ElementStatus = str
EvolutionStatus = str
InteractionStatus = str


@dataclass
class Element:
    node_id: str
    name: str
    center: tuple[float, float]
    size: tuple[float, float]
    movable: bool = False
    blocks_movement: bool = False
    physical_status: ElementStatus = "regular"
    evolution_status: EvolutionStatus = "stable"
    interaction_status: InteractionStatus = "idle"
    # Coarse status fields describe broad shared categories. state_details
    # stores element-specific facts that may matter for future actions, such as
    # door_state=open, flow_state=on, contains=food, or heating_state=running.
    # These details are updated by the environment LLM from the current action
    # and existing element state, keeping the world scene-agnostic without
    # hard-coded rules for each element type.
    state_details: dict[str, str] = field(default_factory=dict)
    default_physical_status: ElementStatus = field(default="regular", init=False)
    default_evolution_status: EvolutionStatus = field(default="stable", init=False)
    default_interaction_status: InteractionStatus = field(default="idle", init=False)
    default_state_details: dict[str, str] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.default_physical_status = self.physical_status
        self.default_evolution_status = self.evolution_status
        self.default_interaction_status = self.interaction_status
        self.default_state_details = deepcopy(self.state_details)

    @property
    def status(self) -> ElementStatus:
        return self.physical_status

    @status.setter
    def status(self, value: ElementStatus) -> None:
        self.physical_status = value

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "center": list(self.center),
            "size": list(self.size),
            "movable": self.movable,
            "blocks_movement": self.blocks_movement,
            "physical_status": self.physical_status,
            "evolution_status": self.evolution_status,
            "interaction_status": self.interaction_status,
            "state_details": dict(self.state_details),
            "default_physical_status": self.default_physical_status,
            "default_evolution_status": self.default_evolution_status,
            "default_interaction_status": self.default_interaction_status,
            "default_state_details": dict(self.default_state_details),
        }

    def reset_status(self) -> None:
        self.physical_status = self.default_physical_status
        self.evolution_status = self.default_evolution_status
        self.interaction_status = self.default_interaction_status
        self.state_details = deepcopy(self.default_state_details)

    def set_status(self, status: ElementStatus, *, evolution_status: EvolutionStatus | None = None) -> None:
        self.physical_status = status
        if evolution_status is not None:
            self.evolution_status = evolution_status

    def set_physical_status(self, status: ElementStatus) -> None:
        self.physical_status = status

    def set_evolution_status(self, evolution_status: EvolutionStatus) -> None:
        self.evolution_status = evolution_status

    def set_interaction_status(self, interaction_status: InteractionStatus) -> None:
        self.interaction_status = interaction_status

    def update_state_details(self, state_details: dict[str, str]) -> None:
        for key, value in state_details.items():
            cleaned_key = str(key).strip()
            if not cleaned_key:
                continue
            cleaned_value = str(value).strip()
            if cleaned_value:
                self.state_details[cleaned_key] = cleaned_value


@dataclass
class Area:
    node_id: str
    name: str
    bounds: tuple[float, float, float, float]
    metadata: dict[str, str] = field(default_factory=dict)
    elements: list[Element] = field(default_factory=list)

    def add(self, element: Element) -> None:
        self.elements.append(element)

    def find_element(self, element_id: str) -> Element | None:
        for element in self.elements:
            if element.node_id == element_id:
                return element
        return None

    def find_element_by_name(self, element_name: str) -> Element | None:
        for element in self.elements:
            if element.name == element_name:
                return element
        return None

    def reset_statuses(self) -> None:
        for element in self.elements:
            element.reset_status()

    def print_elements(self) -> None:
        print(f"[{self.node_id}] {self.name}")
        for element in self.elements:
            print(
                f"  - {element.node_id}: {element.name} "
                f"center={element.center} size={element.size} "
                f"movable={element.movable} "
                f"blocks_movement={element.blocks_movement} "
                f"physical_status={element.physical_status} "
                f"evolution_status={element.evolution_status} "
                f"interaction_status={element.interaction_status} "
                f"state_details={element.state_details}"
            )

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "bounds": list(self.bounds),
            "metadata": dict(self.metadata),
            "elements": [element.to_dict() for element in self.elements],
        }


@dataclass
class Home:
    node_id: str
    name: str
    default_agent_start: tuple[float, float] | None = None
    portals: list[dict] = field(default_factory=list)
    rendering: dict = field(default_factory=dict)
    areas: list[Area] = field(default_factory=list)

    def add(self, area: Area) -> None:
        self.areas.append(area)

    def find_area(self, area_id: str) -> Area | None:
        for area in self.areas:
            if area.node_id == area_id:
                return area
        return None

    def find_element(self, element_id: str) -> Element | None:
        for area in self.areas:
            element = area.find_element(element_id)
            if element is not None:
                return element
        return None

    def find_element_by_name(self, element_name: str) -> Element | None:
        for area in self.areas:
            element = area.find_element_by_name(element_name)
            if element is not None:
                return element
        return None

    def get_all_elements(self) -> list[Element]:
        elements: list[Element] = []
        for area in self.areas:
            elements.extend(area.elements)
        return elements

    def get_element_by_index(self, index: int) -> Element | None:
        elements = self.get_all_elements()
        if 0 <= index < len(elements):
            return elements[index]
        return None

    def reset_all_statuses(self) -> None:
        for area in self.areas:
            area.reset_statuses()

    def update_element_status(
        self,
        status: ElementStatus,
        *,
        node_id: str | None = None,
        name: str | None = None,
        index: int | None = None,
        evolution_status: EvolutionStatus | None = None,
    ) -> Element | None:
        element = None
        if node_id is not None:
            element = self.find_element(node_id)
        elif name is not None:
            element = self.find_element_by_name(name)
        elif index is not None:
            element = self.get_element_by_index(index)

        if element is None:
            return None

        element.set_status(status, evolution_status=evolution_status)
        return element

    def update_element_evolution_status(
        self,
        evolution_status: EvolutionStatus,
        *,
        node_id: str | None = None,
        name: str | None = None,
        index: int | None = None,
    ) -> Element | None:
        element = None
        if node_id is not None:
            element = self.find_element(node_id)
        elif name is not None:
            element = self.find_element_by_name(name)
        elif index is not None:
            element = self.get_element_by_index(index)

        if element is None:
            return None

        element.set_evolution_status(evolution_status)
        return element

    def update_element_interaction_status(
        self,
        interaction_status: InteractionStatus,
        *,
        node_id: str | None = None,
        name: str | None = None,
        index: int | None = None,
    ) -> Element | None:
        element = None
        if node_id is not None:
            element = self.find_element(node_id)
        elif name is not None:
            element = self.find_element_by_name(name)
        elif index is not None:
            element = self.get_element_by_index(index)

        if element is None:
            return None

        element.set_interaction_status(interaction_status)
        return element

    def print_area_elements(self, area_id: str) -> None:
        area = self.find_area(area_id)
        if area is None:
            print(f"Area not found: {area_id}")
            return
        area.print_elements()

    def print_tree(self) -> None:
        print(f"/{self.node_id} ({self.name})")
        for area in self.areas:
            print(f"  /{area.node_id} ({area.name})")
            for element in area.elements:
                print(f"    /{element.node_id} ({element.name})")

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "default_agent_start": list(self.default_agent_start) if self.default_agent_start is not None else None,
            "portals": deepcopy(self.portals),
            "rendering": deepcopy(self.rendering),
            "areas": [area.to_dict() for area in self.areas],
        }
