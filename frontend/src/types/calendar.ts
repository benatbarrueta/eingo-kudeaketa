export type EventRow = { id: number; date: string; values: string[]; eventId?: string | null; version?: number | null };
export type Table = {
  title: string;
  columns: string[];
  rows: {
    kind: string;
    date: string | null;
    values: string[];
    spans?: number[];
    eventId?: string | null;
    version?: number | null;
  }[];
};
export type Config = {
  source: "mock" | "google" | "sheets" | "database";
  googleSync?: boolean;
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
