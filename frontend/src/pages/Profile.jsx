import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { ArrowLeft, User, Mail, Building2, BookOpen, Shield, BadgeCheck } from 'lucide-react';
import { getUserProfile } from "@/services/api";

const ROLE_MAP = {
  '1': { label: 'Super Admin', color: 'bg-purple-500/20 text-purple-400 border-purple-500/30', icon: Shield },
  '2': { label: 'Admin', color: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30', icon: BadgeCheck },
  '3': { label: 'Faculty', color: 'bg-sky-500/20 text-sky-400 border-sky-500/30', icon: User },
};

function InfoRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-4 p-4 rounded-xl bg-black/20 border border-white/5 hover:bg-white/5 transition-colors">
      <div className="bg-indigo-500/20 p-2.5 rounded-lg border border-indigo-500/20 shadow-[0_0_10px_rgba(99,102,241,0.1)]">
        <Icon className="h-4 w-4 text-indigo-400" />
      </div>
      <div>
        <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">{label}</p>
        <p className="text-sm font-semibold text-slate-200 mt-1">{value || '—'}</p>
      </div>
    </div>
  );
}

export default function Profile() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const privilegeLevel = localStorage.getItem('privilege_level');
  const roleInfo = ROLE_MAP[privilegeLevel] || ROLE_MAP['3'];
  const RoleIcon = roleInfo.icon;

  useEffect(() => {
    getUserProfile()
      .then(setProfile)
      .catch((err) => {
        setError(err?.response?.data?.detail || 'Could not load profile. Please try again.');
      })
      .finally(() => setLoading(false));
  }, []);
  const initials = profile?.name
    ? profile.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
    : roleInfo.label[0];

  const handleBack = () => {
    if (privilegeLevel === '1') return navigate('/superadmin');
    if (privilegeLevel === '2') return navigate('/admin-dashboard');
    return navigate('/dashboard');
  };

  return (
    <div className="relative min-h-[calc(100vh-2rem)] bg-[#0f1117] text-slate-200 p-4 sm:p-8 rounded-xl overflow-hidden font-sans shadow-2xl selection:bg-purple-500/30">
      {/* Background Effects */}
      <div className="absolute top-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-blue-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] left-[-10%] w-[30%] h-[40%] rounded-full bg-indigo-600/10 blur-[120px] pointer-events-none" />

      <div className="relative space-y-6 animate-in fade-in duration-700 z-10 w-full px-4 sm:px-6 lg:px-10">        {/* Header */}
        <div className="flex items-center justify-between pb-6 border-b border-white/10">
          <h2 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400">
            My Profile
          </h2>
          <Button variant="outline" onClick={handleBack} className="bg-white/5 hover:bg-white/10 text-white border-white/10 shadow-lg backdrop-blur-md transition-all duration-300">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back
          </Button>
        </div>

        {loading && (
          <Card className="bg-white/5 border-white/10 backdrop-blur-xl shadow-xl">
            <CardContent className="p-10 text-center text-slate-400">Loading profile…</CardContent>
          </Card>
        )}

        {error && (
          <Card className="bg-red-500/5 border-red-500/20 backdrop-blur-xl shadow-xl">
            <CardContent className="p-6">
              <p className="text-red-400 text-sm font-medium">{error}</p>
              <p className="text-slate-400 text-xs mt-1">Your partner's backend endpoint <code className="bg-black/30 px-1 rounded">GET /user/profile</code> may not be live yet.</p>
            </CardContent>
          </Card>
        )}

        {!loading && profile && (
          <>
            {/* Identity Card */}
            <Card className="bg-white/5 border-white/10 backdrop-blur-xl shadow-xl overflow-hidden">
              <div className="h-32 bg-gradient-to-r from-blue-600/40 via-indigo-600/40 to-purple-600/40 relative">
                <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-20" />
              </div>
              <CardContent className="px-6 pb-6 -mt-12 relative z-10">
                <div className="flex flex-col sm:flex-row items-start sm:items-end gap-4">
                  <Avatar className="h-28 w-28 border-4 border-[#0f1117] shadow-xl bg-gradient-to-br from-indigo-500 to-purple-600">
                    <AvatarFallback className="text-white text-3xl font-bold">{initials}</AvatarFallback>
                  </Avatar>
                  <div className="flex-1 pb-1">
                    <h3 className="text-2xl font-bold text-white">{profile.name}</h3>
                    <p className="text-slate-400 text-sm mt-1">@{profile.username}</p>
                    <span className={`inline-flex items-center gap-1.5 mt-3 px-3 py-1 text-xs font-semibold rounded-full border ${roleInfo.color}`}>
                      <RoleIcon className="h-3 w-3" /> {roleInfo.label}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Details Card */}
            <Card className="bg-white/5 border-white/10 backdrop-blur-xl shadow-xl mt-6">
              <CardHeader className="border-b border-white/5 pb-4">
                <CardTitle className="text-lg text-white font-semibold">Account Details</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pt-6">                <InfoRow icon={User} label="Full Name" value={profile.name} />
                <InfoRow icon={Mail} label="Email" value={profile.email_id} />
                <InfoRow icon={Building2} label="School" value={profile.school} />
                <InfoRow icon={BookOpen} label="Department" value={profile.department} />
                <InfoRow icon={BadgeCheck} label="User ID" value={String(profile.user_id)} />
                <InfoRow icon={Shield} label="Role" value={roleInfo.label} />
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
