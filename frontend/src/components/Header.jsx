import UserMenu from './UserMenu';

export default function Header() {
  return (
    <div className="header">
      <div className="header-main">
        <h1>🏠 Rapport de Risque Immobilier - Québec</h1>
        <UserMenu />
      </div>
      <p className="subtitle">
        Analyse complète des risques et services pour courtiers d'assurance -
        Province de Québec
      </p>
    </div>
  );
}
