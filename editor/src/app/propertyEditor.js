export function renderPropertyEditor(container, store) {
  const state = store.snapshot();
  container.innerHTML = "";
  container.appendChild(sceneSection(state.scene, store));
  container.appendChild(areasSection(state, store));
  container.appendChild(roadsEditorSection(state.scene, store));
  container.appendChild(wallsEditorSection(state.scene, store));
  container.appendChild(portalsEditorSection(state.scene, store));
  updatePropertyHighlights(container, state);
}

export function updatePropertyHighlights(container, state) {
  container.querySelectorAll("[data-area-id]").forEach((node) => {
    const id = node.dataset.areaId;
    node.classList.toggle("selected", id === state.selectedAreaId);
    if (id === state.selectedAreaId && node.tagName === "DETAILS") {
      node.open = true;
    }
  });
  container.querySelectorAll("[data-element-id]").forEach((node) => {
    const id = node.dataset.elementId;
    node.classList.toggle("hovered", id === state.hoveredId);
    node.classList.toggle("selected", id === state.selectedId);
    if (id === state.selectedId && node.tagName === "DETAILS") {
      node.open = true;
      const area = node.closest("[data-area-id]");
      if (area?.tagName === "DETAILS") {
        area.open = true;
      }
    }
  });
  container.querySelectorAll("[data-spatial-type][data-spatial-id]").forEach((node) => {
    const selected = state.selectedSpatial
      && node.dataset.spatialType === state.selectedSpatial.type
      && node.dataset.spatialId === state.selectedSpatial.id;
    node.classList.toggle("selected", Boolean(selected));
    if (selected && node.tagName === "DETAILS") {
      node.open = true;
    }
  });
}

export function scrollSelectionIntoView(container, state) {
  const selector = selectionSelector(state);
  if (!selector) {
    return;
  }
  const node = container.querySelector(selector);
  if (!node) {
    return;
  }
  openDetailsPath(node);
  window.requestAnimationFrame(() => {
    node.scrollIntoView({ behavior: "smooth", block: "center" });
  });
}

function selectionSelector(state) {
  if (state.selectedId) {
    return `[data-element-id="${CSS.escape(state.selectedId)}"]`;
  }
  if (state.selectedAreaId) {
    return `[data-area-id="${CSS.escape(state.selectedAreaId)}"]`;
  }
  if (state.selectedSpatial?.type && state.selectedSpatial?.id) {
    return `[data-spatial-type="${CSS.escape(state.selectedSpatial.type)}"][data-spatial-id="${CSS.escape(state.selectedSpatial.id)}"]`;
  }
  return null;
}

function openDetailsPath(node) {
  let current = node;
  while (current && current.nodeType === Node.ELEMENT_NODE) {
    if (current.tagName === "DETAILS") {
      current.open = true;
    }
    current = current.parentElement;
  }
}

function sceneSection(scene, store) {
  return section("Scene", "Scene", [
    field("node_id", textInput(scene.node_id, (value) => store.updateSceneField("node_id", value))),
    field("name", textInput(scene.name, (value) => store.updateSceneField("name", value))),
  ]);
}

function areasSection(state, store) {
  const body = document.createElement("div");
  for (const area of state.scene.areas) {
    body.appendChild(areaCard(area, store, state));
  }
  return section("Areas", "Areas", [body], null);
}

function areaCard(area, store, state) {
  const details = document.createElement("details");
  details.className = "object-card area-card";
  details.dataset.areaId = area.node_id;
  details.open = state.selectedAreaId === area.node_id || (state.selectedId ? area.elements.some((element) => element.node_id === state.selectedId) : false);
  details.addEventListener("pointerdown", (event) => {
    if (event.target.closest("summary") || event.target.closest("button") || event.target.closest("[data-element-id]")) return;
    store.setSelectedArea(area.node_id);
  });

  const header = document.createElement("summary");
  header.className = "object-header sticky-object-header";

  const title = document.createElement("div");
  title.className = "object-title";
  title.textContent = `${area.name} (${area.node_id})`;

  const isChildScene = Boolean(state.scene.metadata?.editor_child_scene);
  const openScene = iconButton("...", isChildScene ? "Return to parent scene" : "Open linked scene", () => store.openAreaScene(area));
  openScene.disabled = !isChildScene && isRoadArea(area);
  header.append(title, openScene);
  bindSummaryToggle(details, header);

  const fields = document.createElement("div");
  fields.className = "collapsible-fields";
  fields.append(
    field("area id", textInput(area.node_id, (value) => store.updateAreaObject(area, "node_id", value))),
    field("name", textInput(area.name, (value) => store.updateAreaObject(area, "name", value))),
    field("bounds", boundsInputs(area.bounds, (index, value) => store.updateAreaBoundsObject(area, index, value))),
    field("locked", checkboxInput(area.metadata?.locked, (value) => store.updateAreaLockedObject(area, value))),
    field("space", selectInput(area.metadata?.space || "outdoor", ["indoor", "outdoor"], (value) => store.updateAreaMetadataObject(area, "space", value))),
    field("type", textInput(area.metadata?.area_type || "", (value) => store.updateAreaMetadataObject(area, "area_type", value))),
  );

  const elementDetails = document.createElement("details");
  elementDetails.open = true;
  const summary = document.createElement("summary");
  summary.className = "section-summary nested-summary";
  const label = document.createElement("span");
  label.className = "section-title";
  label.textContent = `Elements (${area.elements.length})`;
  summary.append(label, iconButton("+", "Add element", () => store.addElement(area.node_id)));

  const elements = document.createElement("div");
  elements.className = "section-body";
  for (const element of area.elements) {
    elements.appendChild(elementCard(element, store, state));
  }
  elementDetails.append(summary, elements);
  bindSummaryToggle(elementDetails, summary);
  details.append(header, fields, elementDetails);
  return details;
}

function elementCard(element, store, state) {
  const card = document.createElement("details");
  card.className = "object-card";
  card.dataset.elementId = element.node_id;
  card.addEventListener("pointerdown", (event) => {
    if (event.target.closest("summary") || event.target.closest("button")) return;
    store.setSelected(element.node_id);
  });
  if (state.hoveredId === element.node_id) card.classList.add("hovered");
  if (state.selectedId === element.node_id) card.classList.add("selected");
  card.open = state.selectedId === element.node_id;

  card.addEventListener("mouseenter", () => store.setHover(element.node_id));
  card.addEventListener("mouseleave", () => store.setHover(null));

  const header = document.createElement("summary");
  header.className = "object-header";

  const title = document.createElement("div");
  title.className = "object-title";
  title.textContent = `${element.name} (${element.node_id})`;

  const duplicate = iconButton("⧉", "Duplicate element", () => store.duplicateElement(element.node_id));
  const remove = iconButton("×", "Delete element", () => store.deleteElement(element.node_id));
  remove.classList.add("danger");
  header.append(title, duplicate, remove);
  bindSummaryToggle(card, header);

  const fields = document.createElement("div");
  fields.className = "collapsible-fields";
  fields.append(
    field("node_id", textInput(element.node_id, (value) => store.updateElementObject(element, "node_id", value))),
    field("name", textInput(element.name, (value) => store.updateElementObject(element, "name", value))),
    field("center", pairInputs(element.center, (index, value) => store.updateElementVectorObject(element, "center", index, value))),
    field("size", pairInputs(element.size, (index, value) => store.updateElementVectorObject(element, "size", index, value))),
    field("locked", checkboxInput(element.locked, (value) => store.updateElementObject(element, "locked", value))),
    field("movable", checkboxInput(element.movable !== false, (value) => store.updateElementObject(element, "movable", value))),
    field("blocks", checkboxInput(element.blocks_movement, (value) => store.updateElementObject(element, "blocks_movement", value))),
    field("physical", textInput(element.physical_status, (value) => store.updateElementObject(element, "physical_status", value))),
    field("evolution", textInput(element.evolution_status, (value) => store.updateElementObject(element, "evolution_status", value))),
    field("interaction", textInput(element.interaction_status, (value) => store.updateElementObject(element, "interaction_status", value))),
    field("state", textareaInput(JSON.stringify(element.state_details || {}, null, 2), (value) => store.updateElementStateDetailsObject(element, value))),
  );

  card.append(header, fields);
  return card;
}

function portalsEditorSection(scene, store) {
  const body = document.createElement("div");
  for (const portal of scene.portals || []) {
    const card = document.createElement("div");
    card.className = "object-card";
    card.dataset.spatialType = "portal";
    card.dataset.spatialId = portal.id;
    const header = document.createElement("div");
    header.className = "object-header";
    const title = document.createElement("div");
    title.className = "object-title";
    title.textContent = `${portal.name} (${portal.kind})`;
    header.append(title);
    const fields = document.createElement("div");
    fields.className = "collapsible-fields";
    fields.append(
      field("id", textInput(portal.id, (value) => store.updatePortalObject(portal, "id", value))),
      field("name", textInput(portal.name, (value) => store.updatePortalObject(portal, "name", value))),
      field("locked", checkboxInput(portal.locked, (value) => store.updatePortalObject(portal, "locked", value))),
      field("role", selectInput(portal.role || "passage", ["passage", "connection"], (value) => store.updatePortalObject(portal, "role", value))),
      field("kind", selectInput(portal.kind || "open_passage", ["open_passage", "geometry_join", "road_junction", "building_entrance", "door"], (value) => store.updatePortalObject(portal, "kind", value))),
      readonlyField("from", endpointLabel(portal.endpoints?.[0])),
      readonlyField("to", endpointLabel(portal.endpoints?.[1])),
      field("start", pairInputs(portal.segment[0], (index, value) => store.updatePortalSegmentObject(portal, 0, index, value))),
      field("end", pairInputs(portal.segment[1], (index, value) => store.updatePortalSegmentObject(portal, 1, index, value))),
    );
    card.append(header, fields);
    body.append(card);
  }
  return section("Portals", "Portals", [body], null);
}

function roadsEditorSection(scene, store) {
  const body = document.createElement("div");
  for (const road of scene.roads?.segments || []) {
    const card = document.createElement("div");
    card.className = "object-card";
    card.dataset.spatialType = "road_segment";
    card.dataset.spatialId = road.road_id;
    const header = document.createElement("div");
    header.className = "object-header";
    const title = document.createElement("div");
    title.className = "object-title";
    title.textContent = `${road.name} (${road.road_id})`;
    header.append(title);
    const fields = document.createElement("div");
    fields.className = "collapsible-fields";
    fields.append(
      readonlyField("type", "segment"),
      field("locked", checkboxInput(road.locked, (value) => store.updateRoadObject(road, "locked", value))),
      field("top y", numberInput(road.top.y, (value) => store.updateRoadEdgeObject(road, "top", "y", value))),
      field("top x", pairInputs([road.top.x1, road.top.x2], (index, value) => store.updateRoadEdgeObject(road, "top", index === 0 ? "x1" : "x2", value))),
      field("bottom y", numberInput(road.bottom.y, (value) => store.updateRoadEdgeObject(road, "bottom", "y", value))),
      field("bottom x", pairInputs([road.bottom.x1, road.bottom.x2], (index, value) => store.updateRoadEdgeObject(road, "bottom", index === 0 ? "x1" : "x2", value))),
    );
    card.append(header, fields);
    body.append(card);
  }
  for (const intersection of scene.roads?.intersections || []) {
    const card = document.createElement("div");
    card.className = "object-card";
    card.dataset.spatialType = "road_intersection";
    card.dataset.spatialId = intersection.intersection_id;
    const header = document.createElement("div");
    header.className = "object-header";
    const title = document.createElement("div");
    title.className = "object-title";
    title.textContent = `${intersection.name} (${intersection.intersection_id})`;
    header.append(title);
    const fields = document.createElement("div");
    fields.className = "collapsible-fields";
    fields.append(
      readonlyField("type", "intersection"),
      field("locked", checkboxInput(intersection.locked, (value) => store.updateIntersectionObject(intersection, "locked", value))),
      field("bounds", boundsInputs(intersection.bounds, (index, value) => store.updateRoadIntersectionBoundsObject(intersection, index, value))),
      readonlyField("roads", (intersection.connected_roads || []).join(", ")),
    );
    card.append(header, fields);
    body.append(card);
  }
  return section("Roads", "Roads", [body], null);
}

function wallsEditorSection(scene, store) {
  const body = document.createElement("div");
  for (const wall of scene.walls || []) {
    const card = document.createElement("div");
    card.className = "object-card";
    card.dataset.spatialType = "wall";
    card.dataset.spatialId = wall.wall_id;
    const header = document.createElement("div");
    header.className = "object-header";
    const title = document.createElement("div");
    title.className = "object-title";
    title.textContent = `${wall.name} (${wall.wall_type})`;
    header.append(title);
    const fields = document.createElement("div");
    fields.className = "collapsible-fields";
    fields.append(
      readonlyField("id", wall.wall_id),
      field("locked", checkboxInput(wall.locked, (value) => store.updateWallObject(wall, "locked", value))),
      field("type", selectInput(wall.wall_type || "interior", ["interior", "exterior", "partition", "glass"], (value) => store.updateWallObject(wall, "wall_type", value))),
      field("start", pairInputs(wall.start, (index, value) => store.updateWallPointObject(wall, "start", index, value))),
      field("end", pairInputs(wall.end, (index, value) => store.updateWallPointObject(wall, "end", index, value))),
      field("material", textInput(wall.material, (value) => store.updateWallObject(wall, "material", value))),
      field("loss", numberInput(wall.penetration_loss_db, (value) => store.updateWallObject(wall, "penetration_loss_db", Number(value)))),
      readonlyField("areas", (wall.areas || []).filter(Boolean).join(" / ")),
      readonlyField("portals", (wall.portal_ids || []).join(", ")),
    );
    card.append(header, fields);
    body.append(card);
  }
  return section("Walls", "Walls", [body], null);
}

function portalsSection(scene) {
  const body = document.createElement("div");
  for (const portal of scene.portals || []) {
    const card = document.createElement("div");
    card.className = "object-card";
    const header = document.createElement("div");
    header.className = "object-header";
    const title = document.createElement("div");
    title.className = "object-title";
    title.textContent = `${portal.name} (${portal.kind})`;
    header.append(title);
    card.append(header);
    body.append(card);
  }
  return section("Portals", "Portals", [body], null);
}

function wallsSection(scene) {
  const body = document.createElement("div");
  for (const wall of scene.walls || []) {
    const card = document.createElement("div");
    card.className = "object-card";
    const header = document.createElement("div");
    header.className = "object-header";
    const title = document.createElement("div");
    title.className = "object-title";
    title.textContent = `${wall.name} (${wall.wall_type})`;
    header.append(title);
    const fields = document.createElement("div");
    fields.className = "collapsible-fields";
    fields.append(
      readonlyField("id", wall.wall_id),
      readonlyField("material", wall.material),
      readonlyField("loss", `${wall.penetration_loss_db} dB`),
      readonlyField("areas", (wall.areas || []).filter(Boolean).join(" / ")),
      readonlyField("portals", (wall.portal_ids || []).join(", ")),
    );
    card.append(header, fields);
    body.append(card);
  }
  return section("Walls", "Walls", [body], null);
}

function section(title, label, children, action = null) {
  const details = document.createElement("details");
  details.className = "section";
  details.open = true;

  const summary = document.createElement("summary");
  summary.className = "section-summary";
  const titleNode = document.createElement("span");
  titleNode.className = "section-title";
  titleNode.textContent = `${label} / ${title}`;
  summary.append(titleNode);
  if (action) summary.append(action);
  bindSummaryToggle(details, summary);

  const body = document.createElement("div");
  body.className = "section-body";
  for (const child of children) body.appendChild(child);
  details.append(summary, body);
  return details;
}

function bindSummaryToggle(details, summary) {
  summary.addEventListener("click", (event) => {
    event.preventDefault();
    if (event.target.closest("button")) return;
    details.open = !details.open;
  });
}

function field(labelText, input) {
  const row = document.createElement("div");
  row.className = "field-grid";
  const label = document.createElement("label");
  label.textContent = labelText;
  row.append(label, input);
  return row;
}

function readonlyField(labelText, value) {
  const text = document.createElement("div");
  text.className = "readonly-value";
  text.textContent = value || "-";
  return field(labelText, text);
}

function endpointLabel(endpoint) {
  if (!endpoint) return "-";
  return `${endpoint.object_type}:${endpoint.object_id}`;
}

function isRoadArea(area) {
  return area.metadata?.area_type === "road" || area.metadata?.area_type === "road_intersection";
}

function textInput(value, onChange) {
  const input = document.createElement("input");
  input.value = value ?? "";
  input.addEventListener("input", () => onChange(input.value));
  return input;
}

function numberInput(value, onChange) {
  const input = document.createElement("input");
  input.type = "number";
  input.step = "1";
  input.value = value ?? 0;
  input.addEventListener("input", () => onChange(input.value));
  return input;
}

function textareaInput(value, onChange) {
  const input = document.createElement("textarea");
  input.value = value ?? "";
  input.addEventListener("input", () => onChange(input.value));
  return input;
}

function checkboxInput(value, onChange) {
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = Boolean(value);
  input.addEventListener("change", () => onChange(input.checked));
  return input;
}

function selectInput(value, options, onChange) {
  const input = document.createElement("select");
  for (const optionValue of options) {
    const option = document.createElement("option");
    option.value = optionValue;
    option.textContent = optionValue;
    input.append(option);
  }
  input.value = value;
  input.addEventListener("change", () => onChange(input.value));
  return input;
}

function pairInputs(values, onChange) {
  const wrap = document.createElement("div");
  wrap.className = "inline-pair";
  values.forEach((value, index) => {
    const input = document.createElement("input");
    input.type = "number";
    input.step = "1";
    input.value = value;
    input.addEventListener("input", () => onChange(index, input.value));
    wrap.append(input);
  });
  return wrap;
}

function boundsInputs(values, onChange) {
  const wrap = document.createElement("div");
  wrap.className = "inline-pair";
  values.forEach((value, index) => {
    const input = document.createElement("input");
    input.type = "number";
    input.step = "1";
    input.value = value;
    input.title = ["x_min", "y_min", "x_max", "y_max"][index];
    input.addEventListener("input", () => onChange(index, input.value));
    wrap.append(input);
  });
  return wrap;
}

function iconButton(text, title, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "icon";
  button.textContent = text;
  button.title = title;
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    event.preventDefault();
    onClick();
  });
  return button;
}
