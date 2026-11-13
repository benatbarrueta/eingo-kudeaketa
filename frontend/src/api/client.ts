import { t } from "../lib/labels";

const apiOrigin = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const errorMessages: Record<string, keyof typeof t> = {
  sync_conflict: "syncConflict",
  conflict_changed: "conflictChanged",
  conflict_not_resolvable: "conflictStructural",
  sync_ambiguous_events: "syncConflict",
  sync_initial_mismatch: "sourcesDiffer",
  sync_state_mismatch: "syncConflict",
  sources_differ: "sourcesDiffer",
  sync_pending: "syncPending",
  database_sync_pending: "databaseSyncPending",
  database_busy: "databaseBusy",
  sheets_access_denied: "sheetsError",
  sheets_unavailable: "sheetsError",
  sheets_api_error: "sheetsError",
  month_without_block: "monthMissing",
  revision_conflict: "conflict",
  manual_review: "manual",
  unsafe_structure: "unsafe",
  rate_limited: "rate",
  validation_error: "invalid",
  date_changes_position: "dateChangesPosition",
  wrong_year: "invalid",
  invalid_fields: "invalid",
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(apiOrigin + path, {
      ...options,
      headers,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, t.disconnected);
  }

  const body = await response.json().catch(() => {
    throw new ApiError(response.status, t.failed);
  });
  if (!response.ok) {
    const code: unknown = body?.error?.code;
    const message =
      typeof code === "string" && Object.hasOwn(errorMessages, code)
        ? t[errorMessages[code]]
        : t.failed;
    throw new ApiError(response.status, message);
  }
  return body as T;
}
