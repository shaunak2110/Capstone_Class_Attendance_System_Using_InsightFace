import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ShieldCheck, Calendar, Users, BookOpen, Plus, Clock } from 'lucide-react';
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
    <div className="relative min-h-[calc(100vh-2rem)] bg-[#0f1117] text-slate-200 p-4 sm:p-8 rounded-xl overflow-hidden font-sans shadow-2xl selection:bg-purple-500/30">
      {/* Background Effects */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-purple-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute top-[40%] right-[-10%] w-[30%] h-[40%] rounded-full bg-teal-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] left-[20%] w-[40%] h-[40%] rounded-full bg-indigo-600/10 blur-[120px] pointer-events-none" />

      <div className="relative space-y-8 animate-in fade-in duration-700 z-10 w-full max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-white/10">
          <div>
            <h2 className="text-4xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-purple-400 via-teal-400 to-indigo-400 mb-2">
              Management Portal
            </h2>
            <p className="text-slate-400 text-lg">
              Welcome back, <span className="font-semibold text-purple-300">{userName}</span>
            </p>
          </div>
          <div className="flex gap-3">
            <Button onClick={() => navigate('/admin-records')} className="bg-white/5 hover:bg-white/10 text-white border border-white/10 shadow-lg backdrop-blur-md transition-all duration-300">
              <BookOpen className="mr-2 h-4 w-4 text-purple-400" /> Attendance Records
            </Button>
            <Button onClick={() => navigate('/admin-students')} className="bg-purple-600 hover:bg-purple-500 text-white shadow-[0_0_15px_rgba(147,51,234,0.3)] border border-purple-500/50 transition-all duration-300">
              <Users className="mr-2 h-4 w-4" /> Manage Students
            </Button>
          </div>
        </div>

        <div className="grid gap-8 lg:grid-cols-2 lg:items-start">
          {/* Create Teacher Card */}
          <Card className="bg-white/5 border-white/10 backdrop-blur-xl shadow-xl relative overflow-hidden transition-all duration-300 hover:bg-white/[0.07]">
            <div className="absolute top-0 right-0 w-32 h-32 bg-teal-500/10 rounded-full blur-[50px] pointer-events-none" />
            <CardHeader className="border-b border-white/5 pb-4">
              <CardTitle className="text-white flex items-center gap-3">
                <div className="bg-teal-500/20 text-teal-400 p-2.5 rounded-lg border border-teal-500/20 shadow-[0_0_15px_rgba(20,184,166,0.15)]">
                  <Users className="h-5 w-5" />
                </div>
                Onboard Faculty
              </CardTitle>
              <CardDescription className="text-slate-400 pt-1">Register a new educator profile in the system.</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              {teacherStatus.error && <Alert variant="destructive" className="mb-4 bg-red-500/10 border border-red-500/20 text-red-400"><AlertDescription>{teacherStatus.error}</AlertDescription></Alert>}
              {teacherStatus.success && <Alert className="mb-4 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"><AlertDescription>{teacherStatus.success}</AlertDescription></Alert>}
              
              <form onSubmit={handleCreateTeacher} className="space-y-4" autoComplete="off">
                 {/* Fake inputs to thwart browser autofill */}
                 <input type="text" name="fakeusernameremembered" style={{display: 'none'}} />
                 <input type="password" name="fakepasswordremembered" style={{display: 'none'}} />
                
                 <div className="grid grid-cols-2 gap-4">
                   <div className="space-y-1.5 col-span-2 sm:col-span-1">
                     <Label className="text-slate-300 text-xs uppercase tracking-wider">Full Name</Label>
                     <Input name="name" type="text" placeholder="John Doe" value={teacherForm.name} onChange={handleTeacherChange} required autoComplete="new-password"
                       className="bg-black/20 border-white/10 text-white focus-visible:ring-teal-500 placeholder:text-slate-600 h-10" />
                   </div>
                   <div className="space-y-1.5 col-span-2 sm:col-span-1">
                     <Label className="text-slate-300 text-xs uppercase tracking-wider">Username</Label>
                     <Input name="username" type="text" placeholder="johndoe" value={teacherForm.username} onChange={handleTeacherChange} required autoComplete="new-password"
                       className="bg-black/20 border-white/10 text-white focus-visible:ring-teal-500 placeholder:text-slate-600 h-10" />
                   </div>
                 </div>

                 <div className="grid grid-cols-2 gap-4">
                   <div className="space-y-1.5 col-span-2 sm:col-span-1">
                     <Label className="text-slate-300 text-xs uppercase tracking-wider">Email Address</Label>
                     <Input name="email_id" type="email" placeholder="john@university.edu" value={teacherForm.email_id} onChange={handleTeacherChange} required autoComplete="new-password"
                       className="bg-black/20 border-white/10 text-white focus-visible:ring-teal-500 placeholder:text-slate-600 h-10" />
                   </div>
                   <div className="space-y-1.5 col-span-2 sm:col-span-1">
                     <Label className="text-slate-300 text-xs uppercase tracking-wider">Mobile Number</Label>
                     <Input name="mob" type="text" placeholder="+1 234 567 890" value={teacherForm.mob} onChange={handleTeacherChange} required autoComplete="new-password"
                       className="bg-black/20 border-white/10 text-white focus-visible:ring-teal-500 placeholder:text-slate-600 h-10" />
                   </div>
                 </div>

                 <div className="space-y-1.5">
                   <Label className="text-slate-300 text-xs uppercase tracking-wider">Password</Label>
                   <Input name="password" type="password" placeholder="••••••••" value={teacherForm.password} onChange={handleTeacherChange} required autoComplete="new-password"
                     className="bg-black/20 border-white/10 text-white focus-visible:ring-teal-500 placeholder:text-slate-600 h-10" />
                 </div>

                 <div className="grid grid-cols-2 gap-4">
                   <div className="space-y-1.5 col-span-2 sm:col-span-1">
                     <Label className="text-slate-300 text-xs uppercase tracking-wider">School</Label>
                     <Input name="school" type="text" placeholder="Engineering" value={teacherForm.school} onChange={handleTeacherChange} required autoComplete="new-password"
                       className="bg-black/20 border-white/10 text-white focus-visible:ring-teal-500 placeholder:text-slate-600 h-10" />
                   </div>
                   <div className="space-y-1.5 col-span-2 sm:col-span-1">
                     <Label className="text-slate-300 text-xs uppercase tracking-wider">Department</Label>
                     <Input name="department" type="text" placeholder="Computer Science" value={teacherForm.department} onChange={handleTeacherChange} required autoComplete="new-password"
                       className="bg-black/20 border-white/10 text-white focus-visible:ring-teal-500 placeholder:text-slate-600 h-10" />
                   </div>
                 </div>

                 <Button type="submit" disabled={teacherStatus.loading} className="w-full bg-teal-600 hover:bg-teal-500 text-white mt-2 border border-teal-500/50 shadow-[0_0_15px_rgba(20,184,166,0.2)] transition-all duration-300 h-11">
                   <Plus className="mr-2 h-4 w-4" /> {teacherStatus.loading ? 'Creating...' : 'Create Faculty Profile'}
                 </Button>
              </form>
            </CardContent>
          </Card>

          {/* Schedule Lecture Card */}
          <Card className="bg-white/5 border-white/10 backdrop-blur-xl shadow-xl relative overflow-hidden transition-all duration-300 hover:bg-white/[0.07]">
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-[50px] pointer-events-none" />
            <CardHeader className="border-b border-white/5 pb-4">
              <CardTitle className="text-white flex items-center gap-3">
                <div className="bg-indigo-500/20 text-indigo-400 p-2.5 rounded-lg border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.15)]">
                  <Calendar className="h-5 w-5" />
                </div>
                Schedule Lecture Details
              </CardTitle>
              <CardDescription className="text-slate-400 pt-1">Allocate sessions and coordinate faculty schedules.</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              {lectureStatus.error && <Alert variant="destructive" className="mb-4 bg-red-500/10 border border-red-500/20 text-red-400"><AlertDescription>{lectureStatus.error}</AlertDescription></Alert>}
              {lectureStatus.success && <Alert className="mb-4 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"><AlertDescription>{lectureStatus.success}</AlertDescription></Alert>}
              
              <form onSubmit={handleScheduleLecture} className="space-y-4" autoComplete="off">
                 
                 <div className="space-y-1.5">
                   <Label className="text-slate-300 text-xs uppercase tracking-wider">Teacher Username</Label>
                   <Input name="username" type="text" placeholder="faculty username" value={lectureForm.username} onChange={handleLectureChange} required autoComplete="new-password"
                     className="bg-black/20 border-white/10 text-white focus-visible:ring-indigo-500 placeholder:text-slate-600 h-10" />
                 </div>

                 <div className="grid grid-cols-2 gap-4">
                   <div className="space-y-1.5 col-span-2 sm:col-span-1">
                     <Label className="text-slate-300 text-xs uppercase tracking-wider">Academic Year</Label>
                     <Input name="year" type="text" placeholder="e.g. 1st Year" value={lectureForm.year} onChange={handleLectureChange} required autoComplete="new-password"
                       className="bg-black/20 border-white/10 text-white focus-visible:ring-indigo-500 placeholder:text-slate-600 h-10" />
                   </div>
                   <div className="space-y-1.5 col-span-2 sm:col-span-1">
                     <Label className="text-slate-300 text-xs uppercase tracking-wider">Specialisation</Label>
                     <Input name="specialisation" type="text" placeholder="e.g. CSE, AIDS" value={lectureForm.specialisation} onChange={handleLectureChange} required autoComplete="new-password"
                       className="bg-black/20 border-white/10 text-white focus-visible:ring-indigo-500 placeholder:text-slate-600 h-10" />
                   </div>
                 </div>

                 <div className="grid grid-cols-2 gap-4">
                   <div className="space-y-1.5 col-span-2 sm:col-span-1">
                     <Label className="text-slate-300 text-xs uppercase tracking-wider">Session Type</Label>
                     <select name="lecorlab" value={lectureForm.lecorlab} onChange={handleLectureChange} required 
                       className="w-full bg-black/20 border border-white/10 text-slate-200 rounded-md focus:ring-1 focus:ring-indigo-500 outline-none h-10 px-3">
                       <option value="lec" className="bg-slate-900">Lecture</option>
                       <option value="lab" className="bg-slate-900">Lab</option>
                     </select>
                   </div>
                   <div className="space-y-1.5 col-span-2 sm:col-span-1">
                     <Label className="text-slate-300 text-xs uppercase tracking-wider">Panel Group</Label>
                     <Input name="panel" type="text" placeholder="e.g. H" value={lectureForm.panel} onChange={handleLectureChange} required autoComplete="new-password"
                       className="bg-black/20 border-white/10 text-white focus-visible:ring-indigo-500 placeholder:text-slate-600 h-10" />
                   </div>
                 </div>

                 <div className="grid grid-cols-2 gap-4">
                   <div className="space-y-1.5 col-span-2 sm:col-span-1">
                     <Label className="text-slate-300 text-xs uppercase tracking-wider">Lecture Name</Label>
                     <Input name="lec_name" type="text" placeholder="Data Structures" value={lectureForm.lec_name} onChange={handleLectureChange} required autoComplete="new-password"
                       className="bg-black/20 border-white/10 text-white focus-visible:ring-indigo-500 placeholder:text-slate-600 h-10" />
                   </div>
                   <div className="space-y-1.5 col-span-2 sm:col-span-1">
                     <Label className="text-slate-300 text-xs uppercase tracking-wider">Course Code</Label>
                     <Input name="course_code" type="text" placeholder="CS201" value={lectureForm.course_code} onChange={handleLectureChange} required autoComplete="new-password"
                       className="bg-black/20 border-white/10 text-white focus-visible:ring-indigo-500 placeholder:text-slate-600 h-10" />
                   </div>
                 </div>

                 <div className="space-y-1.5">
                   <Label className="text-slate-300 text-xs uppercase tracking-wider">Target Date & Time</Label>
                   <Input name="lecture_datetime" type="datetime-local" value={lectureForm.lecture_datetime} onChange={handleLectureChange} required 
                     className="bg-black/20 border-white/10 text-white focus-visible:ring-indigo-500 h-10 [color-scheme:dark]" />
                 </div>

                 <Button type="submit" disabled={lectureStatus.loading} className="w-full bg-indigo-600 hover:bg-indigo-500 text-white mt-2 border border-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.2)] transition-all duration-300 h-11">
                   <Clock className="mr-2 h-4 w-4" /> {lectureStatus.loading ? 'Scheduling...' : 'Reserve Timeslot'}
                 </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
