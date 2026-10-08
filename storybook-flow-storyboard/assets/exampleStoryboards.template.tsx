/* 一條流程的步驟（範本）。每格是既有元件停在那一步的狀態；不自創畫面、不自創過場。 */
import type { FlowStoryboardBoard } from "./FlowStoryboard";
import { SomeFlow } from "../some-feature/SomeFlow";

export const exampleFlow = (): FlowStoryboardBoard => ({
  title: "範例：從首頁進入到完成",
  summary: "一句話說這條流程在做什麼、終點是什麼。",
  rows: [
    {
      label: "A 進入",
      steps: [
        { id: "home", title: "首頁", screen: <SomeFlow initialScreen="home" /> },
        { id: "list", title: "列表頁", action: "點「進入」", note: "這一步的規則一句話。", screen: <SomeFlow initialScreen="list" /> },
        { id: "permission", title: "系統：權限詢問", action: "點「開始」", actor: "system", note: "作業系統的對話框，只決定文案。", screen: <SomeFlow initialScreen="list" storyboard={{ asking: true }} /> },
      ],
    },
    {
      label: "B 完成",
      steps: [
        { id: "done", title: "列表頁：完成", action: "按「允許」", screen: <SomeFlow initialScreen="list" storyboard={{ done: true }} /> },
      ],
    },
  ],
});
