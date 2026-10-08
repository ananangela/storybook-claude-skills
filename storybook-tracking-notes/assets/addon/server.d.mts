export declare const defaultTrackingNotesApiPath: string;
export declare const defaultTrackingNotesDir: string;
export declare const TRACKING_NOTE_KINDS: readonly string[];
export declare const TRACKING_NOTE_KIND_LABELS: Record<string, string>;
export declare function storyFileStem(storyId: string): string;
export declare function regenerateTrackingNotesIndex(dir: string): Promise<void>;
export declare function createTrackingNotesStore(options?: {
  cwd?: string;
  dir?: string;
}): {
  root: string;
  list(storyId: string): Promise<unknown>;
  create(payload: unknown): Promise<unknown>;
  update(storyId: string, noteId: string, patch: unknown): Promise<unknown>;
  remove(storyId: string, noteId: string): Promise<unknown>;
};
export declare function createTrackingNotesPlugin(options?: {
  apiPath?: string;
  cwd?: string;
  dir?: string;
  name?: string;
}): {
  name: string;
  configureServer(server: {
    middlewares: { use(path: string, handler: (request: unknown, response: unknown) => void): void };
  }): void;
};
