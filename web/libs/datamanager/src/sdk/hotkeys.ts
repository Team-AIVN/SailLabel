import { useHotkeys } from "react-hotkeys-hook";
import { pascalCase } from "@humansignal/core";
import { keymap } from "./keymap";

// Only these DM shortcuts share keys with editor hotkeys (shift+left/right), so only
// they yield while the labeling panel is focused. shift+up/down (task navigation) never
// collide and must keep working inside the editor.
const YIELDS_TO_EDITOR = new Set<keyof typeof keymap>(["dm.close-labeling", "dm.open-labeling"]);

export type Hotkey = {
  title: string;
  shortcut?: string;
  macos?: string;
  other?: string;
};

const readableShortcut = (shortcut: string | null | undefined) => {
  if (!shortcut || typeof shortcut !== "string") {
    return "";
  }

  return shortcut
    .split("+")
    .map((str) => pascalCase(str))
    .join(" + ");
};

export const useShortcut = (
  actionName: keyof typeof keymap,
  callback: () => void,
  options = { showShortcut: true },
  dependencies = undefined,
) => {
  const action = keymap[actionName] as Hotkey;
  const isMacos = /mac/i.test(navigator.platform);

  let shortcut = action.shortcut ?? ((isMacos ? action.macos : action.other) as string);

  // Check for custom shortcut in app settings
  const customMapping = window.APP_SETTINGS?.lookupHotkey?.(`data_manager:${actionName}`);
  if (customMapping) {
    // Explicitly use the custom key even if it's null
    shortcut = customMapping.key;
  }

  useHotkeys(
    shortcut,
    () => {
      // Yield to editor (LSF) hotkeys when the labeling panel is active — but only for
      // shortcuts that actually collide. Editor shift+arrow hotkeys are shift+left/right
      // (TimeSeries pan, region grow), so only close/open-labeling (also shift+left/right)
      // must yield. Task navigation is shift+up/down, which no editor hotkey uses, so it
      // keeps working while the labeling panel is focused (no need to click outside first).
      // The flag is set by Label.jsx when labeling starts and toggled via pointerdown.
      if (YIELDS_TO_EDITOR.has(actionName) && document.body.dataset.lsfLabeling === "true") return;

      callback();
    },
    {
      keyup: false,
      element: document.body,
    } as any,
    dependencies,
  );

  const title = action.title + (options.showShortcut ? `: [ ${readableShortcut(shortcut)} ]` : "");

  return title;
};
