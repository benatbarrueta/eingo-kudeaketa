export type EventRow = { id: number; date: string; values: string[] };
export type Table = {
  title: string;
  columns: string[];
  rows: {
    kind: string;
    date: string | null;
    values: string[];
    spans?: number[];
  }[];
};
export type Config = {
  source: "mock" | "google" | "sheets";
  year: number;
  documentUrl: string | null;
  spreadsheetUrl?: string | null;
};
export type EventInput = {
  date: string;
  town: string;
  fields: Record<string, string>;
};
export type SaveResult = { event: EventRow; table: Table; created: boolean };
