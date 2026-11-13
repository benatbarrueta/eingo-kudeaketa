import type { Config, EventInput, SaveResult, Table } from "../types/calendar";
import { apiRequest } from "./client";

export function getCalendarConfig() {
  return apiRequest<Config>("/api/config");
}

export function getDocumentStructure() {
  return apiRequest<Table>("/api/calendar");
}

export function createEvent(input: EventInput) {
  return apiRequest<SaveResult>("/api/events", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function resetDemo() {
  return apiRequest<{ ok: boolean }>("/api/demo/reset", { method: "POST" });
}

export function updateEvent(id: number | string, expected: string[], input: EventInput, expectedVersion?: number | null) {
  return apiRequest<SaveResult>(`/api/events/${id}/edit`, {
    method: "POST",
    body: JSON.stringify({ ...input, expected, expectedVersion }),
  });
}

export function deleteEvent(id: number | string, expected: string[], expectedVersion?: number | null) {
  return apiRequest<Table>(`/api/events/${id}/delete`, {
    method: "POST",
    body: JSON.stringify({ expected, expectedVersion }),
  });
}


export function getDocumentPreview() {
  return apiRequest<Table>("/api/document/structure");
}

export function importDocument() {
  return apiRequest<Table>("/api/sheets/import-document", {
    method: "POST",
  });
}

export function synchronizeDocument() {
  return apiRequest<Table>("/api/document/sync", {
    method: "POST",
  });
}

export interface SyncStatus {
  enabled: boolean;
  lastSuccess: string | null;
  error: string | null;
  intervalSeconds: number;
}

export function getSyncStatus() {
  return apiRequest<SyncStatus>("/api/sync/status");
}

export type ConflictSource = "sheets" | "docs" | "database";
export type ConflictPreview = {
  token: string;
  canResolve: boolean;
  reason: string | null;
  fields: {
    key: string;
    date: string;
    town: string;
    column: string;
    options: { source: ConflictSource; value: string }[];
  }[];
};

export function getSyncConflict() {
  return apiRequest<ConflictPreview>("/api/sync/conflict");
}

export function resolveSyncConflict(token: string, choices: Record<string, ConflictSource>) {
  return apiRequest<Table>("/api/sync/conflict/resolve", {
    method: "POST", body: JSON.stringify({ token, choices }),
  });
}
