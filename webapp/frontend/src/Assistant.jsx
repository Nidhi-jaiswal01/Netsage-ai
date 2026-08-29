import { useState } from 'react';

const API_BASE = 'http://localhost:8000';

function Assistant() {
  const [symptom, setSymptom] = useState('');
  const [notes, setNotes] = useState('');
  const [showOutput, setShowOutput] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [editedDiagnosis, setEditedDiagnosis] = useState(null);
  const [reviewNote, setReviewNote] = useState('');
  const [reviewed, setReviewed] = useState(false);

  const handleDiagnose = async (e) => {
    e.preventDefault();
    if (!symptom.trim()) return;
    setLoading(true);
    setResult(null);
    setReviewed(false);
    setEditMode(false);
    try {
      const res = await fetch(`${API_BASE}/diagnose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symptom,
          packet_tracer_notes: notes,
          show_output: showOutput,
        }),
      });
      const data = await res.json();
      setResult(data);
      setEditedDiagnosis(data.diagnosis);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const submitReview = async (verdict) => {
    if (!result) return;
    const body = {
      verdict,
      note: reviewNote,
      edited_diagnosis: verdict === 'Edited' ? editedDiagnosis : null,
    };
    try {
      const res = await fetch(`${API_BASE}/cases/${result.id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      setResult(data);
      setReviewed(true);
      setEditMode(false);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="assistant">
      <div className="term-body intro">
        <div className="prompt-line">
          <span className="prompt">netsage@lab</span>
          <span className="cmd">:~$ diagnose --interactive</span>
          <span className="cursor"></span>
        </div>
        <h1>NetSage AI Assistant</h1>
        <p className="subtitle">
          Describe the symptom, paste Packet Tracer notes and show-command
          output. NetSage proposes a root cause, OSI layer, next command,
          and fix — pending your review.
        </p>
      </div>

      <form className="panel form-panel" onSubmit={handleDiagnose}>
        <label className="field-label">Symptom</label>
        <textarea
          rows={3}
          placeholder="e.g. PC on VLAN 30 cannot reach anything, including its own gateway."
          value={symptom}
          onChange={(e) => setSymptom(e.target.value)}
          required
        />

        <label className="field-label">Packet Tracer Notes</label>
        <textarea
          rows={3}
          placeholder="Topology notes, interface configs, anything relevant..."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />

        <label className="field-label">Show Command Output</label>
        <textarea
          rows={5}
          placeholder="Paste show vlan brief / show ip interface brief / etc..."
          value={showOutput}
          onChange={(e) => setShowOutput(e.target.value)}
        />

        <button type="submit" disabled={loading}>
          {loading ? 'Diagnosing...' : 'Diagnose'}
        </button>
      </form>

      {result && (
        <div className="panel result-panel">
          <div className="section-title">diagnosis — case {result.id}</div>

          {!editMode ? (
            <div className="diag-grid">
              <div>
                <span className="detail-label">Root Cause</span>
                <p>{result.diagnosis.root_cause}</p>
              </div>
              <div>
                <span className="detail-label">OSI Layer</span>
                <p>{result.diagnosis.osi_layer}</p>
              </div>
              <div>
                <span className="detail-label">Confidence</span>
                <p>{Math.round((result.diagnosis.confidence || 0) * 100)}%</p>
              </div>
              <div>
                <span className="detail-label">Category</span>
                <p>{result.diagnosis.category}</p>
              </div>
              <div className="full">
                <span className="detail-label">Evidence</span>
                <p>{result.diagnosis.evidence}</p>
              </div>
              <div className="full">
                <span className="detail-label">Next Command</span>
                <p className="mono">{result.diagnosis.next_command}</p>
              </div>
              <div className="full">
                <span className="detail-label">Fix Steps</span>
                <ol>
                  {(result.diagnosis.fix_steps || []).map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
              </div>
            </div>
          ) : (
            <div className="diag-grid">
              <div className="full">
                <span className="detail-label">Root Cause</span>
                <textarea
                  rows={2}
                  value={editedDiagnosis.root_cause}
                  onChange={(e) =>
                    setEditedDiagnosis({ ...editedDiagnosis, root_cause: e.target.value })
                  }
                />
              </div>
              <div className="full">
                <span className="detail-label">Evidence</span>
                <textarea
                  rows={2}
                  value={editedDiagnosis.evidence}
                  onChange={(e) =>
                    setEditedDiagnosis({ ...editedDiagnosis, evidence: e.target.value })
                  }
                />
              </div>
              <div className="full">
                <span className="detail-label">Next Command</span>
                <input
                  value={editedDiagnosis.next_command}
                  onChange={(e) =>
                    setEditedDiagnosis({ ...editedDiagnosis, next_command: e.target.value })
                  }
                />
              </div>
            </div>
          )}

          {!reviewed ? (
            <div className="review-bar">
              <input
                className="note-input"
                placeholder="Reviewer note (optional)..."
                value={reviewNote}
                onChange={(e) => setReviewNote(e.target.value)}
              />
              <button className="accept" onClick={() => submitReview('Accepted')}>
                Accept
              </button>
              <button
                className="edit"
                onClick={() => {
                  if (editMode) {
                    submitReview('Edited');
                  } else {
                    setEditMode(true);
                  }
                }}
              >
                {editMode ? 'Save Edit' : 'Edit'}
              </button>
              <button className="reject" onClick={() => submitReview('Rejected')}>
                Reject
              </button>
            </div>
          ) : (
            <div className={`badge-line ${result.verdict.toLowerCase()}`}>
              Marked {result.verdict} ✓
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default Assistant;