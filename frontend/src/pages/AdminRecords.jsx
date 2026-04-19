import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft, BookOpen, BarChart3, Download, Search, Users, Percent, CalendarCheck } from 'lucide-react';
import { getAllLectures, getAttendanceAnalytics } from "@/services/api";

export default function AdminRecords() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('lectures'); // 'lectures' or 'analytics'
  const [lectures, setLectures] = useState([]);
  const [loading, setLoading] = useState(true);

  // Analytics State
  const [filters, setFilters] = useState({ year: '', course_code: '', panel: '', username: '', start_date: '', end_date: '' });
  const [reportData, setReportData] = useState(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    getAllLectures()
      .then(setLectures)
      .catch((e) => console.error(e))
      .finally(() => setLoading(false));
  }, []);

  const formatDateTime = (dt) => {
    if (!dt) return '';
    return new Date(dt).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  };

  const fetchAnalytics = async (e) => {
    e.preventDefault();
    setGenerating(true);
    try {
      const data = await getAttendanceAnalytics(filters);
      setReportData(data);
    } catch (err) {
      console.error(err);
      alert('Error extracting analytics. Please verify your SQL table migrations match the query parameters!');
    } finally {
      setGenerating(false);
    }
  };

  const downloadCSV = () => {
    if (!reportData) return;
    const headers = "PRN,Name,Total Lectures,Present,Absent,Percentage\n";
    const rows = reportData.students.map(s => {
      const p = Math.round((s.present / s.total) * 100);
      return `${s.prn},${s.name},${s.total},${s.present},${s.total - s.present},${p}%`;
    }).join("\n");
    
    const blob = new Blob([headers + rows], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `Analytics_${reportData.subject.replace(' ', '_')}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6 pb-10 animate-in fade-in duration-500">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <h2 className="text-3xl font-bold text-slate-800">Attendance Center</h2>
        <Button variant="outline" onClick={() => navigate('/admin-dashboard')}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
        </Button>
      </div>

      {/* Tabs Navigation */}
      <div className="flex gap-2 border-b border-slate-200 pb-2">
        <Button 
          onClick={() => setActiveTab('lectures')} 
          variant={activeTab === 'lectures' ? 'default' : 'ghost'}
          className={activeTab === 'lectures' ? 'bg-indigo-600 hover:bg-indigo-700' : 'text-slate-600'}
        >
          <BookOpen className="mr-2 h-4 w-4" /> All Lectures
        </Button>
        <Button 
          onClick={() => setActiveTab('analytics')}
          variant={activeTab === 'analytics' ? 'default' : 'ghost'}
          className={activeTab === 'analytics' ? 'bg-emerald-600 hover:bg-emerald-700' : 'text-slate-600'}
        >
          <BarChart3 className="mr-2 h-4 w-4" /> Analytics & Reports
        </Button>
      </div>

      {/* VIEW: ALL LECTURES */}
      {activeTab === 'lectures' && (
        <Card className="border-0 shadow-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><BookOpen className="h-5 w-5 text-indigo-600"/> Scheduled Master List</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-slate-500">Loading records...</p>
            ) : lectures.length === 0 ? (
              <p className="text-slate-500">No scheduled lectures found.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Teacher Username</TableHead>
                    <TableHead>Lecture Name</TableHead>
                    <TableHead>Course</TableHead>
                    <TableHead>Year / Panel</TableHead>
                    <TableHead>Date & Time</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {lectures.map((lec) => (
                    <TableRow key={lec.lec_id}>
                      <TableCell className="font-medium text-slate-700">{lec.username}</TableCell>
                      <TableCell>{lec.lec_name}</TableCell>
                      <TableCell className="text-slate-500">{lec.course_code}</TableCell>
                      <TableCell>{lec.year} ({lec.panel})</TableCell>
                      <TableCell>{formatDateTime(lec.lecture_datetime)}</TableCell>
                      <TableCell>
                        {lec.attendance_status === 'Y' ? (
                          <span className="px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700 border border-green-200">Completed</span>
                        ) : (
                          <span className="px-2 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-700 border border-amber-200">Pending</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* VIEW: ANALYTICS & REPORTS */}
      {activeTab === 'analytics' && (
        <div className="space-y-6">
          <Card className="border-0 shadow-xl bg-gradient-to-br from-indigo-50 to-emerald-50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-indigo-800">
                <Search className="h-5 w-5" /> Filter Parameters
              </CardTitle>
              <CardDescription className="text-indigo-600 font-medium">Select criteria to aggregate student attendance into an analytics report.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={fetchAnalytics} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                <div className="space-y-1"><Label>Year</Label><Input value={filters.year} onChange={e => setFilters({...filters, year: e.target.value})} placeholder="e.g. FY" className="border-white" /></div>
                <div className="space-y-1"><Label>Course Code / Subject</Label><Input value={filters.course_code} onChange={e => setFilters({...filters, course_code: e.target.value})} placeholder="e.g. CS101" className="border-white" /></div>
                <div className="space-y-1"><Label>Panel / Class</Label><Input value={filters.panel} onChange={e => setFilters({...filters, panel: e.target.value})} placeholder="e.g. A1" className="border-white" /></div>
                <div className="space-y-1"><Label>Teacher Username</Label><Input value={filters.username} onChange={e => setFilters({...filters, username: e.target.value})} placeholder="e.g. dr.smith" className="border-white" /></div>
                <div className="space-y-1"><Label>Start Date (Optional)</Label><Input type="date" value={filters.start_date} onChange={e => setFilters({...filters, start_date: e.target.value})} className="border-white text-slate-600" /></div>
                <div className="space-y-1"><Label>End Date (Optional)</Label><Input type="date" value={filters.end_date} onChange={e => setFilters({...filters, end_date: e.target.value})} className="border-white text-slate-600" /></div>
                
                <div className="md:col-span-3 flex justify-end mt-2">
                  <Button type="submit" disabled={generating} className="bg-emerald-600 hover:bg-emerald-700 px-8 shadow-md">
                    {generating ? 'Aggregating Data...' : 'Generate Dashboard'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* DASHBOARD RESULTS */}
          {reportData && (
            <div className="space-y-6 animate-in slide-in-from-bottom-4 duration-500">
              
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <h3 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
                  <BarChart3 className="h-6 w-6 text-indigo-600" /> Report: {reportData.subject} ({reportData.panel})
                </h3>
                <Button onClick={downloadCSV} className="bg-green-600 hover:bg-green-700 shadow-md">
                  <Download className="mr-2 h-4 w-4" /> Download CSV
                </Button>
              </div>

              {/* KPI Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                 <Card className="border-0 shadow-md bg-white">
                   <CardContent className="flex items-center gap-4 p-6">
                     <div className="bg-indigo-100 p-3 rounded-full text-indigo-600"><CalendarCheck className="h-6 w-6" /></div>
                     <div><p className="text-sm font-medium text-slate-500">Total Lectures</p><p className="text-2xl font-bold text-slate-800">{reportData.totalLectures}</p></div>
                   </CardContent>
                 </Card>
                 <Card className="border-0 shadow-md bg-white">
                   <CardContent className="flex items-center gap-4 p-6">
                     <div className="bg-purple-100 p-3 rounded-full text-purple-600"><Users className="h-6 w-6" /></div>
                     <div><p className="text-sm font-medium text-slate-500">Total Students</p><p className="text-2xl font-bold text-slate-800">{reportData.students.length}</p></div>
                   </CardContent>
                 </Card>
                 <Card className="border-0 shadow-md bg-white">
                   <CardContent className="flex items-center gap-4 p-6">
                     <div className="bg-emerald-100 p-3 rounded-full text-emerald-600"><Percent className="h-6 w-6" /></div>
                     <div><p className="text-sm font-medium text-slate-500">Overall Attendance</p><p className="text-2xl font-bold text-emerald-600">{reportData.overallPercentage}%</p></div>
                   </CardContent>
                 </Card>
              </div>

              {/* Student Table */}
              <Card className="border-0 shadow-xl">
                <CardHeader>
                  <CardTitle>Attendance Breakdown</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader className="bg-slate-50">
                      <TableRow>
                        <TableHead className="font-semibold text-slate-700">PRN</TableHead>
                        <TableHead className="font-semibold text-slate-700">Name</TableHead>
                        <TableHead className="text-center font-semibold text-slate-700">Lectures Held</TableHead>
                        <TableHead className="text-center font-semibold text-green-700">Present</TableHead>
                        <TableHead className="text-center font-semibold text-red-700">Absent</TableHead>
                        <TableHead className="text-right font-semibold text-slate-700">Percent (%)</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                     {reportData.students.map((s, i) => {
                       const p = Math.round((s.present / s.total) * 100);
                       return (
                        <TableRow key={i} className="hover:bg-slate-50/50">
                          <TableCell className="font-mono text-sm">{s.prn}</TableCell>
                          <TableCell className="font-medium text-slate-800">{s.name}</TableCell>
                          <TableCell className="text-center">{s.total}</TableCell>
                          <TableCell className="text-center font-medium text-green-600">{s.present}</TableCell>
                          <TableCell className="text-center font-medium text-red-500">{s.total - s.present}</TableCell>
                          <TableCell className="text-right">
                             <div className="flex items-center justify-end gap-2">
                               <div className="w-16 h-2 bg-slate-100 rounded-full overflow-hidden">
                                 <div className={`h-full ${p >= 75 ? 'bg-green-500' : p >= 50 ? 'bg-amber-400' : 'bg-red-500'}`} style={{ width: `${p}%`}}></div>
                               </div>
                               <span className={`font-bold ${p >= 75 ? 'text-green-600' : p >= 50 ? 'text-amber-500' : 'text-red-600'}`}>{p}%</span>
                             </div>
                          </TableCell>
                        </TableRow>
                       );
                     })}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

            </div>
          )}
        </div>
      )}
    </div>
  );
}
