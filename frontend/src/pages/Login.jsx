import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { loginUser } from "@/services/api";

const ROLE_MAP = { 1: 'superadmin', 2: 'admin', 3: 'faculty' };

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const data = await loginUser(username, password);
      const role = ROLE_MAP[data.privilege_level] ?? 'faculty';

      localStorage.setItem('token', 'authenticated');
      localStorage.setItem('role', role);
      localStorage.setItem('name', data.username);

      if (data.privilege_level === 1) {
        navigate('/superadmin');
      } else if (data.privilege_level === 2) {
        navigate('/admin-dashboard');
      } else {
        navigate('/dashboard');
      }
    } catch (err) {
      const msg = err.response?.data?.detail ?? 'Invalid credentials. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative flex items-center justify-center p-4 bg-[#06080F] overflow-hidden selection:bg-purple-500/30">

      {/* Background */}
      <div
        className="absolute inset-0 bg-cover bg-center bg-no-repeat"
        style={{ backgroundImage: "url('/background.png')" }}
      />

      {/* Glow Effects */}
      <div className="absolute -top-20 -right-20 w-72 h-72 bg-purple-500/20 rounded-full blur-[50px]" />
      <div className="absolute -bottom-20 -left-20 w-72 h-72 bg-indigo-500/20 rounded-full blur-[50px]" />

      {/* Logo */}
      <div className="absolute top-4 left-4 md:top-6 md:left-6 z-10">
        <img
          src="/logo.png"
          alt="University Logo"
          className="h-12 md:h-20 w-auto object-contain drop-shadow-lg"
          onError={(e) => {
            e.target.src = 'https://via.placeholder.com/200x60/4f46e5/ffffff?text=MIT+WPU';
          }}
        />
      </div>

      {/* Login Card */}
      <Card className="w-full max-w-md relative z-10 
        bg-black/40 backdrop-blur-2xl 
        border border-white/10 
        shadow-[0_0_40px_rgba(0,0,0,0.6)] 
        rounded-2xl 
        animate-in fade-in zoom-in-95 duration-500"
      >
        {/* Inner Glow */}
        <div className="absolute -top-10 -right-10 w-40 h-40 bg-purple-500/20 rounded-full blur-[80px]" />
        <div className="absolute -bottom-10 -left-10 w-40 h-40 bg-indigo-500/20 rounded-full blur-[80px]" />

        <CardHeader className="space-y-1 pb-4 border-b border-white/10">
          <CardTitle className="text-2xl font-bold text-center text-white">
            Login Portal
          </CardTitle>
        </CardHeader>

        <form onSubmit={handleLogin}>
          <CardContent className="space-y-4 pt-6">

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
                {error}
              </div>
            )}

            {/* Username */}
            <div className="space-y-1.5">
              <Label className="text-slate-400 text-xs uppercase tracking-wider">
                Username
              </Label>
              <Input
                type="text"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="bg-white/5 border-white/10 text-white 
                placeholder:text-slate-500 
                focus-visible:ring-indigo-500 
                h-11 backdrop-blur-md"
                required
                disabled={loading}
              />
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <div className="flex justify-between">
                <Label className="text-slate-400 text-xs uppercase tracking-wider">
                  Password
                </Label>
                <span className="text-xs text-indigo-400 cursor-pointer hover:text-indigo-300">
                  Forgot?
                </span>
              </div>

              <Input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="bg-white/5 border-white/10 text-white 
                placeholder:text-slate-500 
                focus-visible:ring-indigo-500 
                h-11 backdrop-blur-md"
                required
                disabled={loading}
              />
            </div>

          </CardContent>

          <CardFooter className="flex flex-col gap-4 pt-4 pb-6">
            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 font-medium text-white 
              bg-indigo-600 hover:bg-indigo-500 
              border border-indigo-500/40 
              shadow-[0_0_20px_rgba(99,102,241,0.4)] 
              transition-all duration-300"
            >
              {loading ? "Signing in..." : "Sign In"}
            </Button>

            <p className="text-xs text-center text-slate-500">
              By signing in, you agree to the university's data policy
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}