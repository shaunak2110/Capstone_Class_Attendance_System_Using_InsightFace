import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Users, ShieldCheck, Plus, BookOpen, Activity, Shield, UserCog, Mail, Building, Landmark, Phone, Crown } from 'lucide-react';
import { getUsers, createAdmin, createTeacher } from '@/services/api';

export default function SuperadminDashboard() {
  const navigate = useNavigate();
  const userName = localStorage.getItem('username') || 'Superadmin';
  const [activeTab, setActiveTab] = useState('admin');

  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [form, setForm] = useState({
    username: '', password: '', name: '', email_id: '', school: '', department: ''
  });
  const [creating, setCreating] = useState(false);

  const [teacherForm, setTeacherForm] = useState({
    username: '', password: '', name: '', email_id: '', school: '', department: '', mob: ''
  });
  const [creatingTeacher, setCreatingTeacher] = useState(false);

  useEffect(() => {
    getUsers()
      .then(setUsers)
      .catch(() => setError('Failed to load users.'))
      .finally(() => setUsersLoading(false));
  }, []);

  const handleChange = (e) => setForm(f => ({ ...f, [e.target.name]: e.target.value }));

  const handleCreateAdmin = async (e) => {
    e.preventDefault();
    setCreating(true);
    setError('');
    setSuccess('');
    try {
      await createAdmin(form);
      setSuccess(`Admin "${form.name}" created successfully.`);
      setForm({ username: '', password: '', name: '', email_id: '', school: '', department: '' });
      const updated = await getUsers();
      setUsers(updated);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to create admin.');
    } finally {
      setCreating(false);
    }
  };

  const handleTeacherChange = (e) => setTeacherForm(f => ({ ...f, [e.target.name]: e.target.value }));

  const handleCreateTeacher = async (e) => {
    e.preventDefault();
    setCreatingTeacher(true);
    setError('');
    setSuccess('');
    try {
      await createTeacher(teacherForm);
      setSuccess(`Faculty "${teacherForm.name}" created successfully.`);
      setTeacherForm({ username: '', password: '', name: '', email_id: '', school: '', department: '', mob: '' });
      const updated = await getUsers();
      setUsers(updated);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to create faculty.');
    } finally {
      setCreatingTeacher(false);
    }
  };

  const privilegeLabel = (level) => {
    if (level === 1) return <span className="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider bg-rose-500/10 text-rose-400 border border-rose-500/20">Superadmin</span>;
    if (level === 2) return <span className="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider bg-violet-500/10 text-violet-400 border border-violet-500/20">Admin</span>;
    return <span className="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Teacher</span>;
  };

  // Stats computation
  const totalUsers = users.length;
  const totalAdmins = users.filter(u => u.privilege_level === 2).length;
  const totalFaculty = users.filter(u => u.privilege_level === 3).length;

  return (
    <div className="relative min-h-[calc(100vh-2rem)] bg-slate-50 dark:bg-[#0f1117] text-slate-800 dark:text-slate-200 p-4 sm:p-8 rounded-xl overflow-hidden font-sans shadow-2xl selection:bg-indigo-500/30">
      {/* Background Effects */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-indigo-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-violet-600/10 blur-[120px] pointer-events-none" />

      <div className="relative space-y-8 animate-in fade-in duration-700 z-10 w-full max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-slate-300 dark:border-white/10">
          <div>
            <h2 className="text-4xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-violet-400 to-purple-400 mb-2">
              Superadmin Hub
            </h2>
            <p className="text-slate-600 dark:text-slate-400 text-lg">
              Welcome back, <span className="font-semibold text-indigo-300">{userName}</span>
            </p>
          </div>
          <div className="flex gap-3">
            <Button
              onClick={() => navigate('/admin-records')}
              className="bg-white dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-slate-900 dark:text-white border border-slate-300 dark:border-white/10 shadow-lg backdrop-blur-md transition-all duration-300"
            >
              <BookOpen className="mr-2 h-4 w-4 text-indigo-400" /> View Attendance Records
            </Button>
          </div>
        </div>

        {error && (
          <Alert variant="destructive" className="bg-red-500/10 border border-red-500/20 text-red-400">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {success && (
          <Alert className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <AlertDescription>{success}</AlertDescription>
          </Alert>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {[
            { title: "Total Users", value: totalUsers, icon: Users, color: "text-blue-400", bg: "bg-blue-400/10" },
            { title: "Super Admin", value: totalUsers - totalAdmins - totalFaculty, icon: Crown, color: "text-teal-400", bg: "bg-teal-400/10" },
            { title: "Admin", value: totalAdmins, icon: ShieldCheck, color: "text-violet-400", bg: "bg-violet-400/10" },
            { title: "Faculty", value: totalFaculty, icon: UserCog, color: "text-emerald-400", bg: "bg-emerald-400/10" }
          ].map((stat, i) => (
            <Card key={i} className="bg-white dark:bg-white/5 border-slate-300 dark:border-white/10 backdrop-blur-xl shadow-xl hover:bg-slate-200 dark:hover:bg-white/10 transition-all duration-300">
              <CardContent className="p-6 flex items-center gap-4">
                <div className={`p-4 rounded-xl ${stat.bg}`}>
                  <stat.icon className={`h-8 w-8 ${stat.color}`} />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-600 dark:text-slate-400 uppercase tracking-wider">{stat.title}</p>
                  <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">{usersLoading ? '-' : stat.value}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid gap-8 lg:grid-cols-7 items-start">
          {/* User List */}
          <Card className="lg:col-span-4 bg-white dark:bg-white/5 border-slate-300 dark:border-white/10 backdrop-blur-xl shadow-xl overflow-hidden flex flex-col h-[600px]">
            <CardHeader className="bg-white dark:bg-black/20 border-b border-slate-200 dark:border-white/5 pb-4">
              <CardTitle className="flex items-center gap-2 text-xl text-slate-900 dark:text-white">
                <Activity className="h-5 w-5 text-indigo-400" />
                System Roster
              </CardTitle>
              <CardDescription className="text-slate-600 dark:text-slate-400">Manage and view all registered users across the platform.</CardDescription>
            </CardHeader>
            <CardContent className="p-0 flex-1 overflow-auto">
              <div className="p-4">
                {usersLoading ? (
                  <div className="flex justify-center items-center h-40">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
                  </div>
                ) : users.length === 0 ? (
                  <div className="flex flex-col items-center justify-center p-12 text-slate-500 text-center">
                    <Users className="h-12 w-12 mb-4 opacity-20" />
                    <p>No users active.</p>
                  </div>
                ) : (
                  <div className="rounded-lg border border-slate-300 dark:border-white/10 overflow-hidden">
                    <Table>
                      <TableHeader className="bg-slate-50 dark:bg-black/40">
                        <TableRow className="border-slate-300 dark:border-white/10 hover:bg-transparent">
                          <TableHead className="text-slate-600 dark:text-slate-400">User Details</TableHead>
                          <TableHead className="text-slate-600 dark:text-slate-400">Department</TableHead>
                          <TableHead className="text-slate-600 dark:text-slate-400">School</TableHead>
                          <TableHead className="text-slate-600 dark:text-slate-400">Role</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {users.map((u) => (
                          <TableRow key={u.user_id} className="border-slate-200 dark:border-white/5 hover:bg-slate-100 dark:hover:bg-white/5 transition-colors">
                            <TableCell>
                              <div className="font-semibold text-slate-800 dark:text-slate-200">{u.name}</div>
                              <div className="text-slate-500 text-xs mt-0.5">{u.username}</div>
                            </TableCell>
                            <TableCell className="text-slate-600 dark:text-slate-400">{u.department}</TableCell>
                            <TableCell className="text-slate-700 dark:text-slate-300">{u.school}</TableCell>
                            <TableCell>
                              {privilegeLabel(u.privilege_level)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Creation Forms */}
          <div className="lg:col-span-3 space-y-6">
            <div className="flex p-1 bg-slate-50 dark:bg-black/40 rounded-xl border border-slate-300 dark:border-white/10 w-full backdrop-blur-md">
              <button
                className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-semibold rounded-lg transition-all duration-300 ${activeTab === 'admin' ? 'bg-gradient-to-r from-indigo-500 to-violet-600 text-slate-900 dark:text-white shadow-lg shadow-indigo-500/25' : 'text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5'}`}
                onClick={() => setActiveTab('admin')}
              >
                <Shield className="h-4 w-4" /> New Admin
              </button>
              <button
                className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-semibold rounded-lg transition-all duration-300 ${activeTab === 'faculty' ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-slate-900 dark:text-white shadow-lg shadow-emerald-500/25' : 'text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5'}`}
                onClick={() => setActiveTab('faculty')}
              >
                <UserCog className="h-4 w-4" /> New Faculty
              </button>
            </div>

            <div className="relative">
              {activeTab === 'admin' && (
                <div className="animate-in fade-in slide-in-from-right-4 duration-500">
                  <Card className="bg-white dark:bg-white/5 border-slate-300 dark:border-white/10 backdrop-blur-xl shadow-2xl relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-[50px] pointer-events-none" />
                    <CardHeader>
                      <CardTitle className="text-slate-900 dark:text-white text-xl">Register Admin</CardTitle>
                      <CardDescription className="text-slate-600 dark:text-slate-400">Grant administrative access securely.</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <form onSubmit={handleCreateAdmin} className="space-y-4" autoComplete="off">
                        {/* Fake inputs to thwart browser autofill */}
                        <input type="text" name="fakeusernameremembered" style={{ display: 'none' }} />
                        <input type="password" name="fakepasswordremembered" style={{ display: 'none' }} />

                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-1.5 col-span-2 sm:col-span-1">
                            <Label htmlFor="admin-name" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Full Name</Label>
                            <Input id="admin-name" name="name" type="text" value={form.name} onChange={handleChange} required autoComplete="new-password"
                              className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-indigo-500 placeholder:text-slate-400 dark:placeholder:text-slate-600" placeholder="John Doe" />
                          </div>
                          <div className="space-y-1.5 col-span-2 sm:col-span-1">
                            <Label htmlFor="admin-username" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Username</Label>
                            <Input id="admin-username" name="username" type="text" value={form.username} onChange={handleChange} required autoComplete="new-password"
                              className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-indigo-500 placeholder:text-slate-400 dark:placeholder:text-slate-600" placeholder="johndoe" />
                          </div>
                        </div>

                        <div className="space-y-1.5">
                          <Label htmlFor="admin-email" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider flex items-center gap-1"><Mail className="h-3 w-3" /> Email</Label>
                          <Input id="admin-email" name="email_id" type="email" value={form.email_id} onChange={handleChange} required autoComplete="new-password"
                            className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-indigo-500 placeholder:text-slate-400 dark:placeholder:text-slate-600" placeholder="john@university.edu" />
                        </div>

                        <div className="space-y-1.5">
                          <Label htmlFor="admin-password" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Password</Label>
                          <Input id="admin-password" name="password" type="password" value={form.password} onChange={handleChange} required autoComplete="new-password"
                            className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-indigo-500 placeholder:text-slate-400 dark:placeholder:text-slate-600" placeholder="••••••••" />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-1.5 col-span-2 sm:col-span-1">
                            <Label htmlFor="admin-school" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider flex items-center gap-1"><Building className="h-3 w-3" /> School</Label>
                            <Input id="admin-school" name="school" type="text" value={form.school} onChange={handleChange} required autoComplete="new-password"
                              className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-indigo-500 placeholder:text-slate-400 dark:placeholder:text-slate-600" placeholder="Engineering" />
                          </div>
                          <div className="space-y-1.5 col-span-2 sm:col-span-1">
                            <Label htmlFor="admin-dept" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider flex items-center gap-1"><Landmark className="h-3 w-3" /> Department</Label>
                            <Input id="admin-dept" name="department" type="text" value={form.department} onChange={handleChange} required autoComplete="new-password"
                              className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-indigo-500 placeholder:text-slate-400 dark:placeholder:text-slate-600" placeholder="Computer Science" />
                          </div>
                        </div>

                        <Button type="submit" disabled={creating} className="w-full bg-indigo-600 hover:bg-indigo-500 text-slate-900 dark:text-white mt-4 border border-indigo-500/50 shadow-lg shadow-indigo-500/20 transition-all duration-300">
                          <Plus className="mr-2 h-4 w-4" />
                          {creating ? 'Registering...' : 'Create Admin Account'}
                        </Button>
                      </form>
                    </CardContent>
                  </Card>
                </div>
              )}

              {activeTab === 'faculty' && (
                <div className="animate-in fade-in slide-in-from-right-4 duration-500">
                  <Card className="bg-white dark:bg-white/5 border-slate-300 dark:border-white/10 backdrop-blur-xl shadow-2xl relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-full blur-[50px] pointer-events-none" />
                    <CardHeader>
                      <CardTitle className="text-slate-900 dark:text-white text-xl">Register Faculty</CardTitle>
                      <CardDescription className="text-slate-600 dark:text-slate-400">Onboard a new teacher profile.</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <form onSubmit={handleCreateTeacher} className="space-y-4" autoComplete="off">
                        {/* Fake inputs to thwart browser autofill */}
                        <input type="text" name="fakeusernameremembered" style={{ display: 'none' }} />
                        <input type="password" name="fakepasswordremembered" style={{ display: 'none' }} />

                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-1.5 col-span-2 sm:col-span-1">
                            <Label htmlFor="faculty-name" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Full Name</Label>
                            <Input id="faculty-name" name="name" type="text" value={teacherForm.name} onChange={handleTeacherChange} required autoComplete="new-password"
                              className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-emerald-500 placeholder:text-slate-400 dark:placeholder:text-slate-600" placeholder="Jane Smith" />
                          </div>
                          <div className="space-y-1.5 col-span-2 sm:col-span-1">
                            <Label htmlFor="faculty-username" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Username</Label>
                            <Input id="faculty-username" name="username" type="text" value={teacherForm.username} onChange={handleTeacherChange} required autoComplete="new-password"
                              className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-emerald-500 placeholder:text-slate-400 dark:placeholder:text-slate-600" placeholder="janesmith" />
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-1.5 col-span-2 sm:col-span-1">
                            <Label htmlFor="faculty-email" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider flex items-center gap-1"><Mail className="h-3 w-3" /> Email</Label>
                            <Input id="faculty-email" name="email_id" type="email" value={teacherForm.email_id} onChange={handleTeacherChange} required autoComplete="new-password"
                              className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-emerald-500 placeholder:text-slate-400 dark:placeholder:text-slate-600" placeholder="jane@university.edu" />
                          </div>
                          <div className="space-y-1.5 col-span-2 sm:col-span-1">
                            <Label htmlFor="faculty-phone" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider flex items-center gap-1"><Phone className="h-3 w-3" /> Phone</Label>
                            <Input id="faculty-phone" name="mob" type="text" value={teacherForm.mob} onChange={handleTeacherChange} required autoComplete="new-password"
                              className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-emerald-500 placeholder:text-slate-400 dark:placeholder:text-slate-600" placeholder="+91 994230****" />
                          </div>
                        </div>

                        <div className="space-y-1.5">
                          <Label htmlFor="faculty-password" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Password</Label>
                          <Input id="faculty-password" name="password" type="password" value={teacherForm.password} onChange={handleTeacherChange} required autoComplete="new-password"
                            className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-emerald-500 placeholder:text-slate-400 dark:placeholder:text-slate-600" placeholder="••••••••" />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-1.5 col-span-2 sm:col-span-1">
                            <Label htmlFor="faculty-school" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider flex items-center gap-1"><Building className="h-3 w-3" /> School</Label>
                            <Input id="faculty-school" name="school" type="text" value={teacherForm.school} onChange={handleTeacherChange} required autoComplete="new-password"
                              className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-emerald-500 placeholder:text-slate-400 dark:placeholder:text-slate-600" placeholder="Engineering" />
                          </div>
                          <div className="space-y-1.5 col-span-2 sm:col-span-1">
                            <Label htmlFor="faculty-dept" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider flex items-center gap-1"><Landmark className="h-3 w-3" /> Department</Label>
                            <Input id="faculty-dept" name="department" type="text" value={teacherForm.department} onChange={handleTeacherChange} required autoComplete="new-password"
                              className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-emerald-500 placeholder:text-slate-400 dark:placeholder:text-slate-600" placeholder="Computer Science" />
                          </div>
                        </div>

                        <Button type="submit" disabled={creatingTeacher} className="w-full bg-emerald-600 hover:bg-emerald-500 text-slate-900 dark:text-white mt-4 border border-emerald-500/50 shadow-lg shadow-emerald-500/20 transition-all duration-300">
                          <Plus className="mr-2 h-4 w-4" />
                          {creatingTeacher ? 'Registering...' : 'Create Faculty Account'}
                        </Button>
                      </form>
                    </CardContent>
                  </Card>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
