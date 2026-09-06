import { useEffect, useState, useCallback, useMemo } from "react";
import {
  ClipboardList,
  Check,
  X,
  RefreshCw,
  Search,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
} from "lucide-react";
import { api } from "../lib/api";
import type { ReviewItem } from "../lib/api";

const PAGE_SIZE = 20;

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [actingId, setActingId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getReviewQueue("pending");
      setItems(data);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load review queue");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (i) =>
        i.raw_line.toLowerCase().includes(q) ||
        i.source.toLowerCase().includes(q)
    );
  }, [items, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages - 1);
  const pageItems = filtered.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleApprove = async (id: string) => {
    setActingId(id);
    try {
      await api.approveReview(id);
      setItems((prev) => prev.filter((i) => i.event_id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setActingId(null);
    }
  };

  const handleReject = async (id: string) => {
    setActingId(id);
    try {
      await api.rejectReview(id);
      setItems((prev) => prev.filter((i) => i.event_id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reject failed");
    } finally {
      setActingId(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Review Queue</h1>
          <p className="text-sm text-neutral-500 mt-1">
            Low-confidence inferred logs awaiting human review
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
          placeholder="Search by source or raw line..."
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
                <th className="px-4 py-3 text-left font-medium text-neutral-600">Confidence</th>
                <th className="px-4 py-3 text-left font-medium text-neutral-600">Timestamp</th>
                <th className="px-4 py-3 text-left font-medium text-neutral-600">Raw Line</th>
                <th className="px-4 py-3 text-right font-medium text-neutral-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {loading && items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-neutral-400">
                    Loading review queue…
                  </td>
                </tr>
              ) : pageItems.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <AlertTriangle className="h-8 w-8 text-neutral-300" />
                      <p className="text-sm text-neutral-400">Queue is empty</p>
                      <p className="text-xs text-neutral-400">No pending items to review</p>
                    </div>
                  </td>
                </tr>
              ) : (
                pageItems.map((item) => {
                  const isExpanded = expanded.has(item.event_id);
                  const isActing = actingId === item.event_id;
                  return (
                    <>
                      <tr
                        key={item.event_id}
                        className="hover:bg-neutral-50 transition-colors"
                      >
                        <td className="px-4 py-3">
                          <button
                            onClick={() => toggleExpand(item.event_id)}
                            className="rounded p-1 hover:bg-neutral-200 transition-colors"
                          >
                            {isExpanded ? (
                              <ChevronUp className="h-4 w-4 text-neutral-500" />
                            ) : (
                              <ChevronDown className="h-4 w-4 text-neutral-500" />
                            )}
                          </button>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <ClipboardList className="h-4 w-4 text-neutral-400" />
                            <span className="font-medium truncate max-w-[180px]">{item.source}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 w-16 rounded-full bg-neutral-100 overflow-hidden">
                              <div
                                className="h-full rounded-full bg-orange-500"
                                style={{ width: `${Math.round(item.confidence * 100)}%` }}
                              />
                            </div>
                            <span className="text-xs text-neutral-600 font-medium">
                              {Math.round(item.confidence * 100)}%
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-neutral-600 whitespace-nowrap">
                          {new Date(item.event_timestamp).toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-neutral-600 truncate max-w-[250px]">
                          {item.raw_line}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => handleApprove(item.event_id)}
                              disabled={isActing}
                              className="inline-flex items-center gap-1 rounded-md bg-green-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
                            >
                              <Check className="h-3.5 w-3.5" />
                              Approve
                            </button>
                            <button
                              onClick={() => handleReject(item.event_id)}
                              disabled={isActing}
                              className="inline-flex items-center gap-1 rounded-md bg-red-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
                            >
                              <X className="h-3.5 w-3.5" />
                              Reject
                            </button>
                          </div>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr>
                          <td colSpan={6} className="bg-neutral-50 px-4 py-3">
                            <div className="space-y-3 text-xs">
                              <div>
                                <p className="font-semibold text-neutral-700 mb-1">Raw Line</p>
                                <p className="font-mono bg-white border border-neutral-200 rounded p-2 text-neutral-600 break-all">
                                  {item.raw_line}
                                </p>
                              </div>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                <div>
                                  <p className="font-semibold text-neutral-700 mb-1">Inferred Fields JSON</p>
                                  <pre className="font-mono bg-white border border-neutral-200 rounded p-2 text-neutral-600 overflow-auto max-h-48">
                                    {JSON.stringify(
                                      JSON.parse(item.fields_json || "{}"),
                                      null,
                                      2
                                    )}
                                  </pre>
                                </div>
                                <div>
                                  <p className="font-semibold text-neutral-700 mb-1">Metadata JSON</p>
                                  <pre className="font-mono bg-white border border-neutral-200 rounded p-2 text-neutral-600 overflow-auto max-h-48">
                                    {JSON.stringify(
                                      JSON.parse(item.metadata_json || "{}"),
                                      null,
                                      2
                                    )}
                                  </pre>
                                </div>
                              </div>
                              <div className="flex gap-4 text-neutral-500">
                                <span>Event ID: <span className="font-mono text-neutral-700">{item.event_id}</span></span>
                                <span>Ingested: {new Date(item.ingested_at).toLocaleString()}</span>
                                <span>Format: <span className="font-mono text-neutral-700">{item.format}</span></span>
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
              <ChevronDown className="h-4 w-4 rotate-90" />
            </button>
            <span className="text-xs text-neutral-600 font-medium">
              Page {currentPage + 1} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={currentPage >= totalPages - 1}
              className="inline-flex items-center rounded-md border border-neutral-200 bg-white px-2 py-1.5 text-sm text-neutral-700 hover:bg-neutral-50 disabled:opacity-50 transition-colors"
            >
              <ChevronDown className="h-4 w-4 -rotate-90" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
