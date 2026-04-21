import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CheckCircle, ArrowLeft, AlertTriangle, Download } from 'lucide-react';
import { finalizeAttendance, downloadCsv, getEnrolledStudents, resolveFaces } from '@/services/api';

export default function Results() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state;

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState([]);
  const [images, setImages] = useState([]);
  const [enrollForm, setEnrollForm] = useState({ prn: '', name: '', year: '', course: '', specialisation: '', rollno: '', panel: '' });

  const [finalizing, setFinalizing] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [error, setError] = useState('');

  // Dialog state
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState(null);

  useEffect(() => {
    if (!state) {
      setLoading(false);
      return;
    }

    const { lecId, identified_students = [], unidentified_faces = [] } = state;
    setImages(unidentified_faces);

    const loadData = async () => {
      try {
        const classList = await getEnrolledStudents(lecId);

        // Merge DB roster with model-detected present students
        const merged = classList.map((student) => {
          const found = identified_students.find(s => s.prn === student.prn);
          if (found) {
            return {
              ...student,
              confidence: found.similarity ? (found.similarity * 100).toFixed(1) : 100,
              status: 'Present'
            };
          }
          return { ...student, confidence: 0, status: 'Absent' };
        });

        // Push identified students not already in the enrolled roster
        identified_students.forEach(s => {
          if (!merged.find(m => m.prn === s.prn)) {
            merged.push({
              prn: s.prn,
              name: s.name,
              rollno: 'N/A',
              confidence: s.similarity ? (s.similarity * 100).toFixed(1) : 100,
              status: 'Present'
            });
          }
        });

        // Append unidentified faces as separate rows
        const unknownRows = unidentified_faces.map((f, idx) => ({
          prn: `unidentified-${f.face_id || idx}`,
          isUnidentified: true,
          face_id: f.face_id,
          image: f.image,
          name: 'Unknown Face',
          rollno: '-',
          confidence: '-',
          status: '-'
        }));

        setData([...merged, ...unknownRows]);
      } catch (err) {
        setError('Failed to fetch attendance data.');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [state]);

  if (!state) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <p className="text-slate-400 text-lg">No attendance data available.</p>
        <Button variant="outline" onClick={() => navigate('/dashboard')} className="bg-white/5 hover:bg-white/10 text-white border-white/10 shadow-lg backdrop-blur-md">
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
        </Button>
      </div>
    );
  }

  const { lecId } = state;
  const presentCount = data.filter(s => s.status === 'Present').length;
  const absentCount = data.filter(s => s.status === 'Absent').length;
  const totalCount = data.length;

  const handleUnknown = (student) => {
    setSelectedStudent(student);
    setEnrollForm({ prn: '', name: '', year: '', course: '', specialisation: '', rollno: '', panel: '' });
    setIsDialogOpen(true);
  };

  const handleReject = async (student) => {
    try {
      await resolveFaces(lecId, [{ face_id: student.face_id, action: 'discard' }]);
      setData(prev => prev.map(s => s.prn === student.prn ? { ...s, status: '-' } : s));
    } catch (err) {
      setError('Failed to reject face.');
    }
  };

  const handleCorrectToIdentified = (student) => {
    setData(prev => prev.map(s => s.prn === student.prn ? { ...s, status: 'Present' } : s));
  };

  const handleEnrollSubmit = async (e) => {
    e.preventDefault();
    try {
      await resolveFaces(lecId, [{
        face_id: selectedStudent.face_id,
        action: 'new',
        ...enrollForm
      }]);
      // Mutate this row structurally into a localized student format instantly
      setData(prev => prev.map(s => {
        if (s.prn === selectedStudent.prn) {
          return {
            prn: enrollForm.prn,
            name: enrollForm.name,
            rollno: enrollForm.rollno,
            confidence: '100',
            status: 'Present',
            isUnidentified: false
          };
        }
        return s;
      }));
      setIsDialogOpen(false);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to submit form');
    }
  };

  const handleApprove = async () => {
    setFinalizing(true);
    setError('');
    try {
      const prns = data.filter(s => s.status === 'Present').map(s => s.prn);
      const result = await finalizeAttendance(lecId, prns);
      setSuccessMsg(`${result.message} — CSV ready for download!`);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to approve attendance.');
    } finally {
      setFinalizing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500"></div>
        <p className="text-slate-400 font-medium">Fetching class list and analyzing results...</p>
      </div>
    );
  }

  return (
    <div className="relative min-h-[calc(100vh-2rem)] bg-[#0f1117] text-slate-200 p-4 sm:p-8 rounded-xl overflow-hidden font-sans shadow-2xl selection:bg-purple-500/30">
      {/* Background Effects */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-purple-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute top-[40%] right-[-10%] w-[30%] h-[40%] rounded-full bg-teal-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] left-[20%] w-[40%] h-[40%] rounded-full bg-indigo-600/10 blur-[120px] pointer-events-none" />

      <div className="relative space-y-6 animate-in fade-in duration-700 z-10 w-full max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-white/10">
          <div>
            <h2 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-purple-400 via-teal-400 to-indigo-400">
              Attendance Results
            </h2>
            <p className="text-slate-400 mt-2">Review and approve attendance for Lecture ID: <span className="font-semibold text-white">{lecId}</span></p>
          </div>
          <div className="flex gap-3">
            <Button variant="outline" onClick={() => navigate('/dashboard')} disabled={finalizing} className="bg-white/5 hover:bg-white/10 text-white border border-white/10 shadow-lg backdrop-blur-md transition-all duration-300">
              <ArrowLeft className="mr-2 h-4 w-4" /> Dashboard
            </Button>
            {!successMsg && (
              <Button onClick={handleApprove} disabled={finalizing} className="bg-indigo-600 hover:bg-indigo-500 text-white shadow-[0_0_15px_rgba(99,102,241,0.3)] border border-indigo-500/50 transition-all duration-300">
                {finalizing ? 'Approving...' : 'Approve Attendance'}
              </Button>
            )}
            {successMsg && (
              <Button
                onClick={async () => {
                  try {
                    const blob = await downloadCsv(lecId);
                    const url = window.URL.createObjectURL(new Blob([blob]));
                    const link = document.createElement('a');
                    link.href = url;
                    link.setAttribute('download', `lec-${lecId}-attendance.csv`);
                    document.body.appendChild(link);
                    link.click();
                    link.parentNode.removeChild(link);
                  } catch (e) {
                    setError('Failed to download CSV');
                  }
                }}
                className="bg-teal-600 hover:bg-teal-500 text-white shadow-[0_0_15px_rgba(20,184,166,0.3)] border border-teal-500/50 transition-all duration-300"
              >
                <Download className="mr-2 h-4 w-4" /> Download CSV
              </Button>
            )}
          </div>
        </div>

        {error && (
          <Alert variant="destructive" className="bg-red-500/10 border border-red-500/20 text-red-400">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {successMsg && (
          <Alert className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <CheckCircle className="h-4 w-4 text-emerald-400" />
            <AlertDescription className="ml-2">{successMsg}</AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.5fr] gap-8">
          {/* TOP LEFT: Summary Cards */}
          <div className="flex flex-col gap-5">
            <Card className="bg-white/5 border-white/10 backdrop-blur-xl shadow-xl relative overflow-hidden transition-all duration-300 hover:bg-white/[0.07] border-l-4 border-l-teal-500">
              <CardContent className="p-5 flex justify-between items-center">
                <div>
                  <p className="text-teal-400 text-sm font-semibold uppercase tracking-wider">Present</p>
                  <p className="text-4xl font-bold text-white mt-1">{presentCount}</p>
                </div>
                <div className="bg-teal-500/20 p-3 rounded-xl border border-teal-500/20 shadow-[0_0_15px_rgba(20,184,166,0.15)]">
                  <CheckCircle className="h-8 w-8 text-teal-400" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-white/5 border-white/10 backdrop-blur-xl shadow-xl relative overflow-hidden transition-all duration-300 hover:bg-white/[0.07] border-l-4 border-l-red-500">
              <CardContent className="p-5 flex justify-between items-center">
                <div>
                  <p className="text-red-400 text-sm font-semibold uppercase tracking-wider">Absent</p>
                  <p className="text-4xl font-bold text-white mt-1">{absentCount}</p>
                </div>
                <div className="bg-red-500/20 p-3 rounded-xl border border-red-500/20 shadow-[0_0_15px_rgba(239,68,68,0.15)]">
                  <AlertTriangle className="h-8 w-8 text-red-400" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-white/5 border-white/10 backdrop-blur-xl shadow-xl relative overflow-hidden transition-all duration-300 hover:bg-white/[0.07] border-l-4 border-l-purple-500">
              <CardContent className="p-5 flex justify-between items-center">
                <div>
                  <p className="text-purple-400 text-sm font-semibold uppercase tracking-wider">Total</p>
                  <p className="text-4xl font-bold text-white mt-1">{totalCount}</p>
                </div>
                <div className="bg-purple-500/20 p-3 rounded-xl border border-purple-500/20 shadow-[0_0_15px_rgba(168,85,247,0.15)] text-purple-400 flex font-bold w-14 h-14 items-center justify-center text-2xl">
                  ∑
                </div>
              </CardContent>
            </Card>
          </div>

          {/* TOP RIGHT: Processed Image Preview Section */}
          <div className="flex flex-col h-full">
            <Card className="bg-white/5 border-white/10 backdrop-blur-xl shadow-xl relative overflow-hidden transition-all duration-300 flex-1 flex flex-col min-h-[300px]">
              <CardHeader className="py-5 border-b border-white/5">
                <CardTitle className="text-white text-xl">Processed Captures</CardTitle>
                <CardDescription className="text-slate-400">Visuals parsed directly by the server bounding-box models</CardDescription>
              </CardHeader>
              <CardContent className="flex-1 overflow-y-auto max-h-[320px] pt-4">
                {images.length > 0 ? (
                  <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
                    {images.map((imgObj, idx) => (
                      <div key={imgObj.face_id ?? idx} className="flex flex-col items-center">
                        <img
                          src={`data:image/jpeg;base64,${imgObj.image}`}
                          alt={`Processed Result #${idx + 1}`}
                          className="w-full aspect-square object-cover rounded-lg border border-white/10 shadow-[0_4px_12px_rgba(0,0,0,0.5)] transition-transform hover:scale-105"
                        />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-slate-500">
                    <p>No model captures to display.</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* BOTTOM: Attendance Table */}
        <Card className="bg-white/5 border-white/10 backdrop-blur-xl shadow-xl relative overflow-hidden">
          <CardHeader className="border-b border-white/5 pb-4">
            <CardTitle className="text-white text-xl">Student Roster</CardTitle>
            <CardDescription className="text-slate-400">Verify system identification and manually correct if necessary prior to Approval.</CardDescription>
          </CardHeader>
          <CardContent className="pt-4 p-0 sm:p-6 sm:pt-4">
            <div className="rounded-md border border-white/10 overflow-hidden">
              <Table>
                <TableHeader className="bg-black/20 border-b border-white/10">
                  <TableRow className="border-b border-white/10 hover:bg-transparent">
                    <TableHead className="font-semibold text-slate-300">Student Name</TableHead>
                    <TableHead className="font-semibold text-slate-300">Rollno</TableHead>
                    <TableHead className="font-semibold text-slate-300">PRN</TableHead>
                    <TableHead className="font-semibold text-slate-300">Confidence</TableHead>
                    <TableHead className="font-semibold text-slate-300">Status</TableHead>
                    <TableHead className="text-right font-semibold text-slate-300">Feedback</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.map((s) => (
                    <TableRow key={s.prn} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar className="h-9 w-9 border border-[#0f1117] shadow-lg">
                            {s.isUnidentified ? (
                              <img src={`data:image/jpeg;base64,${s.image}`} alt="Unknown" className="w-full h-full object-cover" />
                            ) : (
                              <AvatarFallback className="bg-indigo-500/20 text-indigo-300 text-xs font-semibold">
                                {s.name ? s.name.substring(0, 2).toUpperCase() : 'NA'}
                              </AvatarFallback>
                            )}
                          </Avatar>
                          <span className="font-medium text-white">{s.name}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-slate-300">{s.rollno}</TableCell>
                      <TableCell className="font-mono text-sm text-slate-400">{s.prn}</TableCell>
                      <TableCell>
                        {s.confidence > 0 ? (
                          <span className={`font-semibold ${s.confidence < 70 ? 'text-amber-400' : 'text-teal-400'}`}>
                            {s.confidence}%
                          </span>
                        ) : (
                          <span className="text-slate-500">N/A</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${s.status === 'Present' ? 'bg-teal-500/10 text-teal-400 border-teal-500/20 shadow-[0_0_10px_rgba(20,184,166,0.1)]' : s.status === 'Absent' ? 'bg-red-500/10 text-red-400 border-red-500/20 shadow-[0_0_10px_rgba(239,68,68,0.1)]' : 'bg-slate-500/10 text-slate-400 border-slate-500/20'}`}>
                          {s.status}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        {s.isUnidentified ? (
                          <div className="flex gap-2 justify-end">
                            <Button variant="outline" size="sm" onClick={() => handleUnknown(s)} disabled={s.status !== '-'} className="h-8 bg-black/20 hover:bg-black/40 text-white border-white/20">Unknown</Button>
                            <Button variant="ghost" size="sm" onClick={() => handleReject(s)} disabled={s.status !== '-'} className="h-8 text-red-400 hover:text-red-300 hover:bg-red-500/20">Rejected</Button>
                          </div>
                        ) : (
                          <span className={`font-semibold text-sm ${s.status === 'Present' ? 'text-teal-400' : 'text-slate-500'}`}>
                            {s.status === 'Present' ? 'Identified' : '—'}
                          </span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        {/* Correction Dialog */}
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogContent className="sm:max-w-[500px] bg-[#0f1117] border border-white/10 text-slate-200 shadow-2xl">
            <DialogHeader>
              <DialogTitle className="text-white text-xl">Manage Student Enrollment</DialogTitle>
            </DialogHeader>
            <div className="py-4">
              <p className="text-sm text-slate-400 mb-5">You are registering an unidentified face. Fill out the registry form to mark present.</p>
              <form onSubmit={handleEnrollSubmit} className="grid grid-cols-2 gap-4">
                <div className="col-span-2 space-y-1.5">
                  <Label className="text-slate-300 text-xs uppercase tracking-wider">Student Full Name</Label>
                  <Input required value={enrollForm.name} onChange={e => setEnrollForm({ ...enrollForm, name: e.target.value })} placeholder="Jane Doe" className="bg-black/20 border-white/10 text-white focus-visible:ring-indigo-500 placeholder:text-slate-600 h-10" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-xs uppercase tracking-wider">PRN</Label>
                  <Input required value={enrollForm.prn} onChange={e => setEnrollForm({ ...enrollForm, prn: e.target.value })} placeholder="Unique ID" className="bg-black/20 border-white/10 text-white focus-visible:ring-indigo-500 placeholder:text-slate-600 h-10" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-xs uppercase tracking-wider">Rollno</Label>
                  <Input required value={enrollForm.rollno} onChange={e => setEnrollForm({ ...enrollForm, rollno: e.target.value })} placeholder="Roll Number" className="bg-black/20 border-white/10 text-white focus-visible:ring-indigo-500 placeholder:text-slate-600 h-10" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-xs uppercase tracking-wider">Year</Label>
                  <Input required value={enrollForm.year} onChange={e => setEnrollForm({ ...enrollForm, year: e.target.value })} placeholder="1st Year" className="bg-black/20 border-white/10 text-white focus-visible:ring-indigo-500 placeholder:text-slate-600 h-10" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-xs uppercase tracking-wider">Course</Label>
                  <Input required value={enrollForm.course} onChange={e => setEnrollForm({ ...enrollForm, course: e.target.value })} placeholder="B.Tech" className="bg-black/20 border-white/10 text-white focus-visible:ring-indigo-500 placeholder:text-slate-600 h-10" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-xs uppercase tracking-wider">Specialisation</Label>
                  <Input required value={enrollForm.specialisation} onChange={e => setEnrollForm({ ...enrollForm, specialisation: e.target.value })} placeholder="Computer Science" className="bg-black/20 border-white/10 text-white focus-visible:ring-indigo-500 placeholder:text-slate-600 h-10" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-xs uppercase tracking-wider">Panel</Label>
                  <Input required value={enrollForm.panel} onChange={e => setEnrollForm({ ...enrollForm, panel: e.target.value })} placeholder="Panel A" className="bg-black/20 border-white/10 text-white focus-visible:ring-indigo-500 placeholder:text-slate-600 h-10" />
                </div>
                <div className="col-span-2 mt-5 flex gap-4">
                  <Button type="button" variant="outline" className="flex-1 bg-white/5 hover:bg-white/10 text-white border-white/10 border" onClick={() => setIsDialogOpen(false)}>Cancel</Button>
                  <Button type="submit" className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white border border-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.2)]">Submit & Mark Present</Button>
                </div>
              </form>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
