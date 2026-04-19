import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { UploadCloud, Activity, Users, BookOpen, Camera, X, FileText, ChevronDown, Download } from 'lucide-react';
import { getLectures, markAttendance, getAttendanceRecords } from '@/services/api';

export default function Dashboard() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [lectures, setLectures] = useState([]);
  const [lecturesLoading, setLecturesLoading] = useState(true);
  const [selectedLecId, setSelectedLecId] = useState('');
  const [manualDatetime, setManualDatetime] = useState('');
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Attendance records panel state
  const [recLecId, setRecLecId] = useState('');
  const [recDateFrom, setRecDateFrom] = useState('');
  const [recDateTo, setRecDateTo] = useState('');
  const [records, setRecords] = useState([]);
  const [recLoading, setRecLoading] = useState(false);
  const [recError, setRecError] = useState('');
  const [recFetched, setRecFetched] = useState(false);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const [stream, setStream] = useState(null);

  const role = localStorage.getItem('privilege_level');
  const userName = localStorage.getItem('username') || 'User';

  useEffect(() => {
    getLectures()
      .then(setLectures)
      .catch(() => setError('Failed to load lectures.'))
      .finally(() => setLecturesLoading(false));
  }, []);

  const startCamera = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ video: true });
      setStream(mediaStream);
      setIsCameraOpen(true);
    } catch (err) {
      setError("Unable to access camera: " + err.message);
    }
  };

  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
    setIsCameraOpen(false);
  };

  const captureImage = () => {
    if (videoRef.current && canvasRef.current) {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => {
        const file = new File([blob], `capture-${Date.now()}.jpg`, { type: 'image/jpeg' });
        setSelectedFiles(prev => [...prev, file]);
      }, 'image/jpeg');
    }
  };

  useEffect(() => {
    if (isCameraOpen && videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [isCameraOpen, stream]);

  useEffect(() => {
    return () => {
      if (stream) stream.getTracks().forEach(track => track.stop());
    };
  }, [stream]);

  const handleFileChange = (e) => {
    setSelectedFiles(prev => [...prev, ...Array.from(e.target.files)]);
    setError('');
    e.target.value = '';
  };

  const removeImage = (index) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
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
      const isoDatetime = manualDatetime ? new Date(manualDatetime).toISOString() : null;
      const result = await markAttendance(parseInt(selectedLecId), base64Images, isoDatetime);
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

  const fetchRecords = async () => {
    if (!recLecId) { setRecError('Please select a lecture.'); return; }
    setRecLoading(true);
    setRecError('');
    setRecFetched(false);
    try {
      const data = await getAttendanceRecords(parseInt(recLecId), recDateFrom || null, recDateTo || null);
      setRecords(data);
      setRecFetched(true);
    } catch (err) {
      setRecError(err?.response?.data?.detail || 'Failed to fetch records.');
    } finally {
      setRecLoading(false);
    }
  };

  const handleDownloadCsv = () => {
    if (!records.length) return;
    const headers = ['Student Name', 'Rollno', 'PRN', 'Lecture', 'Date & Time', 'Status'];
    const rows = records.map(r => [
      r.name,
      r.rollno,
      r.prn,
      r.lec_name,
      r.lecture_datetime ? new Date(r.lecture_datetime).toLocaleString() : '',
      r.status,
    ]);
    const csvContent = [headers, ...rows]
      .map(row => row.map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
      .join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `attendance-lec-${recLecId}.csv`);
    document.body.appendChild(link);
    link.click();
    link.parentNode.removeChild(link);
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
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Lecture</Label>
                  <Select value={selectedLecId} onValueChange={(val) => {
                    setSelectedLecId(val);
                    const dt = new Date();
                    const tzOffset = dt.getTimezoneOffset() * 60000;
                    const localISOTime = (new Date(dt - tzOffset)).toISOString().slice(0, 16);
                    setManualDatetime(localISOTime);
                  }}>
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
                          {lec.lec_name} — {lec.year} ({lec.specialisation}) — {lec.panel}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {selectedLecId && (
                  <div className="space-y-2 animate-in fade-in duration-300 slide-in-from-top-2">
                    <Label>Lecture Date & Time</Label>
                    <Input
                      type="datetime-local"
                      value={manualDatetime}
                      onChange={(e) => setManualDatetime(e.target.value)}
                      className="bg-white border-slate-300 w-full"
                    />
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Upload Card */}
        <Card className="border-0 shadow-xl bg-gradient-to-br from-purple-50 to-pink-100 flex flex-col">
          <CardHeader className="bg-white/70 backdrop-blur-sm rounded-t-lg">
            <CardTitle className="text-purple-800 flex items-center gap-2">
              <div className="bg-purple-600 text-white p-2 rounded-lg">
                <Camera className="h-5 w-5" />
              </div>
              Acquire Images
            </CardTitle>
            <CardDescription className="text-purple-600">Upload photos or capture directly</CardDescription>
          </CardHeader>
          <CardContent className="pt-4 flex-grow flex flex-col space-y-4">
            
            <div className="flex gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={handleFileChange}
              />
              <Button type="button" onClick={() => fileInputRef.current?.click()} className="flex-1 bg-white text-purple-700 hover:bg-purple-50 border border-purple-200">
                <UploadCloud className="mr-2 h-4 w-4" /> Upload
              </Button>
              <Button type="button" onClick={isCameraOpen ? stopCamera : startCamera} className="flex-1 bg-white text-purple-700 hover:bg-purple-50 border border-purple-200">
                <Camera className="mr-2 h-4 w-4" /> {isCameraOpen ? 'Close Camera' : 'Open Camera'}
              </Button>
            </div>

            {isCameraOpen && (
              <div className="relative rounded-lg overflow-hidden border-2 border-purple-300 bg-black align-center justify-center flex">
                 <video autoPlay playsInline ref={videoRef} className="w-full h-auto max-h-[300px]" />
                 <canvas ref={canvasRef} className="hidden" />
                 <Button type="button" onClick={captureImage} className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-purple-600 hover:bg-purple-700 rounded-full px-6 shadow-lg">
                   Capture Photo
                 </Button>
              </div>
            )}

            {selectedFiles.length > 0 && (
              <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 border border-purple-200 bg-white/50 p-2 rounded-lg max-h-[200px] overflow-y-auto">
                 {selectedFiles.map((file, idx) => (
                   <div key={idx} className="relative aspect-square rounded-md overflow-hidden group">
                     <img src={URL.createObjectURL(file)} alt="preview" className="w-full h-full object-cover" />
                     <button type="button" onClick={() => removeImage(idx)} className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity">
                       <X className="h-3 w-3" />
                     </button>
                   </div>
                 ))}
              </div>
            )}

            <form onSubmit={handleSubmit} className="mt-auto pt-2">
              <Button
                type="submit"
                className="w-full bg-indigo-600 hover:bg-indigo-700"
                disabled={loading || lecturesLoading || selectedFiles.length === 0}
              >
                {loading ? (
                  <>
                    <Activity className="mr-2 h-4 w-4 animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <Activity className="mr-2 h-4 w-4" />
                    Process Attendance ({selectedFiles.length})
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      {/* Attendance Records Section */}
      <Card className="border-0 shadow-xl">
        <CardHeader className="bg-gradient-to-r from-slate-800 to-indigo-900 rounded-t-lg">
          <CardTitle className="text-white flex items-center gap-2">
            <div className="bg-white/20 p-2 rounded-lg">
              <FileText className="h-5 w-5 text-white" />
            </div>
            View Attendance Records
          </CardTitle>
          <CardDescription className="text-slate-300">Select a lecture and optional date range to view and download records</CardDescription>
        </CardHeader>
        <CardContent className="pt-6 space-y-6">

          {/* Filters Row */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div className="space-y-2">
              <Label className="text-slate-700 font-medium">Lecture</Label>
              <Select value={recLecId} onValueChange={setRecLecId}>
                <SelectTrigger className="bg-white border-slate-300">
                  <SelectValue placeholder="Select lecture" />
                </SelectTrigger>
                <SelectContent className="bg-white border-slate-200">
                  {lectures.map((lec) => (
                    <SelectItem key={lec.lec_id} value={String(lec.lec_id)} className="cursor-pointer hover:bg-indigo-50">
                      {lec.lec_name} — {lec.year} ({lec.specialisation}) — {lec.panel}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-slate-700 font-medium">Date From</Label>
              <Input
                type="date"
                value={recDateFrom}
                onChange={e => setRecDateFrom(e.target.value)}
                className="bg-white border-slate-300"
              />
            </div>

            <div className="space-y-2">
              <Label className="text-slate-700 font-medium">Date To</Label>
              <Input
                type="date"
                value={recDateTo}
                onChange={e => setRecDateTo(e.target.value)}
                className="bg-white border-slate-300"
              />
            </div>

            <Button
              onClick={fetchRecords}
              disabled={recLoading || !recLecId}
              className="bg-indigo-600 hover:bg-indigo-700 w-full"
            >
              {recLoading ? <Activity className="mr-2 h-4 w-4 animate-spin" /> : <ChevronDown className="mr-2 h-4 w-4" />}
              {recLoading ? 'Loading...' : 'Fetch Records'}
            </Button>
          </div>

          {recError && (
            <Alert variant="destructive">
              <AlertDescription>{recError}</AlertDescription>
            </Alert>
          )}

          {/* Records Table */}
          {recFetched && (
            <div className="space-y-3 animate-in fade-in duration-300">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-500">
                  {records.length} record{records.length !== 1 ? 's' : ''} found
                  {records.length > 0 && <> &mdash; <span className="text-green-600 font-semibold">{records.filter(r => r.status === 'Present').length} Present</span> / <span className="text-red-600 font-semibold">{records.filter(r => r.status === 'Absent').length} Absent</span></>}
                </p>
                {records.length > 0 && (
                  <Button variant="outline" size="sm" onClick={handleDownloadCsv} className="gap-2">
                    <Download className="h-4 w-4" /> Download CSV
                  </Button>
                )}
              </div>

              {records.length === 0 ? (
                <div className="text-center py-10 text-slate-400">
                  <FileText className="mx-auto h-10 w-10 mb-3 opacity-40" />
                  <p>No attendance records found for the selected filters.</p>
                </div>
              ) : (
                <div className="rounded-md border border-slate-200 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 border-b border-slate-200">
                      <tr>
                        <th className="text-left px-4 py-3 font-semibold text-slate-600">Student Name</th>
                        <th className="text-left px-4 py-3 font-semibold text-slate-600">Rollno</th>
                        <th className="text-left px-4 py-3 font-semibold text-slate-600">PRN</th>
                        <th className="text-left px-4 py-3 font-semibold text-slate-600">Lecture</th>
                        <th className="text-left px-4 py-3 font-semibold text-slate-600">Date &amp; Time</th>
                        <th className="text-left px-4 py-3 font-semibold text-slate-600">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {records.map((r, idx) => (
                        <tr key={idx} className="hover:bg-slate-50 transition-colors">
                          <td className="px-4 py-3 font-medium text-slate-800">{r.name}</td>
                          <td className="px-4 py-3 text-slate-600">{r.rollno}</td>
                          <td className="px-4 py-3 font-mono text-slate-500 text-xs">{r.prn}</td>
                          <td className="px-4 py-3 text-slate-600">{r.lec_name}</td>
                          <td className="px-4 py-3 text-slate-500 text-xs">{formatDateTime(r.lecture_datetime)}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                              r.status === 'Present' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                            }`}>
                              {r.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
