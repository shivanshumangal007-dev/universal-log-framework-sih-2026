/**
 * Convert a fields object to various log format representations.
 */

export type OutputFormat = "json" | "csv" | "cef" | "syslog";

export const OUTPUT_FORMATS: { value: OutputFormat; label: string }[] = [
  { value: "json", label: "JSON" },
  { value: "csv", label: "CSV" },
  { value: "cef", label: "CEF" },
  { value: "syslog", label: "Syslog" },
];

/**
 * Convert a fields key-value map to the specified output format string.
 */
export function formatFields(
  fields: Record<string, string>,
  format: OutputFormat,
  source?: string,
): string {
  switch (format) {
    case "json":
      return JSON.stringify(fields, null, 2);

    case "csv": {
      const keys = Object.keys(fields);
      const header = keys.map(escapeCsv).join(",");
      const values = keys.map((k) => escapeCsv(fields[k])).join(",");
      return `${header}\n${values}`;
    }

    case "cef": {
      // CEF:Version|Device Vendor|Device Product|Device Version|Signature ID|Name|Severity|Extension
      const vendor = fields.vendor || fields.service || source || "Unknown";
      const product = fields.product || fields.field_2 || "LogFramework";
      const version = fields.version || fields.version_str || "1.0";
      const sigId = fields.signature_id || fields.id || fields.code || "0";
      const name = fields.message || fields.action || fields.name || "event";
      const severity = mapSeverity(fields.severity || fields.level || "");

      // Remaining fields go into the extension area as key=value pairs
      const skipKeys = new Set([
        "vendor", "product", "version", "version_str",
        "signature_id", "name", "severity",
        "service", "id", "code", "message", "action", "level",
      ]);
      const extensions = Object.entries(fields)
        .filter(([k]) => !skipKeys.has(k))
        .map(([k, v]) => `${k}=${v}`)
        .join(" ");

      return `CEF:0|${vendor}|${product}|${version}|${sigId}|${name}|${severity}|${extensions}`;
    }

    case "syslog": {
      // RFC 3164-ish: <priority>timestamp hostname message
      const level = (fields.level || fields.severity || "INFO").toUpperCase();
      const pri = syslogPriority(level);
      const hostname =
        fields.hostname || fields.host || fields.service || source || "localhost";
      const ts = fields.timestamp || fields.syslog_ts || new Date().toISOString();

      // Build the message from remaining fields
      const skipKeys = new Set([
        "level", "severity", "hostname", "host", "service",
        "timestamp", "syslog_ts", "priority", "facility",
      ]);
      const msgParts = Object.entries(fields)
        .filter(([k]) => !skipKeys.has(k))
        .map(([k, v]) => `${k}=${v}`);
      const msg = msgParts.length > 0
        ? msgParts.join(" ")
        : fields.message || "event";

      return `<${pri}>${ts} ${hostname} ${msg}`;
    }

    default:
      return JSON.stringify(fields, null, 2);
  }
}

function escapeCsv(value: string): string {
  if (value.includes(",") || value.includes('"') || value.includes("\n")) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function mapSeverity(level: string): string {
  const l = level.toUpperCase();
  const map: Record<string, string> = {
    CRITICAL: "10",
    FATAL: "10",
    ERROR: "8",
    WARN: "6",
    WARNING: "6",
    INFO: "3",
    DEBUG: "1",
    TRACE: "0",
  };
  return map[l] || "5";
}

function syslogPriority(level: string): number {
  // Facility 1 (user-level) << 3 + severity
  const severityMap: Record<string, number> = {
    CRITICAL: 2,
    FATAL: 2,
    ERROR: 3,
    WARN: 4,
    WARNING: 4,
    INFO: 6,
    DEBUG: 7,
    TRACE: 7,
  };
  const severity = severityMap[level.toUpperCase()] ?? 6;
  return (1 << 3) + severity; // facility=user(1)
}
