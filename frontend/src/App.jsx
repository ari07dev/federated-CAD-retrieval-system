import { useState, useEffect } from 'react'
import './App.css'

const API = 'http://127.0.0.1:5000'

function App() {
  // --- State ---
  const [nodes, setNodes] = useState({})
  const [searchMode, setSearchMode] = useState('text') // 'text' | 'sketch'
  const [query, setQuery] = useState('')
  const [sketchFile, setSketchFile] = useState(null)
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [searchDone, setSearchDone] = useState(false)
  const [error, setError] = useState(null)

  // Add asset
  const [addOpen, setAddOpen] = useState(false)
  const [addName, setAddName] = useState('')
  const [addDesc, setAddDesc] = useState('')
  const [addNode, setAddNode] = useState('NODE_A')
  const [addFile, setAddFile] = useState(null)
  const [adding, setAdding] = useState(false)
  const [addStatus, setAddStatus] = useState(null)

  // --- Poll node health ---
  useEffect(() => {
    const check = () => {
      fetch(`${API}/api/nodes`)
        .then(r => r.json())
        .then(setNodes)
        .catch(() => setNodes({}))
    }
    check()
    const interval = setInterval(check, 15000)
    return () => clearInterval(interval)
  }, [])

  // --- Search ---
  const handleSearch = async (e) => {
    e.preventDefault()
    setSearching(true)
    setSearchDone(false)
    setResults([])
    setError(null)

    try {
      let res
      if (searchMode === 'text') {
        res = await fetch(`${API}/api/search`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query })
        })
      } else {
        const fd = new FormData()
        fd.append('image', sketchFile)
        res = await fetch(`${API}/api/search_sketch`, {
          method: 'POST',
          body: fd
        })
      }
      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`)
      }
      const data = await res.json()
      setResults(data.results || [])
    } catch (err) {
      console.error('Search failed:', err)
      setError(err.message)
    }
    setSearching(false)
    setSearchDone(true)
  }

  // --- Add Asset ---
  const handleAdd = async (e) => {
    e.preventDefault()
    setAdding(true)
    setAddStatus(null)

    const nodeUrl = addNode === 'NODE_A'
      ? 'http://127.0.0.1:6001'
      : 'http://127.0.0.1:6002'

    const fd = new FormData()
    fd.append('name', addName)
    fd.append('description', addDesc)
    fd.append('file', addFile)

    try {
      const res = await fetch(`${nodeUrl}/add`, { method: 'POST', body: fd })
      const data = await res.json()
      if (data.status === 'success') {
        setAddStatus({ type: 'success', msg: `Asset "${addName}" added to ${addNode}` })
        setAddName('')
        setAddDesc('')
        setAddFile(null)
      } else {
        setAddStatus({ type: 'error', msg: data.error || 'Failed to add' })
      }
    } catch (err) {
      setAddStatus({ type: 'error', msg: 'Node unreachable' })
    }
    setAdding(false)
  }

  // --- Helpers ---
  const getConfidenceClass = (score) => {
    if (score >= 0.6) return 'badge-high'
    if (score >= 0.3) return 'badge-mid'
    return 'badge-low'
  }

  const downloadUrl = (r) => {
    if (r.generated === true) {
      return `${API}/api/download_generated?file=${encodeURIComponent(r.file)}`
    }
    const nodeUrl = r.node === 'NODE_A'
      ? 'http://127.0.0.1:6001'
      : 'http://127.0.0.1:6002'
    return `${nodeUrl}/download?file=${encodeURIComponent(r.file)}`
  }

  const canSearch = searchMode === 'text' ? query.trim() : sketchFile

  return (
    <>
      {/* ===== Navbar ===== */}
      <nav className="navbar">
        <div className="navbar-brand">
          <h1>FUSION-CAD</h1>
          <span>Federated CAD Retrieval Engine</span>
        </div>
        <div className="node-indicators">
          {Object.entries(nodes).map(([name, status]) => (
            <div className="node-dot" key={name}>
              <div className={`dot ${status}`} />
              {name.replace('_', ' ')}
            </div>
          ))}
        </div>
      </nav>

      <div className="main-container">
        {/* ===== Search Panel ===== */}
        <div className="search-panel">
          <h2>Search CAD Assets</h2>

          <div className="search-mode-tabs">
            <button
              className={searchMode === 'text' ? 'active' : ''}
              onClick={() => setSearchMode('text')}
            >
              Text Query
            </button>
            <button
              className={searchMode === 'sketch' ? 'active' : ''}
              onClick={() => setSearchMode('sketch')}
            >
              Sketch Upload
            </button>
          </div>

          <form onSubmit={handleSearch}>
            <div className="search-row">
              {searchMode === 'text' ? (
                <input
                  className="search-input"
                  type="text"
                  placeholder="e.g. storage vessel 0.5 KL, heat exchanger, fuel tank..."
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                />
              ) : (
                <div className="file-input-wrapper">
                  <input
                    type="file"
                    accept="image/*"
                    onChange={e => setSketchFile(e.target.files[0])}
                  />
                </div>
              )}
              <button
                className="btn-search"
                type="submit"
                disabled={!canSearch || searching}
              >
                {searching ? 'Searching...' : 'Search'}
              </button>
            </div>
          </form>
        </div>

        {/* ===== Loading ===== */}
        {searching && (
          <div className="loading">
            <div className="spinner" />
            Querying federated nodes...
          </div>
        )}

        {/* ===== Results ===== */}
        {searchDone && !searching && (
          <div className="results-section">
            <div className="results-header">
              <h3>Results</h3>
              <span className="results-count">{results.length} match{results.length !== 1 ? 'es' : ''}</span>
            </div>

            {error ? (
              <div className="error-message">
                <p>Search Error: {error}</p>
              </div>
            ) : results.length === 0 ? (
              <div className="empty-state">
                <p>No matching assets found. Try a different query.</p>
              </div>
            ) : (
              <table className="results-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Description</th>
                    <th>Source</th>
                    <th>Confidence</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, i) => (
                    <tr key={i}>
                      <td className="result-name">{r.name}</td>
                      <td className="result-desc" title={r.description}>{r.description}</td>
                      <td>
                        {r.generated === true ? (
                          <span className="badge badge-generated">AI Generated</span>
                        ) : (
                          <span className="result-node">{r.node}</span>
                        )}
                      </td>
                      <td>
                        <span className={`badge ${getConfidenceClass(r.score)}`}>
                          {(r.score * 100).toFixed(1)}%
                        </span>
                      </td>
                      <td>
                        <a
                          className="btn-download"
                          href={downloadUrl(r)}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Download
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* ===== Add Asset ===== */}
        <div className="add-panel">
          <div className="section-toggle" onClick={() => setAddOpen(!addOpen)}>
            <h2>Add New Asset</h2>
            <span className={`chevron ${addOpen ? 'open' : ''}`}>▼</span>
          </div>

          {addOpen && (
            <>
              {addStatus && (
                <div className={`status-bar ${addStatus.type}`} style={{ marginTop: 16 }}>
                  {addStatus.msg}
                </div>
              )}

              <form className="add-form" onSubmit={handleAdd} style={{ marginTop: 16 }}>
                <div className="form-group">
                  <label>Asset Name *</label>
                  <input
                    type="text"
                    placeholder="e.g. Fuel Tank 500L"
                    value={addName}
                    onChange={e => setAddName(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label>Target Node</label>
                  <select value={addNode} onChange={e => setAddNode(e.target.value)}>
                    <option value="NODE_A">NODE A (Port 6001)</option>
                    <option value="NODE_B">NODE B (Port 6002)</option>
                  </select>
                </div>

                <div className="form-group full-width">
                  <label>Description</label>
                  <input
                    type="text"
                    placeholder="Detailed description for AI search indexing"
                    value={addDesc}
                    onChange={e => setAddDesc(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label>CAD File (PDF) *</label>
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={e => setAddFile(e.target.files[0])}
                    required
                  />
                </div>

                <div className="form-group" style={{ display: 'flex', alignItems: 'flex-end' }}>
                  <button
                    className="btn-add"
                    type="submit"
                    disabled={!addName || !addFile || adding}
                  >
                    {adding ? 'Adding...' : 'Add Asset'}
                  </button>
                </div>
              </form>
            </>
          )}
        </div>
      </div>
    </>
  )
}

export default App
