import React, { useState, useRef, useCallback } from 'react';
import {
  Youtube, Facebook, Instagram, Key, Activity, AlertCircle,
  RefreshCw, CheckCircle, Settings, X, ChevronRight,
  Menu, LogOut, LogIn, History, Palette, PlusSquare
} from 'lucide-react';
import {
  PieChart, Pie, Cell, Tooltip as RechartsTooltip, ResponsiveContainer,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Legend
} from 'recharts';
import './index.css';

const API_BASE_URL = '/api';

/* ─── Default channel targets saved per platform ─── */
const DEFAULT_TARGETS = {
  youtube: '',
  facebook: '',
  instagram: '',
};

const PLATFORM_META = {
  youtube: {
    hint: '@handle, channel URL, or video URL',
    placeholder: '...',
    keyLabel: 'YouTube Data API Key',
    keyPlaceholder: '...',
    docLink: { href: 'https://developers.google.com/youtube/v3/getting-started', text: 'Get YouTube API Key' },
  },
  facebook: {
    hint: 'Facebook Page URL or Post URL',
    placeholder: '...',
    keyLabel: 'Apify API Token (Optional if in .env)',
    keyPlaceholder: '...',
    docLink: { href: 'https://docs.apify.com/api/v2#/introduction/authentication', text: 'How to get Apify Token' },
  },
  instagram: {
    hint: 'Instagram handle or media URL',
    placeholder: '...',
    keyLabel: 'Apify API Token (Optional if in .env)',
    keyPlaceholder: '...',
    docLink: { href: 'https://docs.apify.com/api/v2#/introduction/authentication', text: 'How to get Apify Token' },
  },
};

const COLORS = { positive: '#10b981', neutral: '#6b7280', negative: '#ef4444' };

/* ═══════════════════════════════════════════════════════════════ */
export default function App() {
  const [activePlatform, setActivePlatform] = useState('youtube');
  const [apiKey, setApiKey] = useState('');
  const [targets, setTargets] = useState(DEFAULT_TARGETS);  // persisted per platform
  const [settingsOpen, setSettingsOpen] = useState(false);

  const [loading, setLoading] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);
  const [error, setError] = useState('');
  const [statusMsg, setStatusMsg] = useState('');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [samplesOpen, setSamplesOpen] = useState(false);

  const elapsedRef = useRef(null);
  const pollRef = useRef(null);

  const target = targets[activePlatform];

  /* ── Helpers ──────────────────────────────────────────────── */
  const clearTimers = () => {
    clearInterval(elapsedRef.current);
    clearTimeout(pollRef.current);
  };

  const getCount = useCallback(async (platform) => {
    try {
      const res = await fetch(`${API_BASE_URL}/count/${platform}`);
      const data = await res.json();
      return data.count ?? 0;
    } catch { return 0; }
  }, []);

  const loadDashboard = useCallback(async (platform) => {
    try {
      const res = await fetch(`${API_BASE_URL}/dashboard/${platform}`);
      if (!res.ok) throw new Error();
      const data = await res.json();
      setDashboardData(data);
      setStatusMsg('✅ Analysis complete — dashboard updated!');
    } catch {
      setError('Analysis finished but failed to load dashboard. Try refreshing.');
    } finally {
      setLoading(false);
      clearTimers();
    }
  }, []);


  /* ── Smart polling ────────────────────────────────────────────── */
  // Polls /api/task-status/{job_id} every 3 seconds.
  // Loads dashboard when done=true — works even if all rows are duplicates.
  const pollForResults = useCallback(
    (platform, job_id, attempt = 0) => {
      const MAX = 80;       // 80 × 3 s = 4 min max
      const INTERVAL = 3000;

      if (attempt >= MAX) {
        clearTimers();
        setError('Analysis timed out (>4 min). Backend may still be running — wait and try again.');
        setLoading(false);
        return;
      }

      pollRef.current = setTimeout(async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/task-status/${job_id}`);
          const state = await res.json();

          if (state.done) {
            if (state.error) {
              setError(`Analysis error: ${state.error}`);
              setLoading(false);
              clearTimers();
            } else {
              const saved = state.processed || 0;
              setStatusMsg(`✅ Done! ${saved} comments processed.`);
              await loadDashboard(platform);
            }
          } else {
            setStatusMsg(state.status_message || `⏳ Fetching comments… (${(attempt + 1) * 3}s elapsed)`);
            pollForResults(platform, job_id, attempt + 1);
          }
        } catch {
          pollForResults(platform, job_id, attempt + 1);
        }
      }, INTERVAL);
    },
    [loadDashboard]
  );

  /* ── Run analysis ─────────────────────────────────────────── */
  const handleAnalyze = async (e) => {
    if (e) e.preventDefault();

    if (!target.trim()) {
      setSettingsOpen(true);
      setError(`⚙️ Configure your ${activePlatform} target in Settings first.`);
      return;
    }
    // Require an API key for all platforms (YouTube key, or Apify token for FB/IG)
    if ((activePlatform === 'youtube' || activePlatform === 'facebook' || activePlatform === 'instagram') && !apiKey.trim()) {
      if (activePlatform === 'youtube') {
        setError('⚠️ Please enter your YouTube API key.');
      } else {
        setError('⚠️ Please enter your Apify API token for Facebook/Instagram.');
      }
      return;
    }

    setError('');
    setStatusMsg('');
    setLoading(true);
    setDashboardData(null);
    setElapsedSeconds(0);
    clearTimers();

    elapsedRef.current = setInterval(() => setElapsedSeconds(s => s + 1), 1000);

    try {
      const res = await fetch(`${API_BASE_URL}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform: activePlatform,
          target_account: target,
          api_key: apiKey,
          max_videos: 50,
          max_comments_per_video: 100,
        }),
      });

      if (!res.ok) throw new Error('Failed to start analysis pipeline.');
      const data = await res.json();
      setStatusMsg('🚀 Pipeline started — processing…');
      pollForResults(activePlatform, data.job_id);
    } catch (err) {
      setError(err.message || 'Failed to connect to backend.');
      setLoading(false);
      clearTimers();
    }
  };

  const handleManualRefresh = async () => {
    setLoading(true);
    setError('');
    await loadDashboard(activePlatform);
  };

  const handleClearData = async () => {
    if (!window.confirm(`Clear ALL stored ${activePlatform} data? This cannot be undone.`)) return;
    try {
      const res = await fetch(`${API_BASE_URL}/data/${activePlatform}`, { method: 'DELETE' });
      const data = await res.json();
      setDashboardData(null);
      setStatusMsg('');
      setError(`🗑️ ${data.message}`);
    } catch {
      setError('Failed to clear data.');
    }
  };

  const ProgressStepper = ({ statusMsg }) => {
    const steps = [
      "Connecting to Platform...",
      "Identifying Posts/Reels...",
      "Analyzing Sentiment...",
    ];

    const normalize = (s = "") => (s || "").toLowerCase();

    let active = 0;
    const s = normalize(statusMsg);
    if (s.includes("preprocess") || s.includes("preprocessed") || s.includes("analy")) active = 2;
    else if (s.includes("scrap") || s.includes("fetch") || s.includes("identif")) active = 1;
    else active = 0;

    return (
      <div style={{ display: 'flex', gap: 12, marginTop: 12, marginBottom: 8 }}>
        {steps.map((label, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 18,
              height: 18,
              borderRadius: 9,
              background: i <= active ? '#10b981' : '#374151',
              display: 'inline-block'
            }} />
            <div style={{ color: i <= active ? '#10b981' : '#9ca3af', fontSize: 12 }}>{label}</div>
          </div>
        ))}
      </div>
    )
  }

  /* ── Settings panel ────────────────────────────────────────── */
  const SettingsPanel = () => (
    <div className="settings-overlay" onClick={() => setSettingsOpen(false)}>
      <div className="settings-panel" onClick={e => e.stopPropagation()}>
        <div className="settings-header">
          <h3><Settings size={18} /> Channel / Account Settings</h3>
          <button className="icon-btn" onClick={() => setSettingsOpen(false)}><X size={20} /></button>
        </div>
        <p className="settings-hint">
          Set the account once here. The main form only needs your API key.
        </p>

        {['youtube', 'facebook', 'instagram'].map(p => (
          <div className="form-group" key={p} style={{ marginTop: 16 }}>
            <label style={{ textTransform: 'capitalize', display: 'flex', alignItems: 'center', gap: 6 }}>
              {p === 'youtube' && <Youtube size={16} />}
              {p === 'facebook' && <Facebook size={16} />}
              {p === 'instagram' && <Instagram size={16} />}
              {p} — {PLATFORM_META[p].hint}
            </label>
            <div className="api-input-container">
              <input
                type="text"
                className="api-input"
                placeholder={PLATFORM_META[p].placeholder}
                value={targets[p]}
                onChange={e => setTargets(prev => ({ ...prev, [p]: e.target.value }))}
              />
            </div>
          </div>
        ))}

        <button
          className="connect-btn"
          style={{ marginTop: 20 }}
          onClick={() => { setSettingsOpen(false); setError(''); }}
        >
          Save &amp; Close
        </button>
      </div>
    </div>
  );


  /* ── Dashboard render ─────────────────────────────────────── */
  const renderDashboard = () => {
    if (loading) return (
      <div className="results-section loading-state">
        <RefreshCw className="spinner" size={48} />
        <p style={{ fontWeight: 600, fontSize: '1.1em' }}>
          Multi-Agent Pipeline Running… ({elapsedSeconds}s)
        </p>

        {/* Progress stepper */}
        <ProgressStepper statusMsg={statusMsg} />

        {statusMsg && (
          <p style={{ fontSize: '0.88em', color: 'var(--text-secondary)', marginTop: 8 }}>
            {statusMsg}
          </p>
        )}
        <p style={{ fontSize: '0.82em', color: 'var(--text-secondary)', marginTop: 4 }}>
          For channels, all videos are scanned — this may take a minute or two.
        </p>
      </div>
    );

    if (!dashboardData) return (
      <div className="results-section">
        <div className="placeholder-results">
          <Activity size={48} style={{ color: 'var(--text-secondary)', marginBottom: 16 }} />
          <h3>No Data Analyzed Yet</h3>
          <p>
            Enter your API key and click <strong>Run Analysis</strong>.
            {!target && (
              <> First, <button className="inline-link" onClick={() => setSettingsOpen(true)}>
                configure your target account ↗
              </button></>
            )}
          </p>
        </div>
      </div>
    );

    const { summary, charts, raw_samples } = dashboardData;
    return (
      <div className="dashboard-grid">
        {statusMsg && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#10b981', fontWeight: 600, marginBottom: 8 }}>
            <CheckCircle size={18} />{statusMsg}
          </div>
        )}
        
        {summary.bi_summary && (
          <div className="bi-summary-card" style={{ padding: '20px', backgroundColor: 'var(--bg-secondary)', borderRadius: '12px', marginBottom: '24px', border: '1px solid var(--border)' }}>
            <h3 style={{ marginBottom: '8px', color: 'var(--text-primary)' }}>🤖 Business Intelligence Summary</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '1.1em', lineHeight: '1.5' }}>{summary.bi_summary}</p>
          </div>
        )}

        <div className="summary-cards">
          <div className="card">
            <h4>Total Comments</h4>
            <div className="value">{summary.total_comments}</div>
          </div>
          <div className="card">
            <h4>Avg Sentiment</h4>
            <div className="value">{(summary.avg_sentiment * 100).toFixed(1)} / 100</div>
          </div>
          <div className="card card-action" onClick={handleManualRefresh}>
            <h4>Refresh</h4>
            <div className="value"><RefreshCw size={26} /></div>
          </div>
          <div className="card card-danger" onClick={handleClearData}>
            <h4>Clear Data</h4>
            <div className="value" style={{ fontSize: '1.4rem' }}>🗑️</div>
          </div>
        </div>

        <div className="charts-container">
          <div className="chart-box">
            <h3>Sentiment Distribution</h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={charts.sentiment_pie} cx="50%" cy="50%"
                  innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                  {charts.sentiment_pie.map((entry, i) => (
                    <Cell key={i} fill={COLORS[entry.name.toLowerCase()] || COLORS.neutral} />
                  ))}
                </Pie>
                <RechartsTooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-box">
            <h3>Sentiment Timeline</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={charts.sentiment_timeline}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
                <XAxis dataKey="date" stroke="#9aa0a6" />
                <YAxis stroke="#9aa0a6" />
                <RechartsTooltip contentStyle={{ backgroundColor: '#16181d', border: 'none' }} />
                <Legend />
                <Line type="monotone" dataKey="positive" stroke={COLORS.positive} strokeWidth={3} />
                <Line type="monotone" dataKey="negative" stroke={COLORS.negative} strokeWidth={3} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="feed-container">
          <button
            className="feed-toggle"
            onClick={() => setSamplesOpen(o => !o)}
            aria-expanded={samplesOpen}
          >
            <h3>Recent Processed Samples ({raw_samples.length})</h3>
            <span className="feed-chevron">{samplesOpen ? '▾' : '▸'}</span>
          </button>

          {samplesOpen && (
            <div className="sample-list">
              {raw_samples.map((s, i) => (
                <div key={i} className={`sample-item border-${s.sentiment_label}`}>
                  <p className="sample-text">"{s.clean_text}"</p>
                  <span className={`badge badge-${s.sentiment_label}`}>
                    {s.sentiment_label} ({s.sentiment_score.toFixed(2)})
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  /* ── Layout ──────────────────────────────────────────────────  */
  return (
    <div className="app-container">
      {settingsOpen && <SettingsPanel />}

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header" style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '40px' }}>
          <div className="logo" style={{ marginBottom: 0 }}>
            <Activity size={32} />
            <h2>AgentFlow</h2>
          </div>
        </div>

        <div className="platform-nav">
          <h3 className="nav-title">Platform</h3>
          {['youtube', 'facebook', 'instagram'].map(p => (
            <button key={p}
              className={`platform-btn ${activePlatform === p ? 'active' : ''}`}
              onClick={() => { setActivePlatform(p); setDashboardData(null); setStatusMsg(''); setError(''); }}
            >
              {p === 'youtube' && <Youtube />}
              {p === 'facebook' && <Facebook />}
              {p === 'instagram' && <Instagram />}
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>

        {/* Quick target indicator */}
        <div style={{ marginTop: 'auto', padding: '16px 12px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <p style={{ fontSize: '0.75em', color: 'var(--text-secondary)', marginBottom: 6 }}>
            Target Account
          </p>
          <p style={{ fontSize: '0.82em', wordBreak: 'break-all', color: target ? '#e8eaed' : '#6b7280' }}>
            {target || 'Not set'}
          </p>
          <button className="inline-link" style={{ marginTop: 8, fontSize: '0.8em' }}
            onClick={() => setSettingsOpen(true)}>
            <Settings size={13} /> Change target
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="main-content">
        <header className="main-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1>Social Media Multi-Agent Analysis</h1>
            <p>Fetch &amp; analyse comments from {activePlatform.charAt(0).toUpperCase() + activePlatform.slice(1)} channels, pages, and accounts.</p>
          </div>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <button 
              className="connect-btn" 
              onClick={() => {
                setDashboardData(null);
                setTargets(DEFAULT_TARGETS);
                setApiKey('');
              }} 
              style={{ padding: '8px 16px', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <PlusSquare size={18} /> New Analyze
            </button>
            <button 
              className="icon-btn refresh-pipeline-btn" 
              onClick={() => handleAnalyze()} 
              title="Fetch latest data pipeline"
              disabled={loading}
            >
              <RefreshCw size={24} className={loading && dashboardData === null ? 'spinner' : ''} />
            </button>
          </div>
        </header>

        <section className="api-section">
          <form onSubmit={handleAnalyze} className="config-form">

            {/* Always show input so user can put Apify API Token if they want */}
            <div className="form-group">
              <label>{PLATFORM_META[activePlatform].keyLabel}</label>
              <div className="api-input-container">
                <Key className="api-icon" size={20} />
                <input
                  type="password"
                  className="api-input"
                  placeholder={PLATFORM_META[activePlatform].keyPlaceholder}
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                />
              </div>
            </div>

            {/* Inline target badge */}
            {target ? (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85em',
                color: 'var(--text-secondary)', marginBottom: 8
              }}>
                <ChevronRight size={14} />
                Fetching from: <strong style={{ color: '#e8eaed' }}>{target}</strong>
                <button type="button" className="inline-link" onClick={() => setSettingsOpen(true)}>
                  change
                </button>
                <span style={{ color: 'var(--border)' }}>|</span>
                <a
                  href={PLATFORM_META[activePlatform].docLink.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="doc-link"
                >
                  {PLATFORM_META[activePlatform].docLink.text}
                </a>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <button type="button" className="inline-link"
                  style={{ fontSize: '0.88em' }} onClick={() => setSettingsOpen(true)}>
                  ⚙️ Set target account first
                </button>
                <span style={{ color: 'var(--border)', fontSize: '0.8rem' }}>|</span>
                <a
                  href={PLATFORM_META[activePlatform].docLink.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="doc-link"
                >
                  {PLATFORM_META[activePlatform].docLink.text}
                </a>
              </div>
            )}

            {error && (
              <div className="error-message">
                <AlertCircle size={16} /> {error}
              </div>
            )}

            <button type="submit" className="connect-btn" disabled={loading}>
              {loading ? 'Processing Pipeline…' : 'Run Analysis Pipeline'}
            </button>
          </form>
        </section>

        {renderDashboard()}
      </main>
    </div>
  );
}
