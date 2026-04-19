import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ShieldCheck, Calendar, Users, BookOpen } from 'lucide-react';
import { createTeacher, scheduleLecture } from '@/services/api';

export default function AdminDashboard() {
  const navigate = useNavigate();
  const userName = localStorage.getItem('username') || 'Admin';

  const [teacherForm, setTeacherForm] = useState({
    username: '', password: '', name: '', email_id: '', school: '', department: '', mob: ''
  });
  const [teacherStatus, setTeacherStatus] = useState({ loading: false, error: '', success: '' });

  const [lectureForm, setLectureForm] = useState({
    username: '', year: '', specialisation: '', lecorlab: 'lec', panel: '', lec_name: '', course_code: '', lecture_datetime: ''
  });
  const [lectureStatus, setLectureStatus] = useState({ loading: false, error: '', success: '' });

  const handleTeacherChange = (e) => setTeacherForm({ ...teacherForm, [e.target.name]: e.target.value });
  const handleLectureChange = (e) => setLectureForm({ ...lectureForm, [e.target.name]: e.target.value });

  const handleCreateTeacher = async (e) => {
    e.preventDefault();
    setTeacherStatus({ loading: true, error: '', success: '' });
    try {
      await createTeacher(teacherForm);
      setTeacherStatus({ loading: false, error: '', success: `Teacher "${teacherForm.name}" created.` });
      setTeacherForm({ username: '', password: '', name: '', email_id: '', school: '', department: '', mob: '' });
    } catch (err) {
      setTeacherStatus({ loading: false, error: err?.response?.data?.detail || 'Error creating teacher.', success: '' });
    }
  };

  const handleScheduleLecture = async (e) => {
    e.preventDefault();
    setLectureStatus({ loading: true, error: '', success: '' });
    try {
      const payload = { ...lectureForm, lecture_datetime: new Date(lectureForm.lecture_datetime).toISOString() };
      await scheduleLecture(payload);
      setLectureStatus({ loading: false, error: '', success: `Lecture "${lectureForm.lec_name}" scheduled.` });
      setLectureForm({ username: '', year: '', specialisation: '', lecorlab: 'lec', panel: '', lec_name: '', course_code: '', lecture_datetime: '' });
    } catch (err) {
      setLectureStatus({ loading: false, error: err?.response?.data?.detail || 'Error scheduling lecture.', success: '' });
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-10">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold text-slate-800">Admin Management Portal</h2>
          <p className="text-slate-600 mt-1">Welcome, <span className="font-semibold text-indigo-600">{userName}</span></p>
        </div>
        <div className="flex gap-3 mt-4 md:mt-0">
          <Button onClick={() => navigate('/admin-records')} className="bg-indigo-100 text-indigo-700 hover:bg-indigo-200 shadow-sm border-0">
            <BookOpen className="mr-2 h-4 w-4" /> Attendance Records
          </Button>
          <Button onClick={() => navigate('/admin-students')} className="bg-indigo-600 hover:bg-indigo-700">
            <Users className="mr-2 h-4 w-4" /> Manage Students
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Create Teacher */}
        <Card className="border-0 shadow-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Users className="h-5 w-5 text-indigo-600"/> Create Teacher</CardTitle>
            <CardDescription>Register a new faculty member.</CardDescription>
          </CardHeader>
          <CardContent>
            {teacherStatus.error && <Alert variant="destructive" className="mb-2"><AlertDescription>{teacherStatus.error}</AlertDescription></Alert>}
            {teacherStatus.success && <Alert className="mb-2 border-green-300 bg-green-50"><AlertDescription className="text-green-700">{teacherStatus.success}</AlertDescription></Alert>}
            <form onSubmit={handleCreateTeacher} className="space-y-3">
               {['name', 'username', 'email_id', 'password', 'school', 'department', 'mob'].map(field => (
                 <div key={field} className="space-y-1">
                   <Label className="capitalize">{field.replace('_', ' ')}</Label>
                   <Input name={field} type={field === 'password' ? 'password' : 'text'} value={teacherForm[field]} onChange={handleTeacherChange} required />
                 </div>
               ))}
               <Button type="submit" disabled={teacherStatus.loading} className="w-full bg-indigo-600 hover:bg-indigo-700">Create</Button>
            </form>
          </CardContent>
        </Card>

        {/* Schedule Lecture */}
        <Card className="border-0 shadow-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Calendar className="h-5 w-5 text-purple-600"/> Schedule Lecture</CardTitle>
            <CardDescription>Assign a lecture to a teacher.</CardDescription>
          </CardHeader>
          <CardContent>
            {lectureStatus.error && <Alert variant="destructive" className="mb-2"><AlertDescription>{lectureStatus.error}</AlertDescription></Alert>}
            {lectureStatus.success && <Alert className="mb-2 border-green-300 bg-green-50"><AlertDescription className="text-green-700">{lectureStatus.success}</AlertDescription></Alert>}
            <form onSubmit={handleScheduleLecture} className="space-y-3">
                <div className="space-y-1"><Label>Teacher Username</Label><Input name="username" type="text" value={lectureForm.username} onChange={handleLectureChange} required /></div>
                <div className="space-y-1"><Label>Year</Label><Input name="year" type="text" placeholder="e.g. 1st Year" value={lectureForm.year} onChange={handleLectureChange} required /></div>
                <div className="space-y-1"><Label>Specialisation</Label><Input name="specialisation" type="text" placeholder="e.g. CSE, AIDS" value={lectureForm.specialisation} onChange={handleLectureChange} required /></div>
                <div className="space-y-1">
                  <Label>Lec or Lab</Label>
                  <select name="lecorlab" value={lectureForm.lecorlab} onChange={handleLectureChange} required className="w-full border border-slate-300 rounded-md p-2 bg-white text-sm">
                    <option value="lec">Lecture</option>
                    <option value="lab">Lab</option>
                  </select>
                </div>
                <div className="space-y-1"><Label>Panel (e.g. H)</Label><Input name="panel" value={lectureForm.panel} onChange={handleLectureChange} required /></div>
                <div className="space-y-1"><Label>Lecture Name</Label><Input name="lec_name" value={lectureForm.lec_name} onChange={handleLectureChange} required /></div>
                <div className="space-y-1"><Label>Course Code</Label><Input name="course_code" value={lectureForm.course_code} onChange={handleLectureChange} required /></div>
                <div className="space-y-1"><Label>Date & Time</Label><Input name="lecture_datetime" type="datetime-local" value={lectureForm.lecture_datetime} onChange={handleLectureChange} required /></div>
                <Button type="submit" disabled={lectureStatus.loading} className="w-full bg-purple-600 hover:bg-purple-700">Schedule</Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
