import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import {
  LayoutDashboard,
  GitBranch,
  Play,
  Wrench,
  BarChart3,
  Users,
  LogOut,
} from 'lucide-react';

const navItems = [
  { to: '/workflows', label: 'Workflows', icon: GitBranch },
  { to: '/dashboard', label: 'Dashboard', icon: BarChart3 },
  { to: '/tools', label: 'Tools', icon: Wrench },
  { to: '/team', label: 'Team', icon: Users },
];

export default function Layout() {
  const { user, tenant, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen flex bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-gray-200">
          <LayoutDashboard className="h-6 w-6 text-blue-600 mr-2" />
          <span className="font-semibold text-gray-900 text-sm">
            Agentic Platform
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-medium'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User section */}
        <div className="p-4 border-t border-gray-200">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-sm font-medium">
              {user?.full_name?.charAt(0) || user?.email?.charAt(0) || '?'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">
                {user?.full_name || user?.email}
              </p>
              <p className="text-xs text-gray-500 truncate">{tenant?.name}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-red-600 transition-colors w-full"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
