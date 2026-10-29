import { useEffect, useState } from "react";
type S = "done" | "run" | "pen" | "err";
type Row = { step: string; status: S; startedAt: string; duration: string; attempts: number; insight: string };
const C: Record<S, string> = { done: "#10b981", run: "#3b82f6", pen: "#64748b", err: "#ef4444" };
export default function Dashboard({ wf = "order-1001" }: { wf?: string }) {
  const [rows, setRows] = useState<Row[]>([]);
  useEffect(() => {
    const es = new EventSource(`/api/workflows/${wf}/stream`); // SSE from the backend
    es.onmessage = (e) => setRows(JSON.parse(e.data));
    return () => es.close();
  }, [wf]);
  return (
    <div className="min-h-screen bg-[#0b0f17] p-8 text-slate-200">
      <h1 className="text-2xl font-bold">Order Processing <span className="ml-2 rounded-full border border-emerald-500 px-2 text-xs text-emerald-400">Active</span></h1>
      <div className="my-6 flex gap-3 overflow-x-auto">
        {rows.map((r) => (
          <div key={r.step} className="min-w-44 rounded-lg border border-[#1e293b] p-4" style={{ borderTop: `3px solid ${C[r.status]}` }}>
            <b>{r.step}</b>
            <div className={`mt-2 text-xs ${r.status === "run" ? "animate-pulse" : ""}`} style={{ color: C[r.status] }}>{r.status}</div>
          </div>
        ))}
      </div>
      <table className="w-full border border-[#1e293b] text-sm">
        <thead><tr className="text-left text-slate-400">{["Step", "Status", "Started At", "Duration", "Attempts", "AI Insights / Logs"].map((h) => <th key={h} className="p-3">{h}</th>)}</tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.step} className="border-t border-[#1e293b]"><td className="p-3">{r.step}</td><td style={{ color: C[r.status] }}>{r.status}</td><td>{r.startedAt}</td><td>{r.duration}</td><td>{r.attempts}</td><td>{r.insight}</td></tr>
        ))}</tbody>
      </table>
    </div>
  );
}
