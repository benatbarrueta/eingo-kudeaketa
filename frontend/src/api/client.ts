import { t } from "../lib/labels";

const apiOrigin = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const errorMessages: Record<string, string> = {
  sync_conflict: t.syncConflict,
  sync_ambiguous_events: t.syncConflict,
  sync_initial_mismatch: t.sourcesDiffer,
  sync_state_mismatch: t.syncConflict,
  sources_differ: t.sourcesDiffer,
  sync_pending: t.syncPending,
  sheets_access_denied: t.sheetsError,
  sheets_unavailable: t.sheetsError,
  sheets_api_error: t.sheetsError,
  month_without_block: t.monthMissing,
  revision_conflict: t.conflict,
  manual_review: t.manual,
  unsafe_structure: t.unsafe,
  rate_limited: t.rate,
  validation_error: t.invalid,
  date_changes_position: t.dateChangesPosition,
  wrong_year: t.invalid,
  invalid_fields: t.invalid,
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
        ? errorMessages[code]
        : t.failed;
    throw new ApiError(response.status, message);
  }
  return body as T;
}
