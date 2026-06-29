export class ContextMenu {
  constructor(element, store) {
    this.element = element;
    this.store = store;
    document.addEventListener("click", () => this.hide());
    window.addEventListener("blur", () => this.hide());
  }

  show(request) {
    this.element.innerHTML = "";
    const [x, y] = request.local;
    this.element.style.left = `${x}px`;
    this.element.style.top = `${y}px`;

    if (request.target?.element) {
      this.addItem("Duplicate", () => this.store.duplicateElement(request.target.element.node_id));
      this.addItem("Delete", () => this.store.deleteElement(request.target.element.node_id));
    } else if (request.target?.type) {
      this.addItem("Delete", () => this.store.deleteSpatialObject(request.target.type, request.target.objectId));
    } else {
      this.addItem("Add element", () => this.store.addElementAt(request.world));
    }

    this.element.hidden = false;
  }

  hide() {
    this.element.hidden = true;
  }

  addItem(label, action) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      action();
      this.hide();
    });
    this.element.append(button);
  }
}
