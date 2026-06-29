export function getSceneBounds(scene) {
  if (Array.isArray(scene.rendering?.map_bounds) && scene.rendering.map_bounds.length === 4) {
    return scene.rendering.map_bounds.map(Number);
  }
  const bounds = scene.areas.map((area) => area.bounds);
  for (const road of scene.roads?.segments || []) {
    bounds.push(roadBounds(road));
  }
  for (const intersection of scene.roads?.intersections || []) {
    bounds.push(intersection.bounds);
  }
  for (const wall of scene.walls || []) {
    bounds.push([
      Math.min(wall.start[0], wall.end[0]),
      Math.min(wall.start[1], wall.end[1]),
      Math.max(wall.start[0], wall.end[0]),
      Math.max(wall.start[1], wall.end[1]),
    ]);
  }
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

export function hitTestSpatialObject(scene, worldPoint) {
  for (let index = (scene.portals || []).length - 1; index >= 0; index -= 1) {
    const portal = scene.portals[index];
    if (portal.segment && pointNearSegment(worldPoint, portal.segment[0], portal.segment[1], 6)) {
      return { type: "portal", object: portal, objectId: portal.id };
    }
  }
  for (let index = (scene.walls || []).length - 1; index >= 0; index -= 1) {
    const wall = scene.walls[index];
    if (wall.start && wall.end && pointNearSegment(worldPoint, wall.start, wall.end, 6)) {
      return { type: "wall", object: wall, objectId: wall.wall_id };
    }
  }
  for (let index = (scene.roads?.intersections || []).length - 1; index >= 0; index -= 1) {
    const intersection = scene.roads.intersections[index];
    if (pointInBounds(worldPoint, intersection.bounds)) {
      return { type: "road_intersection", object: intersection, objectId: intersection.intersection_id };
    }
  }
  for (let index = (scene.roads?.segments || []).length - 1; index >= 0; index -= 1) {
    const road = scene.roads.segments[index];
    if (pointInRoadSegment(worldPoint, road)) {
      return { type: "road_segment", object: road, objectId: road.road_id };
    }
  }
  const areaHit = hitTestArea(scene, worldPoint);
  if (areaHit?.area) {
    return { type: "area", object: areaHit.area, objectId: areaHit.area.node_id };
  }
  return null;
}

export function spatialObjectBounds(hit) {
  if (!hit) return null;
  if (hit.type === "area") return hit.object.bounds;
  if (hit.type === "road_intersection") return hit.object.bounds;
  if (hit.type === "road_segment") return roadBounds(hit.object);
  if (hit.type === "wall") {
    return [
      Math.min(hit.object.start[0], hit.object.end[0]),
      Math.min(hit.object.start[1], hit.object.end[1]),
      Math.max(hit.object.start[0], hit.object.end[0]),
      Math.max(hit.object.start[1], hit.object.end[1]),
    ];
  }
  if (hit.type === "portal") {
    return [
      Math.min(hit.object.segment[0][0], hit.object.segment[1][0]),
      Math.min(hit.object.segment[0][1], hit.object.segment[1][1]),
      Math.max(hit.object.segment[0][0], hit.object.segment[1][0]),
      Math.max(hit.object.segment[0][1], hit.object.segment[1][1]),
    ];
  }
  return null;
}

export function pointInRoadSegment(point, road) {
  const [x, y] = point;
  const topY = road.top.y;
  const bottomY = road.bottom.y;
  const minY = Math.min(topY, bottomY);
  const maxY = Math.max(topY, bottomY);
  if (y < minY || y > maxY || topY === bottomY) return false;
  const t = (y - topY) / (bottomY - topY);
  const leftX = road.top.x1 + t * (road.bottom.x1 - road.top.x1);
  const rightX = road.top.x2 + t * (road.bottom.x2 - road.top.x2);
  return x >= Math.min(leftX, rightX) && x <= Math.max(leftX, rightX);
}

export function roadPolygon(road) {
  return [
    [road.top.x1, road.top.y],
    [road.top.x2, road.top.y],
    [road.bottom.x2, road.bottom.y],
    [road.bottom.x1, road.bottom.y],
  ];
}

export function roadBounds(road) {
  const points = roadPolygon(road);
  return [
    Math.min(...points.map((point) => point[0])),
    Math.min(...points.map((point) => point[1])),
    Math.max(...points.map((point) => point[0])),
    Math.max(...points.map((point) => point[1])),
  ];
}

function pointInBounds(point, bounds) {
  const [x, y] = point;
  const [minX, minY, maxX, maxY] = bounds;
  return x >= minX && x <= maxX && y >= minY && y <= maxY;
}

function pointNearSegment(point, start, end, tolerance) {
  const [px, py] = point;
  const [x1, y1] = start;
  const [x2, y2] = end;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const lengthSq = dx * dx + dy * dy;
  if (lengthSq === 0) return Math.hypot(px - x1, py - y1) <= tolerance;
  const t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / lengthSq));
  const x = x1 + t * dx;
  const y = y1 + t * dy;
  return Math.hypot(px - x, py - y) <= tolerance;
}

export function pointInElement(point, element) {
  const [x, y] = point;
  const [cx, cy] = element.center;
  const [width, height] = element.size;
  return x >= cx - width / 2 && x <= cx + width / 2 && y >= cy - height / 2 && y <= cy + height / 2;
}
