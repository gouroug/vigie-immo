import { useState, useRef } from 'react';
import './App.css';
import { analyzeAddress } from './api/analyze';
import Header from './components/Header';
import SearchForm from './components/SearchForm';
import LoadingOverlay from './components/LoadingOverlay';
import ErrorMessage from './components/ErrorMessage';
import ResultsPanel from './components/ResultsPanel';

export default function App() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const resultsRef = useRef(null);

  async function handleSearch(address) {
    setError(null);
    setLoading(true);

    try {
      const result = await analyzeAddress(address);
      setData(result);

      // Scroll to results after render
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'start',
        });
      }, 100);
    } catch (err) {
      setError(`Erreur: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <LoadingOverlay visible={loading} />
      <div className="container">
        <Header />
        <ErrorMessage message={error} />
        <SearchForm onSubmit={handleSearch} loading={loading} />
        {data && (
          <div ref={resultsRef}>
            <ResultsPanel data={data} />
          </div>
        )}
      </div>
    </>
  );
}
