import { useState } from 'react';
import Assistant from './Assistant';
import Dashboard from './Dashboard';
import './App.css';

function App() {
  const [view, setView] = useState('assistant');

  return (
    <div className="app">
      <nav className="top-nav">
        <div className="brand">&gt; NetSage AI_</div>
        <div className="nav-tabs">
          <button
            className={view === 'assistant' ? 'tab active' : 'tab'}
            onClick={() => setView('assistant')}
          >
            Assistant
          </button>
          <button
            className={view === 'dashboard' ? 'tab active' : 'tab'}
            onClick={() => setView('dashboard')}
          >
            Dashboard
          </button>
        </div>
      </nav>
      {view === 'assistant' ? <Assistant /> : <Dashboard />}
    </div>
  );
}

export default App;