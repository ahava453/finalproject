import React, { useState } from 'react';
import { Youtube, Facebook, Instagram, Key, User, Activity, AlertCircle, RefreshCw } from 'lucide-react';
import {
  PieChart, Pie, Cell, Tooltip as RechartsTooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
  LineChart, Line
} from 'recharts';
import './index.css';

const API_BASE_URL = 'http://localhost:8000/api';

const COLORS = {
  positive: '#10b981',
  neutral: '#6b7280',
  negative: '#ef4444'
};

function App() {
  const [activePlatform, setActivePlatform] = useState('youtube');
  const [targetAccount, setTargetAccount] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);
  const [error, setError] = useState('');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const elapsedRef = React.useRef(null);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!targetAccount) {
      setError('Please enter a YouTube video URL');
      return;
    }

    setError('');
    setLoading(true);
    setDashboardData(null);
    setElapsedSeconds(0);
    // Start elapsed timer
    elapsedRef.current = setInterval(() => setElapsedSeconds(s => s + 1), 1000);

    try {
      // 1. Trigger the Multi-Agent Pipeline
      const triggerRes = await fetch(`${API_BASE_URL}/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          platform: activePlatform,
          target_account: targetAccount,
          api_key: apiKey
        }),
      });

      if (!triggerRes.ok) throw new Error('Failed to start analysis pipeline');

      // Poll for results: the background task takes time for API call + NLP
      pollForResults(0);

    } catch (err) {
      setError(err.message || 'Failed to connect to backend.');
      setLoading(false);
    }
  };

  const pollForResults = async (attempt) => {
    const MAX_ATTEMPTS = 40;
    const POLL_INTERVAL = 3000;

    if (attempt >= MAX_ATTEMPTS) {
      clearInterval(elapsedRef.current);
      setError('Analysis timed out after 2 minutes. The NLP model may still be processing — wait a moment and click "Run Analysis Pipeline" again.');
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/dashboard/${activePlatform}`);
      if (!res.ok) throw new Error('Failed to fetch dashboard data');
      const data = await res.json();

      if (data && data.summary && data.summary.total_comments > 0) {
        clearInterval(elapsedRef.current);
        setDashboardData(data);
        setLoading(false);
      } else {
        setTimeout(() => pollForResults(attempt + 1), POLL_INTERVAL);
      }
    } catch (err) {
      setTimeout(() => pollForResults(attempt + 1), POLL_INTERVAL);
    }
  };

  const fetchDashboard = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/dashboard/${activePlatform}`);
      if (!res.ok) throw new Error('Failed to fetch dashboard data');
      const data = await res.json();
      setDashboardData(data);
    } catch (err) {
      setError('Error compiling visualization data.');
    } finally {
      setLoading(false);
    }
  };

  const renderDashboard = () => {
    if (loading) {
      return (
        <div className="results-section loading-state">
          <RefreshCw className="spinner" size={48} />
          <p>Multi-Agent Pipeline Running... ({elapsedSeconds}s)</p>
          <p style={{ fontSize: '0.85em', color: 'var(--text-secondary)' }}>Fetching comments &amp; running NLP sentiment analysis. The model loads once and is fast on subsequent runs.</p>
        </div>
      );
    }

    if (!dashboardData) {
      return (
        <div className="results-section">
          <div className="placeholder-results">
            <Activity size={48} style={{ color: 'var(--text-secondary)', marginBottom: '16px' }} />
            <h3>No Data Analyzed Yet</h3>
            <p>Connect to an API and enter a target account to initiate the data fetching and processing agents.</p>
          </div>
        </div>
      );
    }

    const { summary, charts, raw_samples } = dashboardData;

    return (
      <div className="dashboard-grid">
        <div className="summary-cards">
          <div className="card">
            <h4>Total Comments Analysed</h4>
            <div className="value">{summary.total_comments}</div>
          </div>
          <div className="card">
            <h4>Average Sentiment</h4>
            <div className="value">{(summary.avg_sentiment * 100).toFixed(1)} / 100</div>
          </div>
        </div>

        <div className="charts-container">
          <div className="chart-box">
            <h3>Sentiment Distribution</h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={charts.sentiment_pie}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {charts.sentiment_pie.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[entry.name.toLowerCase()] || COLORS.neutral} />
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
          <h3>Recent Processed Samples</h3>
          <div className="sample-list">
            {raw_samples.map((sample, idx) => (
              <div key={idx} className={`sample-item border-${sample.sentiment_label}`}>
                <p className="sample-text">"{sample.clean_text}"</p>
                <span className={`badge badge-${sample.sentiment_label}`}>{sample.sentiment_label} ({sample.sentiment_score.toFixed(2)})</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="logo">
          <Activity size={32} />
          <h2>AgentFlow</h2>
        </div>

        <div className="platform-nav">
          <h3 className="nav-title">Select Platform</h3>
          <button
            className={`platform-btn ${activePlatform === 'youtube' ? 'active' : ''}`}
            onClick={() => setActivePlatform('youtube')}
          >
            <Youtube /> YouTube
          </button>
          <button
            className={`platform-btn ${activePlatform === 'facebook' ? 'active' : ''}`}
            onClick={() => setActivePlatform('facebook')}
          >
            <Facebook /> Facebook
          </button>
          <button
            className={`platform-btn ${activePlatform === 'instagram' ? 'active' : ''}`}
            onClick={() => setActivePlatform('instagram')}
          >
            <Instagram /> Instagram
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <header className="main-header">
          <h1>Social Media Multi-Agent Analysis</h1>
          <p>Fetch, process, and analyze comments from specific accounts securely.</p>
        </header>

        {/* Input Form Pipeline Trigger */}
        <section className="api-section">
          <form onSubmit={handleAnalyze} className="config-form">
            <div className="form-group">
              <label>YouTube Video URL</label>
              <div className="api-input-container">
                <User className="api-icon" size={20} />
                <input
                  type="text"
                  className="api-input"
                  placeholder="e.g. https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                  value={targetAccount}
                  onChange={(e) => setTargetAccount(e.target.value)}
                />
              </div>
            </div>

            <div className="form-group">
              <label>API Key (Optional for Mock Agents)</label>
              <div className="api-input-container">
                <Key className="api-icon" size={20} />
                <input
                  type="password"
                  className="api-input"
                  placeholder={`Enter your ${activePlatform} API Key`}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
              </div>
            </div>

            {error && (
              <div className="error-message">
                <AlertCircle size={16} /> {error}
              </div>
            )}

            <button type="submit" className="connect-btn" disabled={loading}>
              {loading ? 'Processing Pipeline...' : 'Run Analysis Pipeline'}
            </button>
          </form>
        </section>

        {/* Dynamic Display Area */}
        {renderDashboard()}
      </main>
    </div>
  );
}

export default App;
