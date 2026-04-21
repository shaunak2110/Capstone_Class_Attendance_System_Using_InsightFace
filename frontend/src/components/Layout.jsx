import { Outlet, useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { LogOut, User, Shield, Moon, Sun } from 'lucide-react';
import { useTheme } from './ThemeProvider';

export default function Layout() {
  const navigate = useNavigate();
  const { theme, setTheme } = useTheme();

  const privilegeLevel = localStorage.getItem('privilege_level');
  const username = localStorage.getItem('username');

  const roleLabel = privilegeLevel === '1' ? 'Super Admin' : privilegeLevel === '2' ? 'Admin' : 'Faculty';
  const avatarLetter = privilegeLevel === '1' ? 'SA' : privilegeLevel === '2' ? 'A' : 'F';

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#06080F] text-slate-800 dark:text-slate-200 selection:bg-purple-500/30 font-sans transition-colors duration-300">
      {/* Enhanced Navbar */}
      <nav className="bg-white/80 dark:bg-[#0f1117]/80 backdrop-blur-xl border-b border-slate-200 dark:border-white/10 shadow-lg sticky top-0 z-50">
        <div className="max-w-[120rem] mx-auto px-6 py-3">
          <div className="flex items-center justify-between">
            {/* Logo and Title */}
            <div className="flex items-center gap-4">
              <img
                src="/logo.png"
                alt="University Logo"
                className="h-15 w-40 object-contain drop-shadow-md brightness-110"
                onError={(e) => {
                  e.target.src = "https://via.placeholder.com/120x32/1e1e2e/ffffff?text=MIT+WPU";
                }}
              />
              <div className="hidden sm:flex items-center gap-3 border-l border-white/10 pl-4">
                <div className="bg-indigo-500/20 text-indigo-400 p-2 rounded-xl border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.15)] flex items-center justify-center">
                  <Shield className="h-5 w-5" />
                </div>
                <h1 className="text-2xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-teal-400 tracking-tight">
                  Attendance System
                </h1>
              </div>
            </div>

            {/* User Profile Section */}
            <div className="flex items-center gap-4">
              <div className="text-right pr-4 border-r border-slate-200 dark:border-white/10 hidden sm:block">
                <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {username || 'User'}
                </div>
                <div className="text-xs text-indigo-600 dark:text-purple-400 capitalize font-medium flex items-center justify-end gap-1.5 mt-0.5">
                  {privilegeLevel === '2' || privilegeLevel === '1' ? <Shield className="h-3 w-3" /> : <User className="h-3 w-3" />}
                  {roleLabel}
                </div>
              </div>

              <Avatar
                className="h-10 w-10 border-2 border-white/10 shadow-[0_0_15px_rgba(147,51,234,0.3)] cursor-pointer hover:border-purple-500/50 hover:scale-105 transition-all bg-gradient-to-br from-indigo-500 via-purple-500 to-teal-500"
                onClick={() => navigate('/profile')}
                title="View Profile"
              >
                <AvatarFallback className="text-white font-bold text-sm bg-black/20">{avatarLetter}</AvatarFallback>
              </Avatar>

              <div className="flex items-center gap-2 ml-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                  className="rounded-full shadow-md bg-white hover:bg-slate-100 dark:bg-white/5 dark:hover:bg-white/10 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 border border-slate-200 dark:border-white/10 transition-all duration-300 w-10 h-10"
                >
                  {theme === 'dark' ? (
                    <Sun className="h-4 w-4" />
                  ) : (
                    <Moon className="h-4 w-4" />
                  )}
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLogout}
                  className="bg-white hover:bg-red-50 dark:bg-white/5 dark:hover:bg-red-500/10 text-slate-600 hover:text-red-600 dark:text-slate-300 dark:hover:text-red-400 border-slate-200 dark:border-white/10 hover:border-red-300 dark:hover:border-red-500/30 shadow-md dark:shadow-lg backdrop-blur-md transition-all duration-300"
                >
                  <LogOut className="h-4 w-4 sm:mr-1.5" />
                  <span className="hidden sm:inline">Logout</span>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Page Content */}
      <main className="max-w-[120rem] mx-auto p-4 sm:p-6 w-full relative z-10 mt-2">
        <Outlet />
      </main>
    </div>
  );
}