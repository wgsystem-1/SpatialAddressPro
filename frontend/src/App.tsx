import { useState } from 'react'
import axios from 'axios'
import './App.css'

// Type definition for API response
interface AddressResponse {
  id: number
  raw_text: string
  refined_text: string
  road_addr: string
  jibun_addr?: string // Added
  zip_no: string
  si_nm?: string
  sgg_nm?: string
  buld_nm?: string
  status: string
  is_ai_corrected?: boolean
  error_message?: string
  created_at: string
}

// Type definition for search candidate
interface AddressCandidate {
  id: number
  road_address: string
  jibun_address: string
  building_name: string
  zip_code: string
  si_nm: string
  sgg_nm: string
  emd_nm: string
}

function App() {
  const [inputText, setInputText] = useState('')
  const [result, setResult] = useState<AddressResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // New: Candidates for building name search
  const [candidates, setCandidates] = useState<AddressCandidate[]>([])
  const [showCandidates, setShowCandidates] = useState(false)

  const [bulkData, setBulkData] = useState<{
    count: number;
    results: any[];
    csv_content: string;
    filename: string;
  } | null>(null)

  // Bulk processing state
  const [bulkProcessing, setBulkProcessing] = useState(false)
  const [bulkProgress, setBulkProgress] = useState({ current: 0, total: 0, percent: 0 })
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)

  // Search for candidates (building name search)
  const handleSearch = async () => {
    if (!inputText.trim()) return

    setLoading(true)
    setError('')
    setCandidates([])
    setResult(null)
    setBulkData(null)

    try {
      const response = await axios.get('/api/v1/address/search', {
        params: { query: inputText, limit: 10 }
      })

      if (response.data.candidates && response.data.candidates.length > 0) {
        setCandidates(response.data.candidates)
        setShowCandidates(true)
      } else {
        // No candidates found, try normalize
        handleNormalize()
      }
    } catch (err) {
      console.error(err)
      // Fallback to normalize
      handleNormalize()
    } finally {
      setLoading(false)
    }
  }

  // Select a candidate from the list
  const handleSelectCandidate = (candidate: AddressCandidate) => {
    setResult({
      id: candidate.id,
      raw_text: inputText,
      refined_text: candidate.road_address,
      road_addr: candidate.road_address,
      jibun_addr: candidate.jibun_address,
      zip_no: candidate.zip_code,
      si_nm: candidate.si_nm,
      sgg_nm: candidate.sgg_nm,
      buld_nm: candidate.building_name,
      status: 'success',
      is_ai_corrected: false,
      created_at: new Date().toISOString()
    })
    setCandidates([])
    setShowCandidates(false)
  }

  const handleNormalize = async () => {
    if (!inputText.trim()) return

    setLoading(true)
    setError('')
    setResult(null)
    setBulkData(null)
    setCandidates([])
    setShowCandidates(false)

    try {
      const response = await axios.post<AddressResponse>('/api/v1/address/normalize', {
        raw_text: inputText
      })
      setResult(response.data)
    } catch (err) {
      console.error(err)
      setError('Failed to normalize address. (정제 실패)')
    } finally {
      setLoading(false)
    }
  }

  const handleBulkUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setLoading(true)
    setBulkProcessing(true)
    setError('')
    setBulkData(null)
    setResult(null)
    setBulkProgress({ current: 0, total: 0, percent: 0 })

    const formData = new FormData()
    formData.append('file', file)

    try {
      // 1. Start job
      const response = await axios.post('/api/v1/address/bulk-normalize', formData)
      const jobId = response.data.job_id
      setCurrentJobId(jobId)

      // 2. Poll for status
      const poll = setInterval(async () => {
        try {
          const statusRes = await axios.get(`/api/v1/address/bulk-status/${jobId}`)
          const statusData = statusRes.data

          setBulkProgress({
            current: statusData.current_row,
            total: statusData.total_rows,
            percent: statusData.progress_percent
          })

          if (!statusData.is_running) {
            clearInterval(poll)
            setBulkProcessing(false)
            setLoading(false)

            if (statusData.is_cancelled) {
              setError('처리가 사용자에 의해 중단되었습니다.')
            } else if (statusData.results_data) {
              setBulkData(statusData.results_data)
              alert(`처리 완료! ${statusData.results_data.count}건 정규화됨.`)
            }
          }
        } catch (err) {
          console.error('Polling error:', err)
          clearInterval(poll)
          setBulkProcessing(false)
          setLoading(false)
        }
      }, 800)

    } catch (err: any) {
      console.error(err)
      const errMsg = err.response?.data?.detail || 'Bulk processing failed.'
      setError(errMsg)
      setBulkProcessing(false)
      setLoading(false)
    } finally {
      event.target.value = ''
    }
  }

  const handleCancelBulk = async () => {
    if (!currentJobId) return
    try {
      const res = await axios.post(`/api/v1/address/bulk-cancel/${currentJobId}`)
      if (res.data.success) {
        // Status will be updated via polling
      }
    } catch (err) {
      console.error('Cancel failed:', err)
    }
  }

  const downloadCsv = () => {
    if (!bulkData) return;

    // Convert string to blob with UTF-8-BOM for Excel
    const bom = new Uint8Array([0xEF, 0xBB, 0xBF]); // UTF-8 BOM
    const blob = new Blob([bom, bulkData.csv_content], { type: 'text/csv;charset=utf-8' })

    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', bulkData.filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  return (
    <div className="container">
      <header className="app-header">
        <div className="brand">
          <img src="/logo_new.png" alt="Spatial Address Pro" className="app-logo-full" />
        </div>
      </header>

      <div className="card">
        <h3>Single Address (개별 주소)</h3>
        <div className="input-row">
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="주소 또는 건물명 입력 (예: 우림라이온스밸리)"
            rows={1}
            className="address-input compact"
          />
          <button onClick={handleSearch} disabled={loading} className="normalize-btn" style={{ backgroundColor: '#6366f1' }}>
            {loading ? '...' : '🔍 Search'}
          </button>
          <button onClick={handleNormalize} disabled={loading} className="normalize-btn">
            {loading ? '...' : 'Normalize'}
          </button>
        </div>

        {/* Candidate List */}
        {showCandidates && candidates.length > 0 && (
          <div className="candidates-list">
            <h4>검색 결과 ({candidates.length}건) - 클릭하여 선택</h4>
            <div className="candidates-grid">
              {candidates.map((c) => (
                <div
                  key={c.id}
                  className="candidate-item"
                  onClick={() => handleSelectCandidate(c)}
                >
                  <div className="candidate-main">{c.road_address}</div>
                  <div className="candidate-sub">
                    {c.building_name && <span className="building-name">{c.building_name}</span>}
                    <span className="zip-code">[{c.zip_code}]</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="card" style={{ marginTop: '1rem' }}>
        <h3>Bulk Upload (대량 처리 - CSV, 최대 1,000건)</h3>
        <div className="input-row">
          <div className="address-input compact" style={{ color: '#888', display: 'flex', alignItems: 'center', flexDirection: 'column', gap: '0.5rem' }}>
            {bulkProcessing ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', fontSize: '0.8rem' }}>
                  <span>⏳ 정규화 진행 중...</span>
                  <span>{bulkProgress.current} / {bulkProgress.total}건 ({bulkProgress.percent}%)</span>
                </div>
                <div style={{ width: '100%', backgroundColor: '#333', borderRadius: '4px', height: '10px', overflow: 'hidden' }}>
                  <div
                    style={{
                      width: `${bulkProgress.percent}%`,
                      backgroundColor: '#6366f1',
                      height: '100%',
                      transition: 'width 0.3s ease-out'
                    }}
                  />
                </div>
              </>
            ) : (
              bulkData ? `✅ ${bulkData.count}건 처리 완료` : "Upload a CSV file with an 'address' column."
            )}
          </div>

          {bulkProcessing ? (
            <button onClick={handleCancelBulk} className="normalize-btn" style={{ backgroundColor: '#ef4444' }}>
              중단
            </button>
          ) : !bulkData ? (
            <label className="normalize-btn" style={{ cursor: 'pointer', margin: 0 }}>
              Select CSV
              <input
                type="file"
                accept=".csv"
                onChange={handleBulkUpload}
                disabled={loading}
                style={{ display: 'none' }}
              />
            </label>
          ) : (
            <button onClick={downloadCsv} className="normalize-btn" style={{ backgroundColor: '#10b981' }}>
              Download Result
            </button>
          )}
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {/* Bulk Results Grid (Only if <= 100 rows) */}
      {bulkData && bulkData.count <= 100 && (
        <div className="result-card" style={{ maxWidth: '100%', overflowX: 'auto' }}>
          <h3>Preview Results (미리보기 - {bulkData.count}건)</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Original</th>
                <th>Refined</th>
                <th>Road Addr</th>
                <th>Status</th>
                <th>Info</th>
              </tr>
            </thead>
            <tbody>
              {bulkData.results.map((row, idx) => (
                <tr key={idx}>
                  {/* Adjust keys based on your actual CSV columns or backend logic */}
                  <td>{row.raw_text || row.address || row.addr || row.주소 || Object.values(row)[0] as string}</td>
                  <td>{row.refined_address}</td>
                  <td>{row.road_address}</td>
                  <td>
                    <span className={row.status === 'success' ? 'status-success' : 'status-fail'}>
                      {row.status}
                    </span>
                  </td>
                  <td>
                    {row.si_nm} {row.sgg_nm} {row.buld_nm}
                    {row.error_info && <span className="error-msg"> {row.error_info}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {result && (
        <div className="result-card">
          <h2>Result (결과)</h2>
          <div className="result-grid">
            <div className="label">Refined:</div>
            <div className="value">{result.refined_text || '-'}</div>

            <div className="label">Road Addr:</div>
            <div className="value">{result.road_addr || '-'}</div>

            <div className="label">Jibun Addr:</div>
            <div className="value">{result.jibun_addr || '-'}</div>

            <div className="label">Zip Code:</div>
            <div className="value">{result.zip_no || '-'}</div>

            <div className="label">City/Gu:</div>
            <div className="value">{result.si_nm} {result.sgg_nm}</div>

            <div className="label">Building:</div>
            <div className="value">{result.buld_nm || '-'}</div>

            <div className="label">Status:</div>
            <div className={`value status-${result.status}`}>
              {result.status}
              {result.is_ai_corrected && <span className="badge-ai">AI Fixed</span>}
            </div>

            {result.error_message && (
              <>
                <div className="label">Error:</div>
                <div className="value error-msg">{result.error_message}</div>
              </>
            )}
          </div>
        </div>
      )}
      <footer className="app-footer">
        <span className="powered-by">Powered by</span>
        <div className="logo-box">
          <img src="/wgsura_logo.png" alt="Woori Gangsan System" className="company-logo" />
        </div>
      </footer>
    </div>
  )
}

export default App
