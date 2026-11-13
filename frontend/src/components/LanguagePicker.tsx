import { useEffect, useRef } from "react";
import { Check, ChevronDown } from "lucide-react";
import { useLabels } from "../lib/labels";

function Flag({ language }: { language: string }) {
  return (
    <svg className="languageFlag" viewBox="0 0 28 18" aria-hidden="true" focusable="false">
      {language === "eu" ? <>
        <path fill="#d52b1e" d="M0 0h28v18H0z" />
        <path stroke="#00843d" strokeWidth="4" d="m0 0 28 18M28 0 0 18" />
        <path stroke="#fff" strokeWidth="3" d="M14 0v18M0 9h28" />
      </> : <>
        <path fill="#aa151b" d="M0 0h28v18H0z" />
        <path fill="#f1bf00" d="M0 4.5h28v9H0z" />
      </>}
    </svg>
  );
}

export function LanguagePicker() {
  const { t, language, changeLanguage } = useLabels();
  const picker = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    function dismiss(event: PointerEvent) {
      if (picker.current && !picker.current.contains(event.target as Node)) picker.current.open = false;
    }
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, []);

  return (
    <details className="languagePicker" ref={picker}
      onBlur={event => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) event.currentTarget.open = false;
      }}
      onKeyDown={event => {
        if (event.key === "Escape" && picker.current?.open) {
          picker.current.open = false;
          picker.current.querySelector("summary")?.focus();
        }
      }}>
      <summary aria-label={`${t.language}: ${language === "eu" ? "Euskara" : "Castellano"}`}>
        <Flag language={language} />
        <span>{language.toUpperCase()}</span>
        <ChevronDown size={14} aria-hidden="true" />
      </summary>
      <div className="languageOptions" role="group" aria-label={t.language}>
        {(["eu", "es"] as const).map(code => (
          <button type="button" key={code} lang={code}
            aria-label={code === "eu" ? "Euskara" : "Castellano"}
            aria-pressed={language === code}
            onClick={() => {
              changeLanguage(code);
              if (picker.current) {
                picker.current.open = false;
                picker.current.querySelector("summary")?.focus();
              }
            }}>
            <Flag language={code} />
            <span>{code.toUpperCase()}</span>
            {language === code && <Check size={14} aria-hidden="true" />}
          </button>
        ))}
      </div>
    </details>
  );
}
