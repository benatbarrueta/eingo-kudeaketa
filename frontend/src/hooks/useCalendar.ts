import { useCallback, useEffect, useState } from "react";
import { getCalendarConfig, getDocumentStructure, getSyncStatus, type SyncStatus } from "../api/calendar";
import type { Config, Table } from "../types/calendar";
import { t } from "../lib/labels";

export function useCalendar() {
  const [syncStatus, setSyncStatus] = useState<SyncStatus>();
  const [config, setConfig] = useState<Config>();
  const [table, setTable] = useState<Table>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const cfg = await getCalendarConfig();
      setConfig(cfg);
      setTable(await getDocumentStructure());
    } catch (cause) {
      setTable(undefined);
      setError(cause instanceof Error ? cause.message : t.failed);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    if (config?.source !== "sheets") return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const [calendar, status] = await Promise.all([getDocumentStructure(), getSyncStatus()]);
        if (active) {
          setTable((current) => JSON.stringify(current) === JSON.stringify(calendar) ? current : calendar);
          setSyncStatus(status);
        }
      } catch {
        if (active) setSyncStatus((current) => current ? { ...current, error: "sync_unavailable" } : {
          enabled: true, lastSuccess: null, error: "sync_unavailable", intervalSeconds: 15,
        });
      } finally {
        if (active) timer = setTimeout(() => void poll(), 15000);
      }
    }
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [config?.source]);
  return { syncStatus, config, table, setTable, error, loading, refresh };
}
