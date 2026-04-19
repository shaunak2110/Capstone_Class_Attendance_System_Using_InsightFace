import { Outlet, useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { LogOut, User, Shield } from 'lucide-react';

export default function Layout() {
  const navigate = useNavigate();

  const privilegeLevel = localStorage.getItem('privilege_level');
  const username = localStorage.getItem('username');

  const roleLabel = privilegeLevel === '1' ? 'Super Admin' : privilegeLevel === '2' ? 'Admin' : 'Faculty';
  const avatarLetter = privilegeLevel === '1' ? 'SA' : privilegeLevel === '2' ? 'A' : 'F';

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Enhanced Navbar */}
      <nav className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-10xl mx-auto px-6 py-3">
          <div className="flex items-center justify-between">
            {/* Logo and Title */}
            <img 
                src="/logo.png" 
                alt="University Logo" 
                className="h-12 w-40 object-contain"
                onError={(e) => {
                  e.target.src = "https://via.placeholder.com/120x32/4f46e5/ffffff?text=MIT+WPU";
                }}
              />
            <div className="flex items-center gap-3">
              
              <div>
                <h1 className="text-3xl font-bold text-center text-indigo-600">
                  Attendance System
                </h1>
              </div>
              <div className="bg-gradient-to-r from-indigo-600 to-purple-600 text-white p-2 rounded-xl shadow-lg">
                <Shield className="h-5 w-5" />
              </div>
            </div>

            {/* User Profile Section */}
            <div className="flex items-center gap-4">
              <div className="text-right pr-3 border-r border-slate-200">
                <div className="text-sm font-semibold text-slate-800">
                  {username || 'User'}
                </div>
                <div className="text-xs text-slate-500 capitalize font-medium flex items-center gap-1">
                  {privilegeLevel === '2' || privilegeLevel === '1' ? <Shield className="h-3 w-3" /> : <User className="h-3 w-3" />}
                  {roleLabel}
                </div>
              </div>

              <Avatar
                className="h-10 w-10 bg-gradient-to-br from-indigo-500 to-purple-600 shadow-md cursor-pointer hover:ring-2 hover:ring-indigo-400 transition-all"
                onClick={() => navigate('/profile')}
                title="View Profile"
              >
                <AvatarFallback className="text-white font-bold text-sm">{avatarLetter}</AvatarFallback>
              </Avatar>

              <Button 
                variant="outline" 
                size="sm" 
                onClick={handleLogout}
                className="hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition-colors"
              >
                <LogOut className="h-4 w-4 mr-1" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </nav>

      {/* Page Content */}
      <main className="bg-sky-40 max-w-8xl mx-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}