import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Users, ShieldCheck, Plus } from 'lucide-react';
import { getUsers, createAdmin } from '@/services/api';

export default function SuperadminDashboard() {
  const userName = localStorage.getItem('username') || 'Superadmin';

  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [form, setForm] = useState({
    username: '', password: '', name: '', email_id: '', school: '', department: ''
  });
  const [creating, setCreating] = useState(false);

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

  const privilegeLabel = (level) => {
    if (level === 1) return <span className="px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">Superadmin</span>;
    if (level === 2) return <span className="px-2 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700">Admin</span>;
    return <span className="px-2 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700">Teacher</span>;
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-10">
      {/* Header */}
      <div>
        <h2 className="text-3xl font-bold text-slate-800">Superadmin Dashboard</h2>
        <p className="text-slate-600 mt-1">
          Welcome, <span className="font-semibold text-indigo-600">{userName}</span>
        </p>
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
                    <TableHead>Role</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((u) => (
                    <TableRow key={u.user_id}>
                      <TableCell className="font-medium">{u.name}</TableCell>
                      <TableCell className="text-slate-500 text-sm">{u.username}</TableCell>
                      <TableCell>{privilegeLabel(u.privilege_level)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Create Admin Form */}
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
    </div>
  );
}
