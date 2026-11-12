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

export function updateEvent(id: number, expected: string[], input: EventInput) {
  return apiRequest<SaveResult>(`/api/events/${id}/edit`, {
    method: "POST",
    body: JSON.stringify({ ...input, expected }),
  });
}

export function deleteEvent(id: number, expected: string[]) {
  return apiRequest<Table>(`/api/events/${id}/delete`, {
    method: "POST",
    body: JSON.stringify({ expected }),
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
