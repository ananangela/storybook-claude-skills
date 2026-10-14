export const prototypeFlowLayoutStoragePrefix =
  "prototype-inspector:flow-layout";
export const prototypeFlowLayoutSchemaName =
  "storybook-template.prototype-flow-layout";
export const prototypeFlowLayoutSchemaVersion = 2;
// Version-1 and unsigned payloads predate viewport signatures; they were
// always authored against the phone frame.
export const prototypeFlowLayoutPhoneViewportSignature = "phone:375x812";

export type PrototypeFlowLayoutPosition = {
  x: number;
  y: number;
};

export type PrototypeFlowLayoutViewport = {
  formFactor: string;
  width: number;
  height: number;
};

export function getPrototypeFlowLayoutViewportSignature(
  viewport: PrototypeFlowLayoutViewport | null | undefined,
): string | null {
  if (!viewport) {
    return null;
  }

  return `${viewport.formFactor}:${viewport.width}x${viewport.height}`;
}

export type PrototypeFlowLayoutPositions<NodeId extends string = string> =
  Partial<Record<NodeId, PrototypeFlowLayoutPosition>>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getNormalizedPrototypeId(prototypeId: string | null | undefined) {
  return typeof prototypeId === "string" && prototypeId.trim()
    ? prototypeId.trim()
    : "prototype";
}

export function getPrototypeFlowLayoutStorageKey(
  prototypeId: string | null | undefined,
) {
  return `${prototypeFlowLayoutStoragePrefix}:${getNormalizedPrototypeId(
    prototypeId,
  )}`;
}

export function normalizePrototypeFlowLayoutPositions<NodeId extends string>(
  value: unknown,
  nodeIds: ReadonlySet<NodeId>,
): PrototypeFlowLayoutPositions<NodeId> {
  if (!isRecord(value)) {
    return {};
  }

  const positionsSource = isRecord(value.positions)
    ? value.positions
    : isRecord(value.routePositions)
      ? value.routePositions
      : value;
  const positions: PrototypeFlowLayoutPositions<NodeId> = {};

  Object.entries(positionsSource).forEach(([nodeId, position]) => {
    const typedNodeId = nodeId as NodeId;

    if (
      nodeIds.has(typedNodeId) &&
      isRecord(position) &&
      typeof position.x === "number" &&
      typeof position.y === "number" &&
      Number.isFinite(position.x) &&
      Number.isFinite(position.y)
    ) {
      positions[typedNodeId] = {
        x: Math.round(position.x),
        y: Math.round(position.y),
      };
    }
  });

  return positions;
}

export function createPrototypeFlowLayoutPayload<NodeId extends string>(
  prototypeId: string | null | undefined,
  positions: PrototypeFlowLayoutPositions<NodeId>,
  viewportSignature?: string | null,
) {
  return {
    exportedAt: new Date().toISOString(),
    positions,
    prototypeId: prototypeId ?? null,
    schema: prototypeFlowLayoutSchemaName,
    version: prototypeFlowLayoutSchemaVersion,
    viewport: viewportSignature ?? null,
  };
}

function matchesExpectedViewport(
  payload: unknown,
  expectedViewport: string | null | undefined,
  storageKey: string,
) {
  // No expectation: legacy callers keep their pre-signature behavior.
  if (expectedViewport == null) {
    return true;
  }

  const payloadSignature =
    isRecord(payload) && typeof payload.viewport === "string"
      ? payload.viewport
      : null;
  // Unsigned (v1) payloads were authored against the phone frame.
  const effectiveSignature =
    payloadSignature ?? prototypeFlowLayoutPhoneViewportSignature;

  if (effectiveSignature === expectedViewport) {
    return true;
  }

  console.info(
    `Prototype flow layout ${storageKey} was saved for viewport ` +
      `${effectiveSignature} but the flow now declares ${expectedViewport}; ` +
      "ignoring saved positions until the flow is re-arranged.",
  );
  return false;
}

export function readPrototypeFlowLayoutPositions<NodeId extends string>(
  storageKey: string,
  nodeIds: ReadonlySet<NodeId>,
  expectedViewport?: string | null,
): PrototypeFlowLayoutPositions<NodeId> {
  if (typeof window === "undefined") {
    return {};
  }

  try {
    const storedValue = window.localStorage.getItem(storageKey);
    if (!storedValue) {
      return {};
    }

    const payload: unknown = JSON.parse(storedValue);
    if (!matchesExpectedViewport(payload, expectedViewport, storageKey)) {
      return {};
    }

    return normalizePrototypeFlowLayoutPositions(payload, nodeIds);
  } catch (error) {
    console.warn("Unable to read prototype flow layout.", error);
    return {};
  }
}

export function writePrototypeFlowLayoutPositions<NodeId extends string>(
  storageKey: string,
  prototypeId: string | null | undefined,
  positions: PrototypeFlowLayoutPositions<NodeId>,
  nodeIds: ReadonlySet<NodeId>,
  viewportSignature?: string | null,
) {
  if (typeof window === "undefined") {
    return;
  }

  const normalizedPositions = normalizePrototypeFlowLayoutPositions(
    { positions },
    nodeIds,
  );

  try {
    if (Object.keys(normalizedPositions).length === 0) {
      window.localStorage.removeItem(storageKey);
      return;
    }

    window.localStorage.setItem(
      storageKey,
      JSON.stringify(
        createPrototypeFlowLayoutPayload(
          prototypeId,
          normalizedPositions,
          viewportSignature,
        ),
      ),
    );
  } catch (error) {
    console.warn("Unable to store prototype flow layout.", error);
  }
}
