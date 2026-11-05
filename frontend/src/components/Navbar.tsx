import { Train, LogOut, User } from 'lucide-react';
import { getStoredUser, logout } from '../api';
import './Navbar.css';

interface Props {
  onLogout: () => void;
}

export default function Navbar({ onLogout }: Props) {
  const { username } = getStoredUser();

  const handleLogout = () => {
    logout();
    onLogout();
  };

  return (
    <nav className="navbar">
      <div className="nav-inner">
        <div className="nav-brand">
          <div className="nav-logo">
            <Train size={20} strokeWidth={2.5} />
          </div>
          <span className="nav-title">
            Rail<span className="nav-highlight">wise</span>
          </span>
        </div>

        <div className="nav-actions">
          <div className="nav-user">
            <User size={14} />
            <span>{username || 'Guest User'}</span>
          </div>
          <button className="nav-logout" onClick={handleLogout} title="Sign Out">
            <LogOut size={16} />
            <span>Sign Out</span>
          </button>
        </div>
      </div>
    </nav>
  );
}
