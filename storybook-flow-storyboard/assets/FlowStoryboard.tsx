import { Fragment, type CSSProperties, type ReactNode } from "react";

import "./FlowStoryboard.css";

/** 這一步是誰在看的畫面。決定左上角的小標籤與框線樣式。 */
export type FlowStoryboardActor = "me" | "other" | "system" | "external";

const ACTOR_LABEL: Record<FlowStoryboardActor, string> = {
  me: "我",
  other: "對方",
  system: "系統畫面",
  external: "小程序端",
};

export type FlowStoryboardStep = {
  /** 穩定的識別字;便利貼會記下「貼在哪一步」。 */
  id: string;
  /** 畫面名稱,例如「好友頁：邀請」。 */
  title: string;
  /** 從上一步到這一步做了什麼,例如「點「接受」」。第一步可以省略。 */
  action?: string;
  /** 預設「我」。「對方」是另一個使用者的手機;「系統畫面」是作業系統或第三方 App;「小程序端」本次不含頁面設計。 */
  actor?: FlowStoryboardActor;
  /** 這一步的規則,一句話。 */
  note?: string;
  /** 真的畫面元件,停在這一步的狀態。看板會把它鎖成不可操作。 */
  screen: ReactNode;
};

export type FlowStoryboardRow = {
  /** 這一列在講哪一段,例如「A 送出邀請」。 */
  label?: string;
  steps: FlowStoryboardStep[];
};

export type FlowStoryboardProps = {
  /** 流程代號,固定不改(便利貼以它存檔:`flow-<id>.json`)。 */
  id: string;
  title: string;
  summary?: string;
  rows: FlowStoryboardRow[];
  /** 每一格手機畫面的縮放,預設 0.56(375 → 210px 寬)。 */
  scale?: number;
  className?: string;
};

/** 一條流程的內容(不含代號);代號由 friendsStoryboardIndex 統一給。 */
export type FlowStoryboardBoard = Omit<FlowStoryboardProps, "id">;

/**
 * 【交付導覽】流程走查看板:一條流程照人實際操作的順序,一步一格橫著排,
 * 每格是**真的畫面元件**停在那一步的狀態,格與格之間寫「做了什麼」。
 *
 * 為什麼不用流程圖:2026-09-30 使用者回饋,節點加箭頭的圖看不出一步一步的操作,
 * PM 也沒辦法在圖上貼埋點便利貼。這裡每一格都是 DOM 裡的真畫面,便利貼可以直接貼在
 * 某一步的某個位置,便利貼會記下「第幾步・哪個畫面」。
 *
 * 每格都鎖成不可操作(`pointer-events: none`):這裡是看流程,不是操作原型;要操作去各自的互動 story。
 * 便利貼進入「新增」模式時會暫時打開點擊,讓便利貼記得到「點了哪顆按鈕」,但點擊本身會被便利貼攔掉。
 * 便利貼跟流程存(`data-flow-board`),不跟你從哪一則 story 進來存。
 * 實線框＝App 畫面;虛線框＝系統畫面或小程序端(本次不含頁面設計)。
 */
export function FlowStoryboard({ id, title, summary, rows, scale = 0.56, className }: FlowStoryboardProps) {
  let counter = 0;
  return (
    <div className={["ds-flow-storyboard", className].filter(Boolean).join(" ")} data-flow-board={id} style={{ "--flow-scale": scale } as CSSProperties}>
      <header className="ds-flow-storyboard__header">
        <h1 className="ds-flow-storyboard__title">{title}</h1>
        {summary ? <p className="ds-flow-storyboard__summary">{summary}</p> : null}
        <p className="ds-flow-storyboard__legend">
          <span className="ds-flow-storyboard__legend-item ds-flow-storyboard__legend-item--solid">App 畫面</span>
          <span className="ds-flow-storyboard__legend-item ds-flow-storyboard__legend-item--dashed">系統畫面／小程序端（本次不含頁面設計）</span>
          <span className="ds-flow-storyboard__legend-item">畫面不能操作；要貼便利貼：右上角「便利貼」→「＋ 新增便利貼」→ 點某一步的畫面</span>
        </p>
      </header>

      {rows.map((row, rowIndex) => (
        <section key={row.label ?? rowIndex} className="ds-flow-storyboard__row">
          {row.label ? <h2 className="ds-flow-storyboard__row-label">{row.label}</h2> : null}
          <ol className="ds-flow-storyboard__steps">
            {row.steps.map((step, index) => {
              counter += 1;
              const number = counter;
              const actor = step.actor ?? "me";
              const dashed = actor === "system" || actor === "external";
              return (
                <Fragment key={step.id}>
                  {index > 0 || step.action ? (
                    <li className="ds-flow-storyboard__connector" aria-hidden="true">
                      {step.action ? <span className="ds-flow-storyboard__action">{step.action}</span> : null}
                      <span className="ds-flow-storyboard__arrow" />
                    </li>
                  ) : null}
                  <li
                    className={["ds-flow-storyboard__step", `ds-flow-storyboard__step--${actor}`].join(" ")}
                    data-flow-step={step.id}
                    data-flow-step-title={`第 ${number} 步・${step.title}`}
                  >
                    <div className="ds-flow-storyboard__step-head">
                      <span className="ds-flow-storyboard__number">{number}</span>
                      <span className={["ds-flow-storyboard__actor", `ds-flow-storyboard__actor--${actor}`].join(" ")}>{ACTOR_LABEL[actor]}</span>
                    </div>
                    <p className="ds-flow-storyboard__step-title">{step.title}</p>
                    <div className={["ds-flow-storyboard__frame", dashed ? "ds-flow-storyboard__frame--dashed" : ""].filter(Boolean).join(" ")}>
                      {/* 鎖成不可操作(CSS pointer-events):這裡是看流程,不是操作原型。 */}
                      <div className="ds-flow-storyboard__screen">
                        {step.screen}
                      </div>
                    </div>
                    {step.note ? <p className="ds-flow-storyboard__step-note">{step.note}</p> : null}
                  </li>
                </Fragment>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}
