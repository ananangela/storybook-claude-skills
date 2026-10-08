import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const packageDir = dirname(fileURLToPath(import.meta.url));

/**
 * 埋點便利貼(Tracking Notes)addon。
 * manager.js:工具列上的顯示／隱藏切換。preview.js:畫面上的便利貼本體。
 * 伺服器端(寫檔)在 server.mjs,由 main.ts 的 viteFinal 掛進 Vite。
 */
export default {
  managerEntries: [join(packageDir, "manager.js")],
  name: "storybook-template/tracking-notes",
  previewAnnotations: [join(packageDir, "preview.js")],
};
