import type { Meta, StoryObj } from "@storybook/react-vite";

import { FlowStoryboard } from "./FlowStoryboard";
import { prototypeMeta } from "./prototypeMeta";
import { buildStoryboard, storyboardIndex } from "./StoryboardIndex";

const meta = {
  title: "設計中/YYYY-MM_需求名/流程走查",
  component: FlowStoryboard,
  parameters: { prototype: prototypeMeta, layout: "fullscreen" },
} satisfies Meta<typeof FlowStoryboard>;

export default meta;
type Story = StoryObj<typeof meta>;

const board = (id: string) => {
  const entry = storyboardIndex.find((item) => item.id === id);
  if (!entry) throw new Error(`storyboardIndex 沒有 ${id}`);
  return buildStoryboard(entry);
};

export const ExampleFlow: Story = { name: "範例：從首頁進入到完成", args: board("example-flow") };
