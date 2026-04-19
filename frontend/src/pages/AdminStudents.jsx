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
    <div className="space-y-6 pb-10">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <h2 className="text-3xl font-bold">Manage Students</h2>
        <Button variant="outline" onClick={() => navigate('/admin-dashboard')}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
        </Button>
      </div>

      <Card className="max-w-xl shadow-xl border-0">
        <CardHeader>
          <CardTitle>Enroll New Student</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                {error}
              </div>
            )}

            {success && (
              <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
                {success.message ?? `Student "${success.name}" (PRN: ${success.prn}) enrolled successfully.`}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="prn">PRN</Label>
              <Input
                id="prn"
                type="text"
                placeholder="e.g. 1234567890"
                value={prn}
                onChange={(e) => setPrn(e.target.value)}
                required
                disabled={loading}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="student-name">Student Name</Label>
              <Input
                id="student-name"
                type="text"
                placeholder="Full name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                disabled={loading}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="year">Year</Label>
                <Input id="year" type="text" placeholder="e.g. FY" value={year} onChange={(e) => setYear(e.target.value)} required disabled={loading} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="course">Course</Label>
                <Input id="course" type="text" placeholder="e.g. B.Tech CS" value={course} onChange={(e) => setCourse(e.target.value)} required disabled={loading} />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="specialisation">Specialisation</Label>
                <Input id="specialisation" type="text" placeholder="e.g. CSE or AIDS" value={specialisation} onChange={(e) => setSpecialisation(e.target.value)} required disabled={loading} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rollno">Roll No</Label>
                <Input id="rollno" type="text" placeholder="e.g. 15" value={rollno} onChange={(e) => setRollno(e.target.value)} required disabled={loading} />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="panel">Panel</Label>
              <Input
                id="panel"
                type="text"
                placeholder="e.g. A"
                value={panel}
                onChange={(e) => setPanel(e.target.value)}
                required
                disabled={loading}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="images">
                Student Images{' '}
                <span className={`text-xs font-normal ${images.length === REQUIRED_IMAGES ? 'text-green-600' : 'text-slate-500'}`}>
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
              />
              <p className="text-xs text-slate-500">Select exactly {REQUIRED_IMAGES} images.</p>
            </div>

            <Button
              type="submit"
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
              disabled={loading}
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
                  </svg>
                  Enrolling (this may take a moment)...
                </span>
              ) : 'Enroll Student'}
            </Button>

          </form>
        </CardContent>
      </Card>
    </div>
  );
}
