import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { enrollStudent } from "@/services/api";

const REQUIRED_IMAGES = 25;

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default function AdminStudents() {
  const navigate = useNavigate();
  const [prn, setPrn] = useState('');
  const [name, setName] = useState('');
  const [year, setYear] = useState('');
  const [course, setCourse] = useState('');
  const [specialisation, setSpecialisation] = useState('');
  const [rollno, setRollno] = useState('');
  const [panel, setPanel] = useState('');
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    setImages(Array.from(e.target.files));
    setError('');
    setSuccess(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess(null);

    if (images.length !== REQUIRED_IMAGES) {
      setError(`Exactly ${REQUIRED_IMAGES} images are required. You selected ${images.length}.`);
      return;
    }

    setLoading(true);
    try {
      const base64Images = await Promise.all(images.map(fileToBase64));
      const data = await enrollStudent(prn, name, year, course, specialisation, rollno, panel, base64Images);
      setSuccess({ name, prn: data.prn ?? prn, message: data.message });
      // Reset form
      setPrn('');
      setName('');
      setYear('');
      setCourse('');
      setSpecialisation('');
      setRollno('');
      setPanel('');
      setImages([]);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      if (err.response?.status === 409) {
        setError(`Student with PRN "${prn}" is already enrolled.`);
      } else {
        setError(err.response?.data?.detail ?? 'Enrollment failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-[calc(100vh-2rem)] bg-slate-50 dark:bg-[#0f1117] text-slate-800 dark:text-slate-200 p-4 sm:p-8 rounded-xl overflow-hidden font-sans shadow-2xl selection:bg-purple-500/30">
      {/* Background Effects */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-purple-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[30%] h-[40%] rounded-full bg-indigo-600/10 blur-[120px] pointer-events-none" />

      <div className="relative space-y-6 animate-in fade-in duration-700 z-10 w-full max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-6 border-b border-slate-300 dark:border-white/10">
          <h2 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-purple-400 via-violet-400 to-indigo-400">
            Manage Students
          </h2>
          <Button variant="outline" onClick={() => navigate('/admin-dashboard')} className="bg-white dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-slate-900 dark:text-white border-slate-300 dark:border-white/10 shadow-lg backdrop-blur-md transition-all duration-300">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
          </Button>
        </div>

        <Card className="max-w-2xl mx-auto bg-white dark:bg-white/5 border-slate-300 dark:border-white/10 backdrop-blur-xl shadow-xl relative overflow-hidden transition-all duration-300 hover:bg-slate-100 dark:hover:bg-white/[0.07]">
          <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/10 rounded-full blur-[50px] pointer-events-none" />
          <CardHeader className="border-b border-slate-200 dark:border-white/5 pb-4">
            <CardTitle className="text-slate-900 dark:text-white flex items-center gap-3">
              <div className="bg-purple-500/20 text-purple-400 p-2.5 rounded-lg border border-purple-500/20 shadow-[0_0_15px_rgba(168,85,247,0.15)]">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              </div>
              Enroll New Student
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <form onSubmit={handleSubmit} className="space-y-4">

              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
                  {error}
                </div>
              )}

              {success && (
                <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400 text-sm">
                  {success.message ?? `Student "${success.name}" (PRN: ${success.prn}) enrolled successfully.`}
                </div>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="prn" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">PRN</Label>
                <Input
                  id="prn"
                  type="text"
                  placeholder="e.g. 1234567890"
                  value={prn}
                  onChange={(e) => setPrn(e.target.value)}
                  required
                  disabled={loading}
                  className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-purple-500 placeholder:text-slate-400 dark:placeholder:text-slate-600 h-10"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="student-name" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Student Name</Label>
                <Input
                  id="student-name"
                  type="text"
                  placeholder="Full name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  disabled={loading}
                  className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-purple-500 placeholder:text-slate-400 dark:placeholder:text-slate-600 h-10"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="year" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Year</Label>
                  <Input id="year" type="text" placeholder="e.g. FY" value={year} onChange={(e) => setYear(e.target.value)} required disabled={loading} className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-purple-500 placeholder:text-slate-400 dark:placeholder:text-slate-600 h-10" />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="course" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Course</Label>
                  <Input id="course" type="text" placeholder="e.g. B.Tech CS" value={course} onChange={(e) => setCourse(e.target.value)} required disabled={loading} className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-purple-500 placeholder:text-slate-400 dark:placeholder:text-slate-600 h-10" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="specialisation" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Specialisation</Label>
                  <Input id="specialisation" type="text" placeholder="e.g. CSE or AIDS" value={specialisation} onChange={(e) => setSpecialisation(e.target.value)} required disabled={loading} className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-purple-500 placeholder:text-slate-400 dark:placeholder:text-slate-600 h-10" />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="rollno" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Roll No</Label>
                  <Input id="rollno" type="text" placeholder="e.g. 15" value={rollno} onChange={(e) => setRollno(e.target.value)} required disabled={loading} className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-purple-500 placeholder:text-slate-400 dark:placeholder:text-slate-600 h-10" />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="panel" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Panel</Label>
                <Input
                  id="panel"
                  type="text"
                  placeholder="e.g. A"
                  value={panel}
                  onChange={(e) => setPanel(e.target.value)}
                  required
                  disabled={loading}
                  className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-purple-500 placeholder:text-slate-400 dark:placeholder:text-slate-600 h-10"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="images" className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">
                  Student Images{' '}
                  <span className={`text-xs font-normal ${images.length === REQUIRED_IMAGES ? 'text-teal-400' : 'text-slate-500'}`}>
                    ({images.length}/{REQUIRED_IMAGES} selected)
                  </span>
                </Label>
                <Input
                  id="images"
                  type="file"
                  accept="image/*"
                  multiple
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  required
                  disabled={loading}
                  className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-700 dark:text-slate-300 focus-visible:ring-purple-500 h-10 file:text-white file:bg-white/10 file:border-0 hover:file:bg-white/20 file:mr-4 file:h-full cursor-pointer"
                />
                <p className="text-xs text-slate-500 pt-1">Select exactly {REQUIRED_IMAGES} images.</p>
              </div>

              <Button
                type="submit"
                className="w-full bg-purple-600 hover:bg-purple-500 text-slate-900 dark:text-white mt-4 border border-purple-500/50 shadow-[0_0_15px_rgba(147,51,234,0.2)] transition-all duration-300 h-11"
                disabled={loading}
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Enrolling (this may take a moment)...
                  </span>
                ) : 'Enroll Student'}
              </Button>

            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
