import { NavLink } from "react-router-dom";
import {
  House,
  MessageCircle,
  BookOpen,
  HandHelping,
  FolderOpen,
  Info,
  Scale,
  X,
} from "lucide-react";

const navItems = [
  { label: "Home", path: "/", icon: House },
  { label: "Legal Assistant", path: "/assistant", icon: MessageCircle },
  { label: "Know Your Rights", path: "/rights", icon: BookOpen },
  { label: "Get Help", path: "/get-help", icon: HandHelping },
  { label: "My Documents", path: "/documents", icon: FolderOpen },
  { label: "About", path: "/about", icon: Info },
];

export default function Sidebar({ mobileOpen, setMobileOpen }) {
  return (
    <>
      {mobileOpen && (
        <div className="sidebar-overlay" onClick={() => setMobileOpen(false)} />
      )}

      <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-icon">
            <Scale size={23} />
          </div>
          <div>
            <h2>HerRights</h2>
            <span>Legal support, simplified</span>
          </div>
          <button
            className="mobile-close"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
          >
            <X size={21} />
          </button>
        </div>

        <div className="nav-section-label">MENU</div>

        <nav className="sidebar-nav">
          {navItems.map(({ label, path, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/"}
              className={({ isActive }) =>
                `nav-link ${isActive ? "active" : ""}`
              }
              onClick={() => setMobileOpen(false)}
            >
              <Icon size={19} strokeWidth={1.8} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="support-card">
            <div className="support-icon">
              <HandHelping size={20} />
            </div>
            <h3>Need immediate help?</h3>
            <p>Find emergency helplines and legal support.</p>
            <NavLink to="/get-help" onClick={() => setMobileOpen(false)}>
              Get support →
            </NavLink>
          </div>

          <p className="sidebar-footer">Made for awareness. Built for empowerment.</p>
        </div>
      </aside>
    </>
  );
}