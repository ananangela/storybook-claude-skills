import { DocumentIcon, ChevronDownIcon } from "@storybook/icons";
import { createElement } from "react";
import {
  ToggleButton,
  TooltipLinkList,
  WithTooltip,
} from "storybook/internal/components";
import {
  addons,
  types,
  useGlobals,
  useParameter,
} from "storybook/manager-api";

const prototypeInspectorModes = [
  { id: "story", label: "Story" },
  { id: "docs", label: "Docs" },
  { id: "flow", label: "UI Flow" },
  { id: "components", label: "Components" },
  { id: "data", label: "Data" },
];

const defaultPrototypeModeGlobalName = "prototypeMode";
const defaultPrototypeParameterName = "prototype";
const prototypeInspectorAddonId = "storybook/prototype-inspector";

function getPrototypeMode(value) {
  return prototypeInspectorModes.some((mode) => mode.id === value)
    ? value
    : "story";
}

function PrototypeInspectorToolbar({ options }) {
  const prototype = useParameter(options.parameterName, null);
  const [globals, updateGlobals] = useGlobals();
  const selectedMode = getPrototypeMode(globals[options.globalName]);
  const selectedModeDefinition =
    prototypeInspectorModes.find((mode) => mode.id === selectedMode) ??
    prototypeInspectorModes[0];
  const title = `${options.toolTitle}: ${selectedModeDefinition.label}`;

  // Visibility follows the same contract as the preview decorator: a story
  // (or its docs page) opts in by declaring the prototype parameter. Sidebar
  // category naming carries no meaning here.
  if (!prototype) {
    return null;
  }

  return createElement(WithTooltip, {
    closeOnOutsideClick: true,
    hasChrome: true,
    placement: "bottom",
    tooltip: ({ onHide }) =>
      createElement(TooltipLinkList, {
        links: prototypeInspectorModes.map((mode) => ({
          active: selectedMode === mode.id,
          id: mode.id,
          onClick: (event) => {
            event.preventDefault();
            updateGlobals({ [options.globalName]: mode.id });
            onHide();
          },
          title: mode.label,
        })),
      }),
    trigger: "click",
    children: createElement(
      ToggleButton,
      {
        ariaLabel: title,
        key: `${options.addonId}/tool-button`,
        padding: "small",
        pressed: selectedMode !== "story",
        title,
        tooltip: title,
        variant: "ghost",
      },
      createElement(DocumentIcon),
      createElement("span", null, selectedModeDefinition.label),
      createElement(ChevronDownIcon),
    ),
  });
}

function registerPrototypeInspectorTool(options = {}) {
  const resolvedOptions = {
    addonId: options.addonId ?? prototypeInspectorAddonId,
    globalName: options.globalName ?? defaultPrototypeModeGlobalName,
    parameterName: options.parameterName ?? defaultPrototypeParameterName,
    toolTitle: options.toolTitle ?? "Prototype",
  };
  const toolId = `${resolvedOptions.addonId}/tool`;

  addons.register(resolvedOptions.addonId, () => {
    addons.add(toolId, {
      render: () =>
        createElement(PrototypeInspectorToolbar, {
          options: resolvedOptions,
        }),
      title: resolvedOptions.toolTitle,
      type: types.TOOL,
    });
  });
}

registerPrototypeInspectorTool();
