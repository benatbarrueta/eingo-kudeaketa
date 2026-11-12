import { ExternalLink, RefreshCw } from "lucide-react";
import { t } from "../lib/labels";

interface FilePageHeaderProps {
  title: string;
  description: string;
  url?: string | null;
  openLabel: string;
  canSynchronize: boolean;
  busy: boolean;
  onSynchronize: () => void;
}

export function FilePageHeader({
  title, description, url, openLabel, canSynchronize, busy, onSynchronize,
}: FilePageHeaderProps) {
  return (
    <div className="panelHead filePageHeader">
      <div><h1>{title}</h1><p className="muted">{description}</p></div>
      <div className="pageActions">
        {canSynchronize && (
          <button className="secondary" disabled={busy} onClick={onSynchronize}>
            <RefreshCw size={17} aria-hidden="true" />{t.synchronizeFiles}
          </button>
        )}
        {url && (
          <a className="secondary" href={url} target="_blank" rel="noreferrer">
            {openLabel}<ExternalLink size={17} aria-hidden="true" />
          </a>
        )}
      </div>
    </div>
  );
}
