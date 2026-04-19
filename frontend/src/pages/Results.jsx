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
        <p className="text-slate-500 text-lg">No attendance data available.</p>
        <Button variant="outline" onClick={() => navigate('/dashboard')}>
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
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        <p className="text-slate-500 font-medium">Fetching class list and analyzing results...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-10">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold text-slate-800">Attendance Results</h2>
          <p className="text-slate-600 mt-1">Review and approve attendance for Lecture ID: {lecId}</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => navigate('/dashboard')} disabled={finalizing}>
            <ArrowLeft className="mr-2 h-4 w-4" /> Dashboard
          </Button>
          {!successMsg && (
            <Button onClick={handleApprove} disabled={finalizing} className="bg-indigo-600 hover:bg-indigo-700">
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
              className="bg-green-600 hover:bg-green-700 font-semibold"
            >
              <Download className="mr-2 h-4 w-4" /> Download CSV
            </Button>
          )}
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {successMsg && (
        <Alert className="border-green-300 bg-green-50">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-700 ml-2">{successMsg}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.5fr] gap-6">
        {/* TOP LEFT: Summary Cards */}
        <div className="flex flex-col gap-4">
          <Card className="border-0 shadow-sm bg-green-50 border-l-4 border-green-500">
            <CardContent className="p-4 flex justify-between items-center">
              <div>
                <p className="text-green-700 text-sm font-semibold uppercase">Present</p>
                <p className="text-3xl font-bold text-green-800">{presentCount}</p>
              </div>
              <div className="bg-green-200 p-3 rounded-full">
                <CheckCircle className="h-6 w-6 text-green-700" />
              </div>
            </CardContent>
          </Card>

          <Card className="border-0 shadow-sm bg-red-50 border-l-4 border-red-500">
            <CardContent className="p-4 flex justify-between items-center">
              <div>
                <p className="text-red-700 text-sm font-semibold uppercase">Absent</p>
                <p className="text-3xl font-bold text-red-800">{absentCount}</p>
              </div>
              <div className="bg-red-200 p-3 rounded-full">
                <AlertTriangle className="h-6 w-6 text-red-700" />
              </div>
            </CardContent>
          </Card>

          <Card className="border-0 shadow-sm bg-blue-50 border-l-4 border-blue-500">
            <CardContent className="p-4 flex justify-between items-center">
              <div>
                <p className="text-blue-700 text-sm font-semibold uppercase">Total</p>
                <p className="text-3xl font-bold text-blue-800">{totalCount}</p>
              </div>
              <div className="bg-blue-200 p-3 rounded-full text-blue-700 flex font-bold w-12 h-12 items-center justify-center">
                ∑
              </div>
            </CardContent>
          </Card>
        </div>

        {/* TOP RIGHT: Processed Image Preview Section */}
        <div className="flex flex-col h-full">
          <Card className="border-0 shadow-xl flex-1 flex flex-col min-h-[300px]">
            <CardHeader className="py-4">
              <CardTitle className="text-slate-800 text-lg">Processed Captures</CardTitle>
              <CardDescription>Visuals parsed directly by the server bounding-box models</CardDescription>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto max-h-[300px]">
              {images.length > 0 ? (
                <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
                  {images.map((imgObj, idx) => (
                    <div key={imgObj.face_id ?? idx} className="flex flex-col items-center">
                      <img
                        src={`data:image/jpeg;base64,${imgObj.image}`}
                        alt={`Processed Result #${idx + 1}`}
                        className="w-full aspect-square object-cover rounded-lg border border-slate-200 shadow-sm"
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-slate-400">
                  <p>No model captures to display.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* BOTTOM: Attendance Table */}
      <Card className="border-0 shadow-xl">
        <CardHeader>
          <CardTitle className="text-slate-800">Student Roster</CardTitle>
          <CardDescription>Verify system identification and manually correct if necessary prior to Approval.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border border-slate-200 overflow-hidden">
            <Table>
              <TableHeader className="bg-slate-50">
                <TableRow>
                  <TableHead>Student Name</TableHead>
                  <TableHead>Rollno</TableHead>
                  <TableHead>PRN</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Feedback</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((s) => (
                  <TableRow key={s.prn}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <Avatar className="h-8 w-8">
                          {s.isUnidentified ? (
                            <img src={`data:image/jpeg;base64,${s.image}`} alt="Unknown" className="w-full h-full object-cover" />
                          ) : (
                            <AvatarFallback className="bg-slate-100 text-slate-600 text-xs font-semibold">
                              {s.name ? s.name.substring(0, 2).toUpperCase() : 'NA'}
                            </AvatarFallback>
                          )}
                        </Avatar>
                        <span className="font-medium text-slate-800">{s.name}</span>
                      </div>
                    </TableCell>
                    <TableCell>{s.rollno}</TableCell>
                    <TableCell className="font-mono text-sm">{s.prn}</TableCell>
                    <TableCell>
                      {s.confidence > 0 ? (
                        <span className={`font-semibold ${s.confidence < 70 ? 'text-amber-600' : 'text-green-600'}`}>
                          {s.confidence}%
                        </span>
                      ) : (
                        <span className="text-slate-400">N/A</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className={`px-2 py-1 rounded-full text-xs font-semibold ${s.status === 'Present' ? 'bg-green-100 text-green-700' : s.status === 'Absent' ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-700'}`}>
                        {s.status}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      {s.isUnidentified ? (
                        <div className="flex gap-2 justify-end">
                          <Button variant="outline" size="sm" onClick={() => handleUnknown(s)} disabled={s.status !== '-'} className="h-8">Unknown</Button>
                          <Button variant="ghost" size="sm" onClick={() => handleReject(s)} disabled={s.status !== '-'} className="h-8 text-red-600 hover:text-red-700">Rejected</Button>
                        </div>
                      ) : (
                        <span className={`font-semibold text-sm ${s.status === 'Present' ? 'text-green-600' : 'text-slate-400'}`}>
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
        <DialogContent className="sm:max-w-[500px] bg-white text-slate-800">
          <DialogHeader>
            <DialogTitle>Manage Student Enrollment</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p className="text-sm text-slate-500 mb-4">You are registering an unidentified face. Fill out the registry form to mark present.</p>
            <form onSubmit={handleEnrollSubmit} className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <Label>Student Full Name</Label>
                <Input required value={enrollForm.name} onChange={e => setEnrollForm({ ...enrollForm, name: e.target.value })} placeholder="Jane Doe" />
              </div>
              <div>
                <Label>PRN</Label>
                <Input required value={enrollForm.prn} onChange={e => setEnrollForm({ ...enrollForm, prn: e.target.value })} placeholder="Unique ID" />
              </div>
              <div>
                <Label>Rollno</Label>
                <Input required value={enrollForm.rollno} onChange={e => setEnrollForm({ ...enrollForm, rollno: e.target.value })} placeholder="Roll Number" />
              </div>
              <div>
                <Label>Year</Label>
                <Input required value={enrollForm.year} onChange={e => setEnrollForm({ ...enrollForm, year: e.target.value })} placeholder="1st Year" />
              </div>
              <div>
                <Label>Course</Label>
                <Input required value={enrollForm.course} onChange={e => setEnrollForm({ ...enrollForm, course: e.target.value })} placeholder="B.Tech" />
              </div>
              <div>
                <Label>Specialisation</Label>
                <Input required value={enrollForm.specialisation} onChange={e => setEnrollForm({ ...enrollForm, specialisation: e.target.value })} placeholder="Computer Science" />
              </div>
              <div>
                <Label>Panel</Label>
                <Input required value={enrollForm.panel} onChange={e => setEnrollForm({ ...enrollForm, panel: e.target.value })} placeholder="Panel A" />
              </div>
              <div className="col-span-2 mt-4 flex gap-4">
                <Button type="button" variant="outline" className="flex-1" onClick={() => setIsDialogOpen(false)}>Cancel</Button>
                <Button type="submit" className="flex-1 bg-indigo-600 hover:bg-indigo-700">Submit & Mark Present</Button>
              </div>
            </form>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
