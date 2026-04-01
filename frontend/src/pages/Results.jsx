import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CheckCircle, ArrowLeft } from 'lucide-react';
import { finalizeAttendance } from '@/services/api';

export default function Results() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state;

  const [finalizing, setFinalizing] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [error, setError] = useState('');

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

  const { lecId, identified_students = [], unidentified_faces = [] } = state;

  const handleFinalize = async () => {
    setFinalizing(true);
    setError('');
    try {
      const prns = identified_students.map(s => s.prn);
      const result = await finalizeAttendance(lecId, prns);
      setSuccessMsg(`${result.message} — CSV saved at: ${result.csv_path}`);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to finalize attendance.');
    } finally {
      setFinalizing(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-10">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold text-slate-800">Attendance Results</h2>
          <p className="text-slate-600 mt-1">Lecture ID: {lecId}</p>
        </div>
        <Button variant="outline" onClick={() => navigate('/dashboard')}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
        </Button>
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

      {/* Summary */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-2">
        <Card className="border-0 shadow-md bg-green-50">
          <CardContent className="flex items-center justify-between p-6">
            <span className="text-green-700 font-medium">Present</span>
            <span className="text-3xl font-bold text-green-700">{identified_students.length}</span>
          </CardContent>
        </Card>
        <Card className="border-0 shadow-md bg-amber-50">
          <CardContent className="flex items-center justify-between p-6">
            <span className="text-amber-700 font-medium">Unidentified</span>
            <span className="text-3xl font-bold text-amber-700">{unidentified_faces.length}</span>
          </CardContent>
        </Card>
      </div>

      {/* Identified Students Table */}
      <Card className="border-0 shadow-xl">
        <CardHeader>
          <CardTitle className="text-slate-800">Identified Students</CardTitle>
          <CardDescription>All recognized students are marked Present</CardDescription>
        </CardHeader>
        <CardContent>
          {identified_students.length === 0 ? (
            <p className="text-slate-500 text-sm">No students identified.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>PRN</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Similarity</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {identified_students.map((s) => (
                  <TableRow key={s.prn}>
                    <TableCell className="font-mono text-sm">{s.prn}</TableCell>
                    <TableCell className="font-medium">{s.name}</TableCell>
                    <TableCell className="text-indigo-600 font-medium">
                      {(s.similarity * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell>
                      <span className="px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">
                        Present
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Unidentified Faces */}
      {unidentified_faces.length > 0 && (
        <Card className="border-0 shadow-xl">
          <CardHeader>
            <CardTitle className="text-slate-800">Unidentified Faces</CardTitle>
            <CardDescription>Faces detected but not matched to any enrolled student</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {unidentified_faces.map((face, idx) => (
                <div key={face.face_id ?? idx} className="flex flex-col items-center gap-2">
                  <img
                    src={`data:image/jpeg;base64,${face.image}`}
                    alt={`Unidentified Face #${idx + 1}`}
                    className="w-full aspect-square object-cover rounded-lg border border-slate-200 shadow-sm"
                  />
                  <span className="text-xs text-slate-500">Unidentified Face #{idx + 1}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Finalize */}
      <div className="flex justify-end">
        <Button
          onClick={handleFinalize}
          disabled={finalizing || !!successMsg}
          className="bg-indigo-600 hover:bg-indigo-700 px-8"
        >
          {finalizing ? 'Finalizing...' : 'Finalize Attendance'}
        </Button>
      </div>
    </div>
  );
}
