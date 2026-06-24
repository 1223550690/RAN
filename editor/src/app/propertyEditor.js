export function renderPropertyEditor(container, store) {
  const state = store.snapshot();
  container.innerHTML = "";
  container.appendChild(sceneSection(state.scene, store));
  container.appendChild(areasSection(state, store));
  container.appendChild(portalsSection(state.scene));
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
}

export function scrollSelectionIntoView(container, state) {
  const selector = state.selectedId
    ? `[data-element-id="${CSS.escape(state.selectedId)}"]`
    : state.selectedAreaId
      ? `[data-area-id="${CSS.escape(state.selectedAreaId)}"]`
      : null;
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
  return section("Scene", "场景", [
    field("node_id", textInput(scene.node_id, (value) => store.updateSceneField("node_id", value))),
    field("name", textInput(scene.name, (value) => store.updateSceneField("name", value))),
    field(
      "start",
      pairInputs(scene.default_agent_start, (index, value) => {
        scene.default_agent_start[index] = Number(value);
        store.emit({ renderProperties: false });
      }),
    ),
  ]);
}

function areasSection(state, store) {
  const body = document.createElement("div");
  for (const area of state.scene.areas) {
    body.appendChild(areaCard(area, store, state));
  }
  return section("Areas", "区域", [body], null);
}

function areaCard(area, store, state) {
  const details = document.createElement("details");
  details.className = "object-card area-card";
  details.dataset.areaId = area.node_id;
  details.open = state.selectedAreaId === area.node_id || (state.selectedId ? area.elements.some((element) => element.node_id === state.selectedId) : false);
  details.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button") || event.target.closest("[data-element-id]")) return;
    store.setSelectedArea(area.node_id);
  });

  const header = document.createElement("summary");
  header.className = "object-header sticky-object-header";

  const title = document.createElement("div");
  title.className = "object-title";
  title.textContent = `${area.name} (${area.node_id})`;

  header.append(title);

  const fields = document.createElement("div");
  fields.className = "collapsible-fields";
  fields.append(
    field("area id", textInput(area.node_id, (value) => store.updateAreaObject(area, "node_id", value))),
    field("name", textInput(area.name, (value) => store.updateAreaObject(area, "name", value))),
    field("bounds", boundsInputs(area.bounds, (index, value) => store.updateAreaBoundsObject(area, index, value))),
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
  summary.append(label, iconButton("+", "添加元素", () => store.addElement(area.node_id)));

  const elements = document.createElement("div");
  elements.className = "section-body";
  for (const element of area.elements) {
    elements.appendChild(elementCard(element, store, state));
  }
  elementDetails.append(summary, elements);
  details.append(header, fields, elementDetails);
  return details;
}

function elementCard(element, store, state) {
  const card = document.createElement("details");
  card.className = "object-card";
  card.dataset.elementId = element.node_id;
  card.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button")) return;
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

  const duplicate = iconButton("⧉", "复制元素", () => store.duplicateElement(element.node_id));
  const remove = iconButton("×", "删除元素", () => store.deleteElement(element.node_id));
  remove.classList.add("danger");
  header.append(title, duplicate, remove);

  const fields = document.createElement("div");
  fields.className = "collapsible-fields";
  fields.append(
    field("node_id", textInput(element.node_id, (value) => store.updateElementObject(element, "node_id", value))),
    field("name", textInput(element.name, (value) => store.updateElementObject(element, "name", value))),
    field("center", pairInputs(element.center, (index, value) => store.updateElementVectorObject(element, "center", index, value))),
    field("size", pairInputs(element.size, (index, value) => store.updateElementVectorObject(element, "size", index, value))),
    field("movable", checkboxInput(element.movable, (value) => store.updateElementObject(element, "movable", value))),
    field("blocks", checkboxInput(element.blocks_movement, (value) => store.updateElementObject(element, "blocks_movement", value))),
    field("physical", textInput(element.physical_status, (value) => store.updateElementObject(element, "physical_status", value))),
    field("evolution", textInput(element.evolution_status, (value) => store.updateElementObject(element, "evolution_status", value))),
    field("interaction", textInput(element.interaction_status, (value) => store.updateElementObject(element, "interaction_status", value))),
    field("state", textareaInput(JSON.stringify(element.state_details || {}, null, 2), (value) => store.updateElementStateDetailsObject(element, value))),
  );

  card.append(header, fields);
  return card;
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
  return section("Portals", "通道", [body], null);
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

  const body = document.createElement("div");
  body.className = "section-body";
  for (const child of children) body.appendChild(child);
  details.append(summary, body);
  return details;
}

function field(labelText, input) {
  const row = document.createElement("div");
  row.className = "field-grid";
  const label = document.createElement("label");
  label.textContent = labelText;
  row.append(label, input);
  return row;
}

function textInput(value, onChange) {
  const input = document.createElement("input");
  input.value = value ?? "";
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
    input.step = "0.01";
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
    input.step = "0.01";
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
