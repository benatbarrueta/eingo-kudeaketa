import { useCallback, useEffect, useRef, useState } from "react";
import { getCalendarConfig, getDocumentStructure, getSyncStatus, synchronizeDocument, type SyncStatus } from "../api/calendar";
import type { Config, Table } from "../types/calendar";
import { readVisit, saveVisit, visitChanges, visitKey, type VisitChange } from "../lib/visitChanges";
import { t } from "../lib/labels";

export function useCalendar() {
  const [changes, setChanges] = useState<VisitChange[]>([]);
  const [storageError, setStorageError] = useState(false);
  const refreshing = useRef(false);
  const initialized = useRef(false);
  const storageKey = useRef<string | undefined>(undefined);
  const [syncStatus, setSyncStatus] = useState<SyncStatus>();
  const [config, setConfig] = useState<Config>();
  const [table, setTable] = useState<Table>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    if (refreshing.current) return;
    refreshing.current = true;
    setLoading(true);
    setError("");
    try {
      const cfg = await getCalendarConfig();
      if (cfg.source === "sheets") await synchronizeDocument();
      const current = await getDocumentStructure();
      const key = visitKey(cfg);
      if (!initialized.current) {
        const previous = readVisit(key);
        setChanges(previous ? visitChanges(previous, current) : []);
        initialized.current = true;
      }
      storageKey.current = key;
      setStorageError(!saveVisit(key, current));
      setTable(current);
      setConfig(cfg);
    } catch (cause) {
      setTable(undefined);
      setError(cause instanceof Error ? cause.message : t.failed);
    } finally {
      refreshing.current = false;
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    function resume() {
      if (document.visibilityState === "visible") {
        initialized.current = false;
        void refresh();
      }
    }
    document.addEventListener("visibilitychange", resume);
    return () => document.removeEventListener("visibilitychange", resume);
  }, [refresh]);
  useEffect(() => {
    if (config?.source !== "sheets") return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      if (document.visibilityState === "hidden" || refreshing.current) {
        timer = setTimeout(() => void poll(), 15000);
        return;
      }
      try {
        const [calendar, status] = await Promise.all([getDocumentStructure(), getSyncStatus()]);
        if (active && document.visibilityState === "visible" && !refreshing.current) {
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
  useEffect(() => {
    if (table && storageKey.current && !syncStatus?.error && document.visibilityState === "visible") setStorageError(!saveVisit(storageKey.current, table));
  }, [table, syncStatus?.error]);
  return { changes, storageError, syncStatus, config, table, setTable, error, loading, refresh };
}
