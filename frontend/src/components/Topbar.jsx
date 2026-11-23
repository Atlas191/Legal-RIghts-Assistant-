import { Menu, Bell, ChevronDown } from "lucide-react";

export default function Topbar({ setMobileOpen }) {
  return (
    <header className="topbar">
      <button
        className="mobile-menu"
        onClick={() => setMobileOpen(true)}
        aria-label="Open navigation"
      >
        <Menu size={22} />
      </button>

      <div className="topbar-label">
        <span>YOUR SPACE</span>
        <h3>Legal Rights Assistant</h3>
      </div>

      <div className="topbar-actions">
        <button className="icon-button" aria-label="Notifications">
          <Bell size={19} />
        </button>

        <button className="profile-button">
          <div className="avatar">G</div>
          <span>Guest</span>
          <ChevronDown size={15} />
        </button>
      </div>
    </header>
  );
}