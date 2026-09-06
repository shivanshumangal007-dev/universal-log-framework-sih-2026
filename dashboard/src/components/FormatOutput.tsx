import { useState } from "react";
import { Copy, Check } from "lucide-react";
import {
  formatFields,
  OUTPUT_FORMATS,
  type OutputFormat,
} from "../lib/formatFields";

type Props = {
  fieldsJson: string;
  source?: string;
  label?: string;
};

export default function FormatOutput({ fieldsJson, source, label = "Fields Output" }: Props) {
  const [format, setFormat] = useState<OutputFormat>("json");
  const [copied, setCopied] = useState(false);

  let fields: Record<string, string> = {};
  try {
    const parsed = JSON.parse(fieldsJson || "{}");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      fields = Object.fromEntries(
        Object.entries(parsed).map(([k, v]) => [k, String(v ?? "")])
      );
    }
  } catch {
    fields = {};
  }

  const output = formatFields(fields, format, source);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(output);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for environments without clipboard API
    }
  };

  const renderOutput = () => {
    if (format === "csv") {
      const keys = Object.keys(fields);
      if (keys.length === 0) {
        return (
          <div className="bg-white border border-neutral-200 rounded p-4 text-center text-sm text-neutral-500">
            No fields available
          </div>
        );
      }
      return (
        <div className="overflow-x-auto border border-neutral-200 rounded-md bg-white">
          <table className="w-full text-xs text-left">
            <thead className="bg-neutral-50 border-b border-neutral-200">
              <tr>
                {keys.map((k) => (
                  <th key={k} className="px-3 py-2 font-semibold text-neutral-600 whitespace-nowrap">
                    {k}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              <tr>
                {keys.map((k) => (
                  <td key={k} className="px-3 py-2 text-neutral-700 whitespace-nowrap">
                    {fields[k]}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      );
    }

    return (
      <pre className="font-mono bg-white border border-neutral-200 rounded p-2 text-neutral-600 overflow-auto max-h-48 text-xs whitespace-pre-wrap break-all">
        {output}
      </pre>
    );
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <p className="font-semibold text-neutral-700">{label}</p>
        <div className="flex items-center gap-2">
          <select
            id="format-select"
            value={format}
            onChange={(e) => setFormat(e.target.value as OutputFormat)}
            className="rounded border border-neutral-200 bg-white px-2 py-0.5 text-xs font-medium text-neutral-700 outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 cursor-pointer transition-colors"
          >
            {OUTPUT_FORMATS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-1 rounded border border-neutral-200 bg-white px-2 py-0.5 text-xs text-neutral-600 hover:bg-neutral-50 transition-colors"
            title="Copy to clipboard"
          >
            {copied ? (
              <>
                <Check className="h-3 w-3 text-green-600" />
                <span className="text-green-600">Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3 w-3" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>
      {renderOutput()}
    </div>
  );
}
