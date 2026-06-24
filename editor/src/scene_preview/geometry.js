export function getSceneBounds(scene) {
  const bounds = scene.areas.map((area) => area.bounds);
  const minX = Math.min(...bounds.map((item) => item[0]));
  const minY = Math.min(...bounds.map((item) => item[1]));
  const maxX = Math.max(...bounds.map((item) => item[2]));
  const maxY = Math.max(...bounds.map((item) => item[3]));
  return [minX, minY, maxX, maxY];
}

export function createTransform(sceneBounds, viewportWidth, viewportHeight, padding = 42, view = {}) {
  const [minX, minY, maxX, maxY] = sceneBounds;
  const worldWidth = maxX - minX;
  const worldHeight = maxY - minY;
  const baseScale = Math.min(
    (viewportWidth - padding * 2) / worldWidth,
    (viewportHeight - padding * 2) / worldHeight,
  );
  const scale = baseScale * (view.scaleMultiplier || 1);
  const offsetX = (viewportWidth - worldWidth * scale) / 2 - minX * scale + (view.panX || 0);
  const offsetY = (viewportHeight - worldHeight * scale) / 2 - minY * scale + (view.panY || 0);

  return {
    scale,
    toScreen(point) {
      return [point[0] * scale + offsetX, point[1] * scale + offsetY];
    },
    toWorld(point) {
      return [(point[0] - offsetX) / scale, (point[1] - offsetY) / scale];
    },
    rectToScreen(bounds) {
      const [x1, y1] = this.toScreen([bounds[0], bounds[1]]);
      const [x2, y2] = this.toScreen([bounds[2], bounds[3]]);
      return [x1, y1, x2 - x1, y2 - y1];
    },
    elementToScreen(element) {
      const [cx, cy] = this.toScreen(element.center);
      return [
        cx - (element.size[0] * scale) / 2,
        cy - (element.size[1] * scale) / 2,
        element.size[0] * scale,
        element.size[1] * scale,
      ];
    },
  };
}

export function hitTestElement(scene, worldPoint) {
  for (let areaIndex = scene.areas.length - 1; areaIndex >= 0; areaIndex -= 1) {
    const area = scene.areas[areaIndex];
    for (let elementIndex = area.elements.length - 1; elementIndex >= 0; elementIndex -= 1) {
      const element = area.elements[elementIndex];
      if (pointInElement(worldPoint, element)) {
        return { type: "element", area, element };
      }
    }
  }
  return null;
}

export function hitTestArea(scene, worldPoint) {
  for (let areaIndex = scene.areas.length - 1; areaIndex >= 0; areaIndex -= 1) {
    const area = scene.areas[areaIndex];
    const [minX, minY, maxX, maxY] = area.bounds;
    if (worldPoint[0] >= minX && worldPoint[0] <= maxX && worldPoint[1] >= minY && worldPoint[1] <= maxY) {
      return { type: "area", area };
    }
  }
  return null;
}

export function pointInElement(point, element) {
  const [x, y] = point;
  const [cx, cy] = element.center;
  const [width, height] = element.size;
  return x >= cx - width / 2 && x <= cx + width / 2 && y >= cy - height / 2 && y <= cy + height / 2;
}
