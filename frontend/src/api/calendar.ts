import type { Config, EventInput, SaveResult, Table } from "../types/calendar";
import { apiRequest } from "./client";

export function getCalendarConfig() {
  return apiRequest<Config>("/api/config");
}

export function getDocumentStructure() {
  return apiRequest<Table>("/api/calendar");
}

export function createEvent(input: EventInput, token: string) {
  return apiRequest<SaveResult>("/api/events", {
    method: "POST",
    headers: token ? { Authorization: "Bearer " + token } : undefined,
    body: JSON.stringify(input),
  });
}

export function resetDemo() {
  return apiRequest<{ ok: boolean }>("/api/demo/reset", { method: "POST" });
}

export function updateEvent(id: number, expected: string[], input: EventInput, token: string) {
  return apiRequest<SaveResult>(`/api/events/${id}/edit`, {
    method: "POST",
    headers: token ? { Authorization: "Bearer " + token } : undefined,
    body: JSON.stringify({ ...input, expected }),
  });
}

export function deleteEvent(id: number, expected: string[], token: string) {
  return apiRequest<Table>(`/api/events/${id}/delete`, {
    method: "POST",
    headers: token ? { Authorization: "Bearer " + token } : undefined,
    body: JSON.stringify({ expected }),
  });
}


export function getDocumentPreview() {
  return apiRequest<Table>("/api/document/structure");
}

export function importDocument(token: string) {
  return apiRequest<Table>("/api/sheets/import-document", {
    method: "POST",
    headers: token ? { Authorization: "Bearer " + token } : undefined,
  });
}

export function synchronizeDocument(token: string) {
  return apiRequest<Table>("/api/document/sync", {
    method: "POST",
    headers: token ? { Authorization: "Bearer " + token } : undefined,
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
