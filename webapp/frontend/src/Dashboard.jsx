import { useEffect, useState } from 'react';

const API_BASE = 'http://localhost:8000';

function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [cases, setCases] = useState([]);
  const [openId, setOpenId] = useState(null);

  const load = async () => {
    try {
      const [sRes, cRes] = await Promise.all([
        fetch(`${API_BASE}/summary`),
        fetch(`${API_BASE}/cases`),
      ]);
      setSummary(await sRes.json());
      setCases(await cRes.json());
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (!summary) return <div className="panel">Loading...</div>;

  const { total, verdict_counts, category_counts } = summary;
  const maxCat = Math.max(1, ...Object.values(category_counts));

  const verdictColors = {
    Accepted: '#3fd67a',
    Edited: '#e0a12c',
    Rejected: '#f2555a',
    Pending: '#6b7a8c',
  };

  let acc = 0;
  const gradientParts = Object.entries(verdict_counts)
    .filter(([, count]) => count > 0)
    .map(([verdict, count]) => {
      const start = (acc / total) * 360;
      acc += count;
      const end = (acc / total) * 360;
      return `${verdictColors[verdict]} ${start}deg ${end}deg`;
    });
  const gradient = total > 0 ? `conic-gradient(${gradientParts.join(', ')})` : '#1a212c';
  const acceptedPct = total > 0 ? Math.round(((verdict_counts.Accepted || 0) / total) * 100) : 0;

  return (
    <div className="dashboard">
      <div className="term-body intro">
        <div className="prompt-line">
          <span className="prompt">netsage@lab</span>
          <span className="cmd">:~$ show diagnosis --summary</span>
          <span className="cursor"></span>
        </div>
        <h1>NetSage AI — Diagnosis Dashboard</h1>
        <p className="subtitle">
          {total} case{total !== 1 ? 's' : ''} · AI diagnosis · human-reviewed
        </p>
      </div>

      <div className="stats">
        <div className="stat-card" style={{ '--bar-color': '#4fa3f7' }}>
          <div className="stat-num">{total}</div>
          <div className="stat-label">Total Cases</div>
        </div>
        <div className="stat-card" style={{ '--bar-color': '#3fd67a' }}>
          <div className="stat-num">{verdict_counts.Accepted || 0}</div>
          <div className="stat-label">Accepted</div>
        </div>
        <div className="stat-card" style={{ '--bar-color': '#f2555a' }}>
          <div className="stat-num">
            {(verdict_counts.Edited || 0) + (verdict_counts.Rejected || 0)}
          </div>
          <div className="stat-label">Edited / Rejected</div>
        </div>
        <div className="stat-card" style={{ '--bar-color': '#e0a12c' }}>
          <div className="stat-num">{verdict_counts.Pending || 0}</div>
          <div className="stat-label">Pending Review</div>
        </div>
      </div>

      <section>
        <div className="section-title">cases by category</div>
        <div className="panel">
          {Object.entries(category_counts).map(([cat, count]) => (
            <div className="cat-row" key={cat}>
              <div className="cat-name">{cat}</div>
              <div className="cat-track">
                <div
                  className="cat-fill"
                  style={{ width: `${(count / maxCat) * 100}%` }}
                ></div>
              </div>
              <div className="cat-count">{count}</div>
            </div>
          ))}
          {Object.keys(category_counts).length === 0 && (
            <p className="empty-note">No cases yet — run a diagnosis first.</p>
          )}
        </div>
      </section>

      <section>
        <div className="section-title">human review verdicts</div>
        <div className="panel verdict-wrap">
          <div className="donut" style={{ background: gradient }}>
            <div className="donut-hole">
              <div className="donut-pct">{acceptedPct}%</div>
              <div className="donut-label">ACCEPTED</div>
            </div>
          </div>
          <div className="legend">
            {Object.entries(verdict_counts).map(([v, count]) => (
              <div className="legend-item" key={v}>
                <span className="swatch" style={{ background: verdictColors[v] }}></span>
                {v} — {count}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section>
        <div className="section-title">case log (click a row to expand)</div>
        <div className="panel">
          <div className="case-log">
            {cases.map((c) => (
              <div
                key={c.id}
                className={`case-entry ${openId === c.id ? 'open' : ''}`}
                onClick={() => setOpenId(openId === c.id ? null : c.id)}
              >
                <div className="case-head">
                  <span className="case-id">{c.id}</span>
                  <span className="case-cat">{c.diagnosis.category}</span>
                  <span className="case-symptom">{c.symptom}</span>
                  <span className={`badge ${c.verdict.toLowerCase()}`}>{c.verdict}</span>
                </div>
                <div className="case-detail">
                  <div className="detail-row">
                    <span className="detail-label">Root Cause</span>
                    {c.diagnosis.root_cause}
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Next Command</span>
                    {c.diagnosis.next_command}
                  </div>
                  {c.reviewer_note && (
                    <div className="detail-row">
                      <span className="detail-label">Reviewer Note</span>
                      <span className="detail-note">{c.reviewer_note}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {cases.length === 0 && <p className="empty-note">No cases logged yet.</p>}
          </div>
        </div>
      </section>
    </div>
  );
}

export default Dashboard;