import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { UploadCloud, Activity, Users, BookOpen, Camera, X, FileText, ChevronDown, Download, CheckCircle, XCircle } from 'lucide-react';
import { getLectures, markAttendance, getAttendanceRecords, getTodayLectures } from '@/services/api';

export default function Dashboard() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [lectures, setLectures] = useState([]);
  const [todayLectures, setTodayLectures] = useState([]);
  const [lecturesLoading, setLecturesLoading] = useState(true);
  const [selectedLecId, setSelectedLecId] = useState('');
  const [activeTab, setActiveTab] = useState('today');
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
    Promise.all([
      getLectures().catch(() => []),
      getTodayLectures().catch(() => [])
    ]).then(([allLecs, todayLecs]) => {
      setLectures(allLecs || []);
      setTodayLectures(todayLecs || []);

      // Auto-select the pending lecture closest to the current time
      if (todayLecs && todayLecs.length > 0) {
        const now = new Date();
        let closestLec = null;
        let smallestDiff = Infinity;

        todayLecs.forEach(lec => {
          if (lec.attendance_status === 'Y') return; // skip completed
          const lecTime = new Date(lec.lecture_datetime);
          const durationHrs = lec.lecorlab === 'lab' ? 2 : 1;
          const lecEndTime = new Date(lecTime.getTime() + durationHrs * 60 * 60 * 1000);
          const diff = Math.abs(now - lecEndTime);
          if (diff < smallestDiff) {
            smallestDiff = diff;
            closestLec = lec;
          }
        });

        // Fallback to first PENDING lecture, or nothing if all completed
        if (!closestLec) {
          const firstPending = todayLecs.find(l => l.attendance_status !== 'Y');
          if (firstPending) closestLec = firstPending;
          // If all completed, don't auto-select anything
        }
        if (closestLec) setSelectedLecId(String(closestLec.lec_id));
      }
    }).catch(() => {
      setError('Failed to load lectures.');
      setLectures([]);
      setTodayLectures([]);
    }).finally(() => {
      setLecturesLoading(false);
    });
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
    if (!selectedLecId) { setError('Please select a lecture first.'); return; }
    if (selectedFiles.length === 0) { setError('Please select at least one image.'); return; }

    // Check if selected lecture is already finalized
    const allLecs = [...todayLectures, ...pastPendingLectures];
    const selectedLec = allLecs.find(l => String(l.lec_id) === String(selectedLecId));
    if (selectedLec && selectedLec.attendance_status === 'Y') {
      setError('This lecture has already been finalized. Select a different lecture.');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const base64Images = await Promise.all(selectedFiles.map(toBase64));
      const result = await markAttendance(parseInt(selectedLecId), base64Images, null);
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

  // Lectures that are not today and still pending — shown in "Past Pending" tab
  const pastPendingLectures = lectures.filter(lec =>
    lec.attendance_status !== 'Y' &&
    !todayLectures.some(tLec => tLec.lec_id === lec.lec_id)
  );

  return (
    <div className="relative min-h-[calc(100vh-2rem)] bg-slate-50 dark:bg-[#0f1117] text-slate-800 dark:text-slate-200 p-4 sm:p-8 rounded-xl overflow-hidden font-sans shadow-2xl selection:bg-blue-500/30">
      {/* Background Effects */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-blue-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute top-[40%] right-[-10%] w-[30%] h-[40%] rounded-full bg-indigo-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] left-[20%] w-[40%] h-[40%] rounded-full bg-purple-600/10 blur-[120px] pointer-events-none" />

      <div className="relative space-y-8 animate-in fade-in duration-700 z-10 w-full max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-slate-300 dark:border-white/10">
          <div>
            <h2 className="text-4xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 mb-2">
              Faculty Dashboard
            </h2>
            <p className="text-slate-600 dark:text-slate-400 text-lg">
              Welcome back, <span className="font-semibold text-blue-300">{userName}</span>
            </p>
          </div>
          {(role === '1' || role === '2') && (
            <Button onClick={() => navigate('/admin-students')} className="bg-white dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-slate-900 dark:text-white border border-slate-300 dark:border-white/10 shadow-lg backdrop-blur-md transition-all duration-300">
              <Users className="mr-2 h-4 w-4 text-blue-400" />
              Manage Students
            </Button>
          )}
        </div>

        {error && (
          <Alert variant="destructive" className="bg-red-500/10 border border-red-500/20 text-red-400">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="grid gap-8 lg:grid-cols-2">
          {/* Lecture Selection Card */}
          <Card className="bg-white dark:bg-white/5 border-slate-300 dark:border-white/10 backdrop-blur-xl shadow-xl hover:bg-slate-100 dark:hover:bg-white/[0.07] transition-all duration-300 flex flex-col relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-[50px] pointer-events-none" />
            <CardHeader className="border-b border-slate-200 dark:border-white/5 pb-4">
              <CardTitle className="text-slate-900 dark:text-white flex items-center gap-3">
                <div className="bg-blue-500/20 text-blue-400 p-2.5 rounded-lg border border-blue-500/20 shadow-[0_0_15px_rgba(59,130,246,0.15)]">
                  <BookOpen className="h-5 w-5" />
                </div>
                Lecture Configuration
              </CardTitle>
              <CardDescription className="text-slate-600 dark:text-slate-400 pt-1">Select the lecture to initialize attendance marking.</CardDescription>
            </CardHeader>
            <CardContent className="pt-6 flex-1">
              {lecturesLoading ? (
                <div className="flex justify-center items-center h-40">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                </div>
              ) : todayLectures.length === 0 && pastPendingLectures.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-8 text-slate-500 text-center">
                  <BookOpen className="h-10 w-10 mb-3 opacity-20" />
                  <p>No pending classes to mark.</p>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Today / Past-Pending tabs */}
                  <div className="flex bg-slate-200 dark:bg-black/40 p-1 rounded-lg">
                    <button
                      onClick={() => {
                        setActiveTab('today');
                        const first = todayLectures.find(l => l.attendance_status !== 'Y') || todayLectures[0];
                        if (first) setSelectedLecId(String(first.lec_id));
                      }}
                      className={`flex-1 text-xs font-bold uppercase tracking-wider py-2 rounded-md transition-all ${
                        activeTab === 'today'
                          ? 'bg-blue-500 text-white shadow'
                          : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                      }`}
                    >
                      Today's Classes
                    </button>
                    <button
                      onClick={() => {
                        setActiveTab('past');
                        if (pastPendingLectures[0]) setSelectedLecId(String(pastPendingLectures[0].lec_id));
                      }}
                      className={`flex-1 text-xs font-bold uppercase tracking-wider py-2 rounded-md transition-all ${
                        activeTab === 'past'
                          ? 'bg-amber-500 text-white shadow'
                          : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                      }`}
                    >
                      Past Pending
                    </button>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Select Lecture</Label>

                    {activeTab === 'today' && todayLectures.length === 0 ? (
                      <div className="bg-slate-100 dark:bg-white/5 border border-slate-300 dark:border-white/10 rounded-lg p-6 text-center text-slate-500 flex flex-col items-center justify-center min-h-[120px]">
                        <BookOpen className="h-6 w-6 mb-2 opacity-30" />
                        No classes scheduled for today.
                      </div>
                    ) : activeTab === 'past' && pastPendingLectures.length === 0 ? (
                      <div className="bg-slate-100 dark:bg-white/5 border border-slate-300 dark:border-white/10 rounded-lg p-6 text-center text-slate-500 flex flex-col items-center justify-center min-h-[120px]">
                        <CheckCircle className="h-6 w-6 mb-2 text-emerald-500 opacity-60" />
                        No past pending classes. You're all caught up!
                      </div>
                    ) : (
                      <Select value={selectedLecId} onValueChange={setSelectedLecId}>
                        <SelectTrigger className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus:ring-blue-500 h-12">
                          <SelectValue placeholder="Choose a lecture..." />
                        </SelectTrigger>
                        <SelectContent className="bg-slate-900 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white">
                          {activeTab === 'today' ? (
                            todayLectures.map((lec) => {
                              const timeStr = new Date(lec.lecture_datetime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                              const done = lec.attendance_status === 'Y';
                              return (
                                <SelectItem
                                  key={`today-${lec.lec_id}`}
                                  value={String(lec.lec_id)}
                                  disabled={done}
                                  className={`cursor-pointer font-semibold ${done ? 'opacity-40 cursor-not-allowed' : 'hover:bg-slate-200 dark:hover:bg-white/10 focus:bg-white/10'}`}
                                >
                                  <span className={done ? 'text-slate-500 mr-2' : 'text-emerald-400 mr-2'}>[{timeStr}]</span>
                                  <span className={done ? 'line-through text-slate-500' : ''}>
                                    {lec.lec_name} — {lec.year} ({lec.specialisation}) — Panel {lec.panel}
                                  </span>
                                  {done && <span className="ml-2 text-emerald-500 text-xs font-bold uppercase">✓ Done</span>}
                                </SelectItem>
                              );
                            })
                          ) : (
                            pastPendingLectures.map((lec) => {
                              const timeStr = new Date(lec.lecture_datetime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                              const dateStr = new Date(lec.lecture_datetime).toLocaleDateString([], { month: 'short', day: 'numeric' });
                              return (
                                <SelectItem
                                  key={`past-${lec.lec_id}`}
                                  value={String(lec.lec_id)}
                                  className="cursor-pointer hover:bg-slate-200 dark:hover:bg-white/10 focus:bg-white/10 font-semibold"
                                >
                                  <span className="text-amber-400 mr-2">[{dateStr} {timeStr}]</span>
                                  {lec.lec_name} — {lec.year} ({lec.specialisation}) — Panel {lec.panel}
                                </SelectItem>
                              );
                            })
                          )}
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Upload Card */}
          <Card className="bg-white dark:bg-white/5 border-slate-300 dark:border-white/10 backdrop-blur-xl shadow-xl hover:bg-slate-100 dark:hover:bg-white/[0.07] transition-all duration-300 flex flex-col relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/10 rounded-full blur-[50px] pointer-events-none" />
            <CardHeader className="border-b border-slate-200 dark:border-white/5 pb-4">
              <CardTitle className="text-slate-900 dark:text-white flex items-center gap-3">
                <div className="bg-purple-500/20 text-purple-400 p-2.5 rounded-lg border border-purple-500/20 shadow-[0_0_15px_rgba(168,85,247,0.15)]">
                  <Camera className="h-5 w-5" />
                </div>
                Acquire Proof
              </CardTitle>
              <CardDescription className="text-slate-600 dark:text-slate-400 pt-1">Upload images or activate the camera to capture attendance.</CardDescription>
            </CardHeader>
            <CardContent className="pt-6 flex-grow flex flex-col space-y-6">

              <div className="flex gap-4">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={handleFileChange}
                />
                <Button type="button" onClick={() => fileInputRef.current?.click()} className="flex-1 bg-slate-200 dark:bg-white/10 hover:bg-slate-300 dark:hover:bg-white/20 text-slate-900 dark:text-white border border-slate-300 dark:border-white/10 shadow-lg h-12 transition-all">
                  <UploadCloud className="mr-2 h-4 w-4 text-indigo-400" /> Upload Images
                </Button>
                <Button type="button" onClick={isCameraOpen ? stopCamera : startCamera} className={`flex-1 h-12 transition-all shadow-lg ${isCameraOpen ? 'bg-red-500/20 hover:bg-red-500/30 text-slate-900 dark:text-white border border-red-500/30' : 'bg-slate-200 dark:bg-white/10 hover:bg-slate-300 dark:hover:bg-white/20 text-slate-900 dark:text-white border border-slate-300 dark:border-white/10'}`}>
                  {isCameraOpen ? <X className="mr-2 h-4 w-4 text-red-400" /> : <Camera className="mr-2 h-4 w-4 text-indigo-400" />}
                  {isCameraOpen ? 'Close Camera' : 'Live Camera'}
                </Button>
              </div>

              {isCameraOpen && (
                <div className="relative rounded-xl overflow-hidden border border-slate-300 dark:border-white/10 bg-slate-200 dark:bg-black/50 shadow-2xl animate-in zoom-in-95 duration-300">
                  <video autoPlay playsInline ref={videoRef} className="w-full h-auto max-h-[350px] object-cover" />
                  <canvas ref={canvasRef} className="hidden" />
                  <Button type="button" onClick={captureImage} className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-purple-600 hover:bg-purple-500 text-slate-900 dark:text-white rounded-full px-8 shadow-[0_0_20px_rgba(168,85,247,0.4)] border border-purple-400/50">
                    <Camera className="mr-2 h-4 w-4" /> Snap Photo
                  </Button>
                </div>
              )}

              {selectedFiles.length > 0 && (
                <div className="grid grid-cols-4 gap-3 bg-white dark:bg-black/20 border border-slate-200 dark:border-white/5 p-3 rounded-xl max-h-[200px] overflow-y-auto custom-scrollbar animate-in fade-in">
                  {selectedFiles.map((file, idx) => (
                    <div key={idx} className="relative aspect-square rounded-lg overflow-hidden group shadow-lg border border-slate-300 dark:border-white/10">
                      <img src={URL.createObjectURL(file)} alt="preview" className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" />
                      <div className="absolute inset-0 bg-slate-50 dark:bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <button type="button" onClick={() => removeImage(idx)} className="bg-red-500/80 hover:bg-red-500 text-slate-900 dark:text-white rounded-full p-2 backdrop-blur-sm transform transition hover:scale-110">
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <form onSubmit={handleSubmit} className="mt-auto">
                {(() => {
                  const allLecs = [...todayLectures, ...pastPendingLectures];
                  const selLec = allLecs.find(l => String(l.lec_id) === String(selectedLecId));
                  const isFinalized = selLec?.attendance_status === 'Y';
                  const noLec = !selectedLecId;
                  const btnDisabled = loading || lecturesLoading || selectedFiles.length === 0 || noLec || isFinalized;
                  return (
                    <Button
                      type="submit"
                      className={`w-full h-12 border transition-all duration-300 font-medium text-lg ${
                        isFinalized
                          ? 'bg-slate-400 dark:bg-slate-600 border-slate-400 text-slate-200 cursor-not-allowed opacity-60'
                          : noLec
                          ? 'bg-slate-400 dark:bg-slate-600 border-slate-400 text-slate-200 cursor-not-allowed opacity-60'
                          : 'bg-blue-600 hover:bg-blue-500 text-slate-900 dark:text-white shadow-[0_0_20px_rgba(37,99,235,0.3)] border-blue-500/50'
                      }`}
                      disabled={btnDisabled}
                    >
                      {loading ? (
                        <><Activity className="mr-2 h-5 w-5 animate-spin" /> Processing AI Recognition...</>
                      ) : isFinalized ? (
                        <><Activity className="mr-2 h-5 w-5 opacity-50" /> Lecture Already Finalized</>
                      ) : noLec ? (
                        <><Activity className="mr-2 h-5 w-5 opacity-50" /> Select a Lecture First</>
                      ) : (
                        <><Activity className="mr-2 h-5 w-5" /> Process Attendance ({selectedFiles.length} photos)</>
                      )}
                    </Button>
                  );
                })()}
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Attendance Records Section */}
        <Card className="bg-white dark:bg-[#1a1d27] border border-slate-300 dark:border-white/10 shadow-2xl relative overflow-hidden">
          <CardHeader className="bg-white dark:bg-black/20 border-b border-slate-200 dark:border-white/5 pb-5">
            <CardTitle className="text-slate-900 dark:text-white flex items-center gap-3">
              <div className="bg-indigo-500/20 text-indigo-400 p-2 rounded-lg border border-indigo-500/20">
                <FileText className="h-5 w-5" />
              </div>
              Archive & Logs
            </CardTitle>
            <CardDescription className="text-slate-600 dark:text-slate-400 pt-1">Query historical attendance metrics, export records, and cross-reference dates.</CardDescription>
          </CardHeader>
          <CardContent className="pt-6 space-y-6">

            {/* Filters Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-5 items-end">
              <div className="space-y-2">
                <Label className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Lecture Target</Label>
                <Select value={recLecId} onValueChange={setRecLecId}>
                  <SelectTrigger className="bg-slate-100 dark:bg-black/30 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus:ring-indigo-500 h-11">
                    <SelectValue placeholder="Select context" />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-900 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white">
                    {lectures.map((lec) => (
                      <SelectItem key={lec.lec_id} value={String(lec.lec_id)} className="cursor-pointer hover:bg-slate-200 dark:hover:bg-white/10">
                        {lec.lec_name} — {lec.year} ({lec.specialisation}) — {lec.panel}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Start Date</Label>
                <Input
                  type="date"
                  value={recDateFrom}
                  onChange={e => setRecDateFrom(e.target.value)}
                  className="bg-slate-100 dark:bg-black/30 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-indigo-500 h-11 [color-scheme:dark]"
                />
              </div>

              <div className="space-y-2">
                <Label className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">End Date</Label>
                <Input
                  type="date"
                  value={recDateTo}
                  onChange={e => setRecDateTo(e.target.value)}
                  className="bg-slate-100 dark:bg-black/30 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-indigo-500 h-11 [color-scheme:dark]"
                />
              </div>

              <Button
                onClick={fetchRecords}
                disabled={recLoading || !recLecId}
                className="bg-slate-200 dark:bg-white/10 hover:bg-slate-300 dark:hover:bg-white/20 text-slate-900 dark:text-white border border-slate-300 dark:border-white/10 h-11 shadow-lg backdrop-blur-md"
              >
                {recLoading ? <Activity className="mr-2 h-4 w-4 animate-spin" /> : <ChevronDown className="mr-2 h-4 w-4 text-indigo-400" />}
                {recLoading ? 'Extracting...' : 'Fetch Logs'}
              </Button>
            </div>

            {recError && (
              <Alert variant="destructive" className="bg-red-500/10 border border-red-500/20 text-red-400">
                <AlertDescription>{recError}</AlertDescription>
              </Alert>
            )}

            {/* Records Table */}
            {recFetched && (
              <div className="space-y-4 animate-in fade-in duration-500">
                <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-white dark:bg-black/20 border border-slate-200 dark:border-white/5">
                  <p className="text-sm text-slate-600 dark:text-slate-400">
                    <strong className="text-slate-900 dark:text-white text-lg">{records.length}</strong> record{records.length !== 1 ? 's' : ''} retrieved
                    {records.length > 0 && (
                      <span className="ml-3 border-l border-slate-300 dark:border-white/10 pl-3">
                        <span className="text-emerald-400 font-semibold">{records.filter(r => r.status === 'Present').length} Present</span> <span className="text-slate-500 mx-1">•</span> <span className="text-rose-400 font-semibold">{records.filter(r => r.status === 'Absent').length} Absent</span>
                      </span>
                    )}
                  </p>
                  {records.length > 0 && (
                    <Button variant="outline" size="sm" onClick={handleDownloadCsv} className="bg-slate-50 dark:bg-black/40 hover:bg-black/60 text-indigo-300 border-indigo-500/30 gap-2">
                      <Download className="h-4 w-4" /> Export CSV
                    </Button>
                  )}
                </div>

                {records.length === 0 ? (
                  <div className="text-center py-16 text-slate-500 bg-slate-50 dark:bg-black/10 rounded-xl border border-slate-200 dark:border-white/5">
                    <FileText className="mx-auto h-12 w-12 mb-4 opacity-20" />
                    <p className="text-lg">No logs found matching your criteria.</p>
                  </div>
                ) : (
                  <div className="rounded-xl border border-slate-300 dark:border-white/10 overflow-hidden bg-white dark:bg-black/20 shadow-inner">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-slate-50 dark:bg-black/40 border-b border-slate-300 dark:border-white/10">
                        <tr>
                          <th className="px-5 py-4 font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider text-xs">Scholar Identity</th>
                          <th className="px-5 py-4 font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider text-xs">Credentials</th>
                          <th className="px-5 py-4 font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider text-xs">Lecture Target</th>
                          <th className="px-5 py-4 font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider text-xs">Timestamp</th>
                          <th className="px-5 py-4 font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider text-xs w-32">Status Check</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {records.map((r, idx) => (
                          <tr key={idx} className="hover:bg-slate-100 dark:hover:bg-white/5 transition-colors duration-200">
                            <td className="px-5 py-4">
                              <span className="font-semibold text-slate-800 dark:text-slate-200 block">{r.name}</span>
                            </td>
                            <td className="px-5 py-4">
                              <span className="text-slate-700 dark:text-slate-300 font-mono block">{r.rollno}</span>
                              <span className="text-slate-500 font-mono text-[10px] mt-0.5 block">{r.prn}</span>
                            </td>
                            <td className="px-5 py-4 text-slate-700 dark:text-slate-300">{r.lec_name}</td>
                            <td className="px-5 py-4 text-slate-600 dark:text-slate-400 text-xs bg-white dark:bg-black/20 rounded-md my-2 mr-4 inline-block px-2 py-1 shadow-sm border border-slate-200 dark:border-white/5">{formatDateTime(r.lecture_datetime)}</td>
                            <td className="px-5 py-4">
                              {r.status === 'Present' ?
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.1)]"><CheckCircle className="w-3 h-3" /> Present</span> :
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider bg-rose-500/10 text-rose-400 border border-rose-500/20 shadow-[0_0_10px_rgba(244,63,94,0.1)]"><XCircle className="w-3 h-3" /> Absent</span>
                              }
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
    </div>
  );
}
