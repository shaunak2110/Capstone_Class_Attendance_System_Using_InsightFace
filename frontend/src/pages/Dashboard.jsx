import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { UploadCloud, Activity, Users, BookOpen } from 'lucide-react';
import { getLectures, markAttendance } from '@/services/api';

export default function Dashboard() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [lectures, setLectures] = useState([]);
  const [lecturesLoading, setLecturesLoading] = useState(true);
  const [selectedLecId, setSelectedLecId] = useState('');
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const role = localStorage.getItem('privilege_level');
  const userName = localStorage.getItem('username') || 'User';

  useEffect(() => {
    getLectures()
      .then(setLectures)
      .catch(() => setError('Failed to load lectures.'))
      .finally(() => setLecturesLoading(false));
  }, []);

  const handleFileChange = (e) => {
    setSelectedFiles(Array.from(e.target.files));
    setError('');
    e.target.value = '';
  };

  const toBase64 = (file) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(',')[1]);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedLecId) { setError('Please select a lecture.'); return; }
    if (selectedFiles.length === 0) { setError('Please select at least one image.'); return; }

    setLoading(true);
    setError('');
    try {
      const base64Images = await Promise.all(selectedFiles.map(toBase64));
      const result = await markAttendance(parseInt(selectedLecId), base64Images);
      navigate('/results', {
        state: {
          lecId: parseInt(selectedLecId),
          identified_students: result.identified_students,
          unidentified_faces: result.unidentified_faces,
        },
      });
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to process attendance. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const formatDateTime = (dt) => {
    if (!dt) return '';
    return new Date(dt).toLocaleString(undefined, {
      dateStyle: 'medium', timeStyle: 'short',
    });
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-10">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold text-slate-800">Dashboard</h2>
          <p className="text-slate-600 mt-1">
            Welcome, <span className="font-semibold text-indigo-600">{userName}</span>
          </p>
        </div>
        {(role === '1' || role === '2') && (
          <Button onClick={() => navigate('/admin-students')} className="bg-indigo-600 hover:bg-indigo-700">
            <Users className="mr-2 h-4 w-4" />
            Manage Students
          </Button>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Lecture Selection Card */}
        <Card className="border-0 shadow-xl bg-gradient-to-br from-blue-50 to-indigo-100">
          <CardHeader className="bg-white/70 backdrop-blur-sm rounded-t-lg">
            <CardTitle className="text-blue-800 flex items-center gap-2">
              <div className="bg-blue-600 text-white p-2 rounded-lg">
                <BookOpen className="h-5 w-5" />
              </div>
              Select Lecture
            </CardTitle>
            <CardDescription className="text-blue-600">Choose the lecture to mark attendance for</CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            {lecturesLoading ? (
              <p className="text-slate-500 text-sm">Loading lectures...</p>
            ) : lectures.length === 0 ? (
              <p className="text-slate-500 text-sm">No lectures scheduled.</p>
            ) : (
              <div className="space-y-2">
                <Label>Lecture</Label>
                <Select value={selectedLecId} onValueChange={setSelectedLecId}>
                  <SelectTrigger className="bg-white border-slate-300">
                    <SelectValue placeholder="Select a lecture" />
                  </SelectTrigger>
                  <SelectContent className="bg-white border-slate-200">
                    {lectures.map((lec) => (
                      <SelectItem
                        key={lec.lec_id}
                        value={String(lec.lec_id)}
                        className="cursor-pointer hover:bg-blue-50"
                      >
                        {lec.lec_name} — {lec.panel} — {formatDateTime(lec.lecture_datetime)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Upload Card */}
        <Card className="border-0 shadow-xl bg-gradient-to-br from-purple-50 to-pink-100">
          <CardHeader className="bg-white/70 backdrop-blur-sm rounded-t-lg">
            <CardTitle className="text-purple-800 flex items-center gap-2">
              <div className="bg-purple-600 text-white p-2 rounded-lg">
                <UploadCloud className="h-5 w-5" />
              </div>
              Upload Classroom Images
            </CardTitle>
            <CardDescription className="text-purple-600">Select one or more classroom photos</CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            <form onSubmit={handleSubmit} className="space-y-4">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={handleFileChange}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="w-full border-2 border-dashed border-purple-300 rounded-lg p-8 text-center hover:bg-purple-50 transition-colors cursor-pointer"
              >
                <UploadCloud className="mx-auto h-8 w-8 text-purple-400 mb-2" />
                <p className="text-sm text-slate-600">Click to select images</p>
              </button>

              {selectedFiles.length > 0 && (
                <p className="text-sm text-slate-600 font-medium">
                  {selectedFiles.length} image{selectedFiles.length > 1 ? 's' : ''} selected
                </p>
              )}

              <Button
                type="submit"
                className="w-full bg-indigo-600 hover:bg-indigo-700"
                disabled={loading || lecturesLoading}
              >
                {loading ? (
                  <>
                    <Activity className="mr-2 h-4 w-4 animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <UploadCloud className="mr-2 h-4 w-4" />
                    Process Attendance
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
