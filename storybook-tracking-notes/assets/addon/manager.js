import { CommentsIcon } from "@storybook/icons";
import { createElement } from "react";
import { ToggleButton } from "storybook/internal/components";
import { addons, types, useGlobals } from "storybook/manager-api";

const addonId = "storybook/tracking-notes";
const globalName = "trackingNotes";

/** 工具列上的一顆按鈕:整個 Storybook 的便利貼一起顯示或隱藏。 */
function TrackingNotesToolbar() {
  const [globals, updateGlobals] = useGlobals();
  const visible = globals[globalName] !== "hide";
  const title = visible ? "隱藏埋點便利貼" : "顯示埋點便利貼";
  return createElement(
    ToggleButton,
    {
      ariaLabel: title,
      key: `${addonId}/tool-button`,
      onClick: () => updateGlobals({ [globalName]: visible ? "hide" : "show" }),
      padding: "small",
      pressed: visible,
      title,
      tooltip: title,
      variant: "ghost",
    },
    createElement(CommentsIcon),
    createElement("span", null, "便利貼"),
  );
}

addons.register(addonId, () => {
  addons.add(`${addonId}/tool`, {
    render: () => createElement(TrackingNotesToolbar),
    title: "埋點便利貼",
    type: types.TOOL,
  });
});
