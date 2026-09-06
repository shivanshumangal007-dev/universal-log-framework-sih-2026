import { useEffect, useState, useCallback } from "react";
import {
  Activity,
  FileText,
  ClipboardList,
  TrendingUp,
  Clock,
  Server,
} from "lucide-react";
import { api } from "../lib/api";
import type { ParsedLog, ReviewItem } from "../lib/api";
import StatsCard from "../components/StatsCard";

export default function DashboardPage() {
  const [throughput, setThroughput] = useState<number>(0);
  const [recentLogs, setRecentLogs] = useState<ParsedLog[]>([]);
  const [pendingReview, setPendingReview] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [tp, logs, reviews] = await Promise.all([
        api.getThroughput(),
        api.getRecentLogs(5),
        api.getReviewQueue("pending"),
      ]);
      setThroughput(tp.events_last_10s);
      setRecentLogs(logs);
      setPendingReview(reviews);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load stats");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-sm text-neutral-500 mt-1">
          Overview of log ingestion and review pipeline
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
          {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          title="Throughput (10s)"
          value={throughput}
          icon={<TrendingUp className="h-5 w-5" />}
          accent
        />
        <StatsCard
          title="Recent Logs"
          value={recentLogs.length}
          icon={<FileText className="h-5 w-5" />}
        />
        <StatsCard
          title="Pending Review"
          value={pendingReview.length}
          icon={<ClipboardList className="h-5 w-5" />}
        />
        <StatsCard
          title="Status"
          value="Healthy"
          icon={<Activity className="h-5 w-5" />}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Logs */}
        <div className="rounded-lg border border-neutral-200 bg-white">
          <div className="border-b border-neutral-200 px-4 py-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Recent Parsed Logs</h2>
            <span className="text-xs text-neutral-500">Last 5</span>
          </div>
          <div className="divide-y divide-neutral-100">
            {loading && recentLogs.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-neutral-400">Loading…</div>
            ) : recentLogs.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-neutral-400">No logs yet</div>
            ) : (
              recentLogs.map((log) => (
                <div key={log.event_id} className="px-4 py-3 flex items-start gap-3">
                  <Server className="mt-0.5 h-4 w-4 text-neutral-400 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-neutral-900 truncate">{log.source}</p>
                    <p className="text-xs text-neutral-500 truncate">{log.raw_line}</p>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="inline-flex items-center rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-medium text-neutral-700 uppercase">
                        {log.format}
                      </span>
                      <span className="text-[10px] text-neutral-400 flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(log.ingested_at).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Pending Review */}
        <div className="rounded-lg border border-neutral-200 bg-white">
          <div className="border-b border-neutral-200 px-4 py-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Pending Review</h2>
            <span className="text-xs text-neutral-500">Top 5</span>
          </div>
          <div className="divide-y divide-neutral-100">
            {loading && pendingReview.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-neutral-400">Loading…</div>
            ) : pendingReview.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-neutral-400">Queue is empty</div>
            ) : (
              pendingReview.slice(0, 5).map((item) => (
                <div key={item.event_id} className="px-4 py-3 flex items-start gap-3">
                  <ClipboardList className="mt-0.5 h-4 w-4 text-orange-500 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-neutral-900 truncate">{item.source}</p>
                    <p className="text-xs text-neutral-500 truncate">{item.raw_line}</p>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="inline-flex items-center rounded-full bg-orange-50 px-2 py-0.5 text-[10px] font-medium text-orange-600 uppercase">
                        {Math.round(item.confidence * 100)}% confidence
                      </span>
                      <span className="text-[10px] text-neutral-400">
                        {new Date(item.ingested_at).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
