import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { ArrowLeft, User, Mail, Building2, BookOpen, Shield, BadgeCheck } from 'lucide-react';
import { getUserProfile } from "@/services/api";

const ROLE_MAP = {
  '1': { label: 'Super Admin', color: 'bg-purple-100 text-purple-700 border-purple-200', icon: Shield },
  '2': { label: 'Admin',       color: 'bg-indigo-100 text-indigo-700 border-indigo-200',  icon: BadgeCheck },
  '3': { label: 'Faculty',     color: 'bg-sky-100 text-sky-700 border-sky-200',           icon: User },
};

function InfoRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-4 p-4 rounded-xl bg-slate-50 border border-slate-100">
      <div className="bg-white p-2 rounded-lg shadow-sm border border-slate-200">
        <Icon className="h-4 w-4 text-indigo-600" />
      </div>
      <div>
        <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">{label}</p>
        <p className="text-sm font-semibold text-slate-800 mt-0.5">{value || '—'}</p>
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
    <div className="max-w-2xl mx-auto space-y-6 pb-10 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold text-slate-800">My Profile</h2>
        <Button variant="outline" onClick={handleBack}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
      </div>

      {loading && (
        <Card className="border-0 shadow-xl">
          <CardContent className="p-10 text-center text-slate-500">Loading profile…</CardContent>
        </Card>
      )}

      {error && (
        <Card className="border-0 shadow-xl border-red-100">
          <CardContent className="p-6">
            <p className="text-red-600 text-sm font-medium">{error}</p>
            <p className="text-slate-400 text-xs mt-1">Your partner's backend endpoint <code className="bg-slate-100 px-1 rounded">GET /user/profile</code> may not be live yet.</p>
          </CardContent>
        </Card>
      )}

      {!loading && profile && (
        <>
          {/* Identity Card */}
          <Card className="border-0 shadow-xl overflow-hidden">
            <div className="h-24 bg-gradient-to-r from-indigo-600 via-purple-600 to-sky-500" />
            <CardContent className="px-6 pb-6 -mt-12">
              <div className="flex flex-col sm:flex-row items-start sm:items-end gap-4">
                <Avatar className="h-24 w-24 border-4 border-white shadow-lg bg-gradient-to-br from-indigo-500 to-purple-600">
                  <AvatarFallback className="text-white text-2xl font-bold">{initials}</AvatarFallback>
                </Avatar>
                <div className="flex-1 pb-1">
                  <h3 className="text-2xl font-bold text-slate-800">{profile.name}</h3>
                  <p className="text-slate-500 text-sm">@{profile.username}</p>
                  <span className={`inline-flex items-center gap-1.5 mt-2 px-3 py-1 text-xs font-semibold rounded-full border ${roleInfo.color}`}>
                    <RoleIcon className="h-3 w-3" /> {roleInfo.label}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Details Card */}
          <Card className="border-0 shadow-xl">
            <CardHeader>
              <CardTitle className="text-base text-slate-700">Account Details</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <InfoRow icon={User}      label="Full Name"    value={profile.name} />
              <InfoRow icon={Mail}      label="Email"        value={profile.email_id} />
              <InfoRow icon={Building2} label="School"       value={profile.school} />
              <InfoRow icon={BookOpen}  label="Department"   value={profile.department} />
              <InfoRow icon={BadgeCheck}label="User ID"      value={String(profile.user_id)} />
              <InfoRow icon={Shield}    label="Role"         value={roleInfo.label} />
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
