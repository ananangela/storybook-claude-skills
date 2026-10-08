/* 流程走查總表（範本）：複製到 <需求> 的 handoff 資料夾，改名、改前綴。
   id 是契約（便利貼檔名 flow-<id>.json），名稱與步驟可以改，id 不要改。 */
import { FlowStoryboard, type FlowStoryboardBoard, type FlowStoryboardProps } from "./FlowStoryboard";
import * as boards from "./exampleStoryboards";

export type StoryboardEntry = { id: string; title: string; related: string[]; build: () => FlowStoryboardBoard };

const G = "設計中/YYYY-MM_需求名/"; // 側邊欄群組前綴（狀態變了只改這裡）
const P = "Pages/";

export const storyboardIndex: StoryboardEntry[] = [
  { id: "example-flow", title: "範例：從首頁進入到完成", related: [`${P}首頁`, `${G}互動流程`], build: boards.exampleFlow },
].map((entry) => ({ ...entry, related: [`${G}流程走查/${entry.title}`, ...entry.related] }));

export const buildStoryboard = (entry: StoryboardEntry): FlowStoryboardProps => ({ id: entry.id, ...entry.build() });

export const prototypeStoryboards = storyboardIndex.map((entry) => ({
  id: entry.id,
  title: entry.title,
  related: entry.related,
  render: () => <FlowStoryboard {...buildStoryboard(entry)} />,
}));
