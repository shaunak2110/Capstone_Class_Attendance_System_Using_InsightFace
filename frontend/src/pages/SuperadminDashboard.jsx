import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Users, ShieldCheck, Plus, BookOpen } from 'lucide-react';
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
      // Refresh user list
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
      // Refresh user list
      const updated = await getUsers();
      setUsers(updated);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to create faculty.');
    } finally {
      setCreatingTeacher(false);
    }
  };

  const privilegeLabel = (level) => {
    if (level === 1) return <span className="px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">Superadmin</span>;
    if (level === 2) return <span className="px-2 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700">Admin</span>;
    return <span className="px-2 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700">Teacher</span>;
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-10">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold text-slate-800">Superadmin Dashboard</h2>
          <p className="text-slate-600 mt-1">
            Welcome, <span className="font-semibold text-indigo-600">{userName}</span>
          </p>
        </div>
        <div className="flex gap-3 mt-4 md:mt-0">
          <Button onClick={() => navigate('/admin-records')} className="bg-indigo-100 text-indigo-700 hover:bg-indigo-200 shadow-sm border-0">
            <BookOpen className="mr-2 h-4 w-4" /> Attendance Records
          </Button>
        </div>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      {success && (
        <Alert className="border-green-300 bg-green-50">
          <AlertDescription className="text-green-700">{success}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* User List */}
        <Card className="border-0 shadow-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-slate-800">
              <Users className="h-5 w-5 text-indigo-600" />
              All Users
            </CardTitle>
            <CardDescription>All registered users in the system</CardDescription>
          </CardHeader>
          <CardContent>
            {usersLoading ? (
              <p className="text-slate-500 text-sm">Loading users...</p>
            ) : users.length === 0 ? (
              <p className="text-slate-500 text-sm">No users found.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Username</TableHead>
                    <TableHead>Department</TableHead>
                    <TableHead>School</TableHead>
                    <TableHead>Role</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((u) => (
                    <TableRow key={u.user_id}>
                      <TableCell className="font-medium">{u.name}</TableCell>
                      <TableCell className="text-slate-500 text-sm">{u.username}</TableCell>
                      <TableCell>{u.department}</TableCell>
                      <TableCell>{u.school}</TableCell>
                      <TableCell>{privilegeLabel(u.privilege_level)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Create Forms with Tabs */}
        <div className="space-y-5">
          <div className="flex p-1 bg-slate-100 rounded-lg w-full max-w-sm">
            <button
              className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-md transition-all ${activeTab === 'admin' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
              onClick={() => setActiveTab('admin')}
            >
              <ShieldCheck className="h-4 w-4" /> Create Admin
            </button>
            <button
              className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-md transition-all ${activeTab === 'faculty' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
              onClick={() => setActiveTab('faculty')}
            >
              <Users className="h-4 w-4" /> Create Faculty
            </button>
          </div>

          <div className="relative">
            {activeTab === 'admin' && (
              <div className="animate-in fade-in zoom-in-95 duration-200">
                <Card className="border-0 shadow-xl">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-slate-800">
                      <ShieldCheck className="h-5 w-5 text-indigo-600" />
                      Create Admin
                    </CardTitle>
                    <CardDescription>Add a new admin account</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <form onSubmit={handleCreateAdmin} className="space-y-3">
                      {[
                        { name: 'name', label: 'Full Name', type: 'text' },
                        { name: 'username', label: 'Username (Email)', type: 'email' },
                        { name: 'email_id', label: 'Email ID', type: 'email' },
                        { name: 'password', label: 'Password', type: 'password' },
                        { name: 'school', label: 'School', type: 'text' },
                        { name: 'department', label: 'Department', type: 'text' },
                      ].map(({ name, label, type }) => (
                        <div key={name} className="space-y-1">
                          <Label htmlFor={name}>{label}</Label>
                          <Input
                            id={name}
                            name={name}
                            type={type}
                            value={form[name]}
                            onChange={handleChange}
                            required
                            className="border-slate-300"
                          />
                        </div>
                      ))}
                      <Button type="submit" disabled={creating} className="w-full bg-indigo-600 hover:bg-indigo-700 mt-2">
                        <Plus className="mr-2 h-4 w-4" />
                        {creating ? 'Creating...' : 'Create Admin'}
                      </Button>
                    </form>
                  </CardContent>
                </Card>
              </div>
            )}

            {activeTab === 'faculty' && (
              <div className="animate-in fade-in zoom-in-95 duration-200">
                <Card className="border-0 shadow-xl">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-slate-800">
                      <Users className="h-5 w-5 text-indigo-600" />
                      Create Faculty
                    </CardTitle>
                    <CardDescription>Add a new faculty/teacher account</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <form onSubmit={handleCreateTeacher} className="space-y-3">
                      {[
                        { name: 'name', label: 'Full Name', type: 'text' },
                        { name: 'username', label: 'Username (Email)', type: 'email' },
                        { name: 'email_id', label: 'Email ID', type: 'email' },
                        { name: 'password', label: 'Password', type: 'password' },
                        { name: 'school', label: 'School', type: 'text' },
                        { name: 'department', label: 'Department', type: 'text' },
                        { name: 'mob', label: 'Mobile Number', type: 'text' },
                      ].map(({ name, label, type }) => (
                        <div key={name} className="space-y-1">
                          <Label htmlFor={`teacher-${name}`}>{label}</Label>
                          <Input
                            id={`teacher-${name}`}
                            name={name}
                            type={type}
                            value={teacherForm[name]}
                            onChange={handleTeacherChange}
                            required
                            className="border-slate-300"
                          />
                        </div>
                      ))}
                      <Button type="submit" disabled={creatingTeacher} className="w-full bg-indigo-600 hover:bg-indigo-700 mt-2">
                        <Plus className="mr-2 h-4 w-4" />
                        {creatingTeacher ? 'Creating...' : 'Create Faculty'}
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
  );
}
