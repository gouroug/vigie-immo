export default function LoadingOverlay({ visible }) {
  if (!visible) return null;

  return (
    <div className="loading-overlay">
      <div className="loading">
        <div className="spinner" />
        <p>Analyse en cours...</p>
      </div>
    </div>
  );
}
