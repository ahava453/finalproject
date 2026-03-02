import { useState, useEffect } from 'react'
import { Youtube, Facebook, Instagram, KeyRound, Activity, AlertCircle, RefreshCw } from 'lucide-react'
import './index.css'

function App() {
    const [activePlatform, setActivePlatform] = useState('YouTube')
    const [apiKey, setApiKey] = useState('')
    const [isAnalyzing, setIsAnalyzing] = useState(false)
    const [results, setResults] = useState([])
    const [error, setError] = useState(null)

    const platforms = [
        { name: 'YouTube', icon: Youtube, color: '#FF0000' },
        { name: 'Facebook', icon: Facebook, color: '#1877F2' },
        { name: 'Instagram', icon: Instagram, color: '#E4405F' },
    ]

    // Poll for results after triggering analysis
    useEffect(() => {
        let interval;
        if (isAnalyzing) {
            interval = setInterval(() => {
                fetchResults()
            }, 3000); // Poll every 3 seconds
        }
        return () => clearInterval(interval);
    }, [isAnalyzing, activePlatform]);

    // Handle switching platforms
    const handlePlatformSwitch = (platformName) => {
        setActivePlatform(platformName);
        setResults([]);
        setError(null);
        setIsAnalyzing(false);
    }

    const fetchResults = async () => {
        try {
            const response = await fetch(`http://localhost:8000/api/results/${activePlatform.toLowerCase()}`);
            if (!response.ok) throw new Error('Failed to fetch results');
            const data = await response.json();
            setResults(data.results);
            if (data.results.length > 0) {
                setIsAnalyzing(false); // Stop polling once we have some results
            }
        } catch (err) {
            console.error(err);
        }
    }

    const handleAnalyze = async () => {
        if (!apiKey) {
            setError("API Key is required to connect to the platform.");
            return;
        }
        setError(null);
        setIsAnalyzing(true);
        setResults([]); // Clear previous results

        try {
            const response = await fetch('http://localhost:8000/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    platform: activePlatform.toLowerCase(),
                    api_key: apiKey
                })
            });

            if (!response.ok) {
                throw new Error('Failed to trigger analysis');
            }
        } catch (err) {
            setError(err.message);
            setIsAnalyzing(false);
        }
    }

    return (
        <div className="app-container">
            {/* Sidebar */}
            <aside className="sidebar">
                <div className="logo">
                    <Activity size={32} />
                    <h2>SentPulse</h2>
                </div>
                <nav className="platform-nav">
                    {platforms.map((platform) => {
                        const Icon = platform.icon
                        return (
                            <button
                                key={platform.name}
                                className={`platform-btn ${activePlatform === platform.name ? 'active' : ''}`}
                                onClick={() => handlePlatformSwitch(platform.name)}
                            >
                                <Icon color={activePlatform === platform.name ? platform.color : 'currentColor'} />
                                {platform.name}
                            </button>
                        )
                    })}
                </nav>
            </aside>

            {/* Main Content Area */}
            <main className="main-content">
                <header className="main-header">
                    <h1>{activePlatform} Sentiment Analysis</h1>
                    <p>Connect your {activePlatform} account to analyze real-time sentiment</p>
                </header>

                <section className="api-section">
                    <div className="api-input-container">
                        <KeyRound size={20} className="api-icon" />
                        <input
                            type="password"
                            placeholder={`Enter your ${activePlatform} API Key`}
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            className="api-input"
                            disabled={isAnalyzing}
                        />
                        <button
                            className="connect-btn"
                            onClick={handleAnalyze}
                            disabled={isAnalyzing}
                        >
                            {isAnalyzing ? (
                                <>
                                    <RefreshCw size={16} className="spin-icon" style={{ marginRight: '8px', animation: 'spin 1s linear infinite' }} />
                                    Analyzing...
                                </>
                            ) : 'Connect & Analyze'}
                        </button>
                    </div>
                    {error && (
                        <div className="error-message" style={{ color: '#ff6b6b', marginTop: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <AlertCircle size={16} />
                            {error}
                        </div>
                    )}
                </section>

                <section className="results-section">
                    {results.length === 0 && !isAnalyzing ? (
                        <div className="placeholder-results">
                            <h3>Monitoring will appear here</h3>
                            <p>Enter your configuration to start streaming analyzed data points directly from the social graph.</p>
                        </div>
                    ) : (
                        <div className="results-list" style={{ width: '100%', height: '100%', padding: '20px', overflowY: 'auto' }}>
                            {isAnalyzing && results.length === 0 && (
                                <div className="loading-state" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-secondary)' }}>
                                    <Activity size={48} className="pulse-icon" style={{ marginBottom: '16px', animation: 'pulse 2s infinite' }} />
                                    <p>Agents are fetching and analyzing data...</p>
                                </div>
                            )}
                            {results.map((result, idx) => (
                                <div key={idx} className={`result-card sentiment-${result.sentiment_label}`} style={{
                                    background: 'var(--sidebar-bg)',
                                    padding: '16px',
                                    borderRadius: '8px',
                                    marginBottom: '12px',
                                    borderLeft: `4px solid ${result.sentiment_label === 'positive' ? '#4CAF50' : result.sentiment_label === 'negative' ? '#F44336' : '#9E9E9E'}`
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                                        <span style={{ fontWeight: 600, textTransform: 'capitalize', color: `var(--text-primary)` }}>{result.sentiment_label} ({Math.round(result.sentiment_score * 100)}%)</span>
                                        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{new Date(result.created_at).toLocaleString()}</span>
                                    </div>
                                    <p style={{ lineHeight: 1.5 }}>{result.content_text}</p>
                                </div>
                            ))}
                        </div>
                    )}
                </section>
            </main>
        </div>
    )
}

export default App
