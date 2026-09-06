import { useEffect, useState, useCallback, useMemo } from "react";
import {
  FileText,
  ChevronLeft,
  ChevronRight,
  Search,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api } from "../lib/api";
import type { ParsedLog } from "../lib/api";
import FormatOutput from "../components/FormatOutput";

const PAGE_SIZE = 25;

export default function LogsPage() {
  const [logs, setLogs] = useState<ParsedLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getRecentLogs(200);
      setLogs(data);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load logs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return logs;
    return logs.filter(
      (l) =>
        l.raw_line.toLowerCase().includes(q) ||
        l.source.toLowerCase().includes(q) ||
        l.format.toLowerCase().includes(q)
    );
  }, [logs, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages - 1);
  const pageLogs = filtered.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Parsed Logs</h1>
          <p className="text-sm text-neutral-500 mt-1">
            Recently ingested and parsed log events
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={["h-4 w-4", loading ? "animate-spin" : ""].join(" ")} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
          {error}
        </div>
      )}

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" />
        <input
          type="text"
          placeholder="Search by source, raw line, or format..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          className="w-full rounded-md border border-neutral-200 bg-white py-2 pl-9 pr-4 text-sm outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors"
        />
      </div>

      <div className="rounded-lg border border-neutral-200 bg-white overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-200 bg-neutral-50">
                <th className="px-4 py-3 text-left font-medium text-neutral-600 w-10"></th>
                <th className="px-4 py-3 text-left font-medium text-neutral-600">Source</th>
                <th className="px-4 py-3 text-left font-medium text-neutral-600">Format</th>
                <th className="px-4 py-3 text-left font-medium text-neutral-600">Timestamp</th>
                <th className="px-4 py-3 text-left font-medium text-neutral-600">Raw Line</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {loading && logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-neutral-400">
                    Loading logs…
                  </td>
                </tr>
              ) : pageLogs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-neutral-400">
                    No logs found
                  </td>
                </tr>
              ) : (
                pageLogs.map((log) => {
                  const isExpanded = expanded.has(log.event_id);
                  return (
                    <>
                      <tr
                        key={log.event_id}
                        className="hover:bg-neutral-50 transition-colors cursor-pointer"
                        onClick={() => toggleExpand(log.event_id)}
                      >
                        <td className="px-4 py-3">
                          <button className="rounded p-1 hover:bg-neutral-200 transition-colors">
                            {isExpanded ? (
                              <ChevronUp className="h-4 w-4 text-neutral-500" />
                            ) : (
                              <ChevronDown className="h-4 w-4 text-neutral-500" />
                            )}
                          </button>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <FileText className="h-4 w-4 text-neutral-400" />
                            <span className="font-medium truncate max-w-[200px]">{log.source}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-medium text-neutral-700 uppercase">
                            {log.format}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-neutral-600 whitespace-nowrap">
                          {new Date(log.event_timestamp.replace(" ", "T") + (log.event_timestamp.endsWith("Z") ? "" : "Z")).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })}
                        </td>
                        <td className="px-4 py-3 text-neutral-600 truncate max-w-[300px]">
                          {log.raw_line}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr>
                          <td colSpan={5} className="bg-neutral-50 px-4 py-3">
                            <div className="space-y-3 text-xs">
                              <div>
                                <p className="font-semibold text-neutral-700 mb-1">Raw Line</p>
                                <p className="font-mono bg-white border border-neutral-200 rounded p-2 text-neutral-600 break-all">
                                  {log.raw_line}
                                </p>
                              </div>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                <FormatOutput
                                  fieldsJson={log.fields_json}
                                  source={log.source}
                                  label="Fields Output"
                                />
                                <div>
                                  <p className="font-semibold text-neutral-700 mb-1">Metadata JSON</p>
                                  <pre className="font-mono bg-white border border-neutral-200 rounded p-2 text-neutral-600 overflow-auto max-h-48">
                                    {JSON.stringify(
                                      JSON.parse(log.metadata_json || "{}"),
                                      null,
                                      2
                                    )}
                                  </pre>
                                </div>
                              </div>
                              <div className="flex gap-4 text-neutral-500">
                                <span>Event ID: <span className="font-mono text-neutral-700">{log.event_id}</span></span>
                                <span>Ingested: {new Date(log.ingested_at.replace(" ", "T") + (log.ingested_at.endsWith("Z") ? "" : "Z")).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })}</span>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between border-t border-neutral-200 px-4 py-3">
          <p className="text-xs text-neutral-500">
            Showing {filtered.length > 0 ? currentPage * PAGE_SIZE + 1 : 0} to{" "}
            {Math.min((currentPage + 1) * PAGE_SIZE, filtered.length)} of {filtered.length} results
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={currentPage === 0}
              className="inline-flex items-center rounded-md border border-neutral-200 bg-white px-2 py-1.5 text-sm text-neutral-700 hover:bg-neutral-50 disabled:opacity-50 transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-xs text-neutral-600 font-medium">
              Page {currentPage + 1} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={currentPage >= totalPages - 1}
              className="inline-flex items-center rounded-md border border-neutral-200 bg-white px-2 py-1.5 text-sm text-neutral-700 hover:bg-neutral-50 disabled:opacity-50 transition-colors"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
