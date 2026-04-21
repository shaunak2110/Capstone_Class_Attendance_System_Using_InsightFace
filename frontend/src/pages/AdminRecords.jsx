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
    <div className="relative min-h-[calc(100vh-2rem)] bg-slate-50 dark:bg-[#0f1117] text-slate-800 dark:text-slate-200 p-4 sm:p-8 rounded-xl overflow-hidden font-sans shadow-2xl selection:bg-purple-500/30">
      {/* Background Effects */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-indigo-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-teal-600/10 blur-[120px] pointer-events-none" />

      <div className="relative space-y-6 animate-in fade-in duration-700 z-10 w-full max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-6 border-b border-slate-300 dark:border-white/10">
          <h2 className="text-3xl font-bold tracking-tight text-solid bg-clip-text bg-gradient-to-r from-indigo-400 via-teal-400 to-purple-400">
            Attendance Center
          </h2>
          <Button variant="outline" onClick={() => navigate(-1)} className="bg-white dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-slate-900 dark:text-white border-slate-300 dark:border-white/10 shadow-lg backdrop-blur-md transition-all duration-300">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
          </Button>
        </div>

        {/* Tabs Navigation */}
        <div className="flex gap-2 border-b border-slate-300 dark:border-white/10 pb-4">
          <Button
            onClick={() => setActiveTab('lectures')}
            variant="ghost"
            className={activeTab === 'lectures' ? 'bg-indigo-600 hover:bg-indigo-500 text-slate-900 dark:text-white shadow-[0_0_15px_rgba(79,70,229,0.3)] border border-indigo-500/50 transition-all duration-300' : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5'}
          >
            <BookOpen className="mr-2 h-4 w-4" /> All Lectures
          </Button>
          <Button
            onClick={() => setActiveTab('analytics')}
            variant="ghost"
            className={activeTab === 'analytics' ? 'bg-teal-600 hover:bg-teal-500 text-slate-900 dark:text-white shadow-[0_0_15px_rgba(20,184,166,0.3)] border border-teal-500/50 transition-all duration-300' : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5'}
          >
            <BarChart3 className="mr-2 h-4 w-4" /> Analytics & Reports
          </Button>
        </div>

        {/* VIEW: ALL LECTURES */}
        {activeTab === 'lectures' && (
          <Card className="bg-white dark:bg-white/5 border-slate-300 dark:border-white/10 backdrop-blur-xl shadow-xl relative overflow-hidden transition-all duration-300 hover:bg-slate-100 dark:hover:bg-white/[0.07]">
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-[50px] pointer-events-none" />
            <CardHeader className="border-b border-slate-200 dark:border-white/5 pb-4">
              <CardTitle className="text-slate-900 dark:text-white flex items-center gap-3">
                <div className="bg-indigo-500/20 text-indigo-400 p-2.5 rounded-lg border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.15)]">
                  <BookOpen className="h-5 w-5" />
                </div>
                Scheduled Master List
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              {loading ? (
                <p className="text-slate-600 dark:text-slate-400">Loading records...</p>
              ) : lectures.length === 0 ? (
                <p className="text-slate-600 dark:text-slate-400">No scheduled lectures found.</p>
              ) : (
                <div className="rounded-md border border-slate-300 dark:border-white/10 overflow-hidden">
                  <Table>
                    <TableHeader className="bg-white dark:bg-black/20 border-b border-slate-300 dark:border-white/10">
                      <TableRow className="border-b border-slate-300 dark:border-white/10 hover:bg-transparent">
                        <TableHead className="text-slate-700 dark:text-slate-300 font-semibold">Teacher Username</TableHead>
                        <TableHead className="text-slate-700 dark:text-slate-300 font-semibold">Lecture Name</TableHead>
                        <TableHead className="text-slate-700 dark:text-slate-300 font-semibold">Course</TableHead>
                        <TableHead className="text-slate-700 dark:text-slate-300 font-semibold">Year / Panel</TableHead>
                        <TableHead className="text-slate-700 dark:text-slate-300 font-semibold">Date & Time</TableHead>
                        <TableHead className="text-slate-700 dark:text-slate-300 font-semibold">Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {lectures.map((lec) => (
                        <TableRow key={lec.lec_id} className="border-b border-slate-200 dark:border-white/5 hover:bg-slate-100 dark:hover:bg-white/5 transition-colors">
                          <TableCell className="font-medium text-slate-800 dark:text-slate-200">{lec.username}</TableCell>
                          <TableCell className="text-slate-700 dark:text-slate-300">{lec.lec_name}</TableCell>
                          <TableCell className="text-slate-600 dark:text-slate-400">{lec.course_code}</TableCell>
                          <TableCell className="text-slate-700 dark:text-slate-300">{lec.year} ({lec.panel})</TableCell>
                          <TableCell className="text-slate-700 dark:text-slate-300">{formatDateTime(lec.lecture_datetime)}</TableCell>
                          <TableCell>
                            {lec.attendance_status === 'Y' ? (
                              <span className="px-2 py-1 rounded-full text-xs font-medium bg-teal-500/10 text-teal-400 border border-teal-500/20 shadow-[0_0_10px_rgba(20,184,166,0.1)]">Completed</span>
                            ) : (
                              <span className="px-2 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 shadow-[0_0_10px_rgba(245,158,11,0.1)]">Pending</span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* VIEW: ANALYTICS & REPORTS */}
        {activeTab === 'analytics' && (
          <div className="space-y-6">
            <Card className="bg-white dark:bg-white/5 border-slate-300 dark:border-white/10 backdrop-blur-xl shadow-xl relative overflow-hidden transition-all duration-300 hover:bg-slate-100 dark:hover:bg-white/[0.07]">
              <div className="absolute top-0 right-0 w-32 h-32 bg-teal-500/10 rounded-full blur-[50px] pointer-events-none" />
              <CardHeader className="border-b border-slate-200 dark:border-white/5 pb-4">
                <CardTitle className="text-slate-900 dark:text-white flex items-center gap-3">
                  <div className="bg-teal-500/20 text-teal-400 p-2.5 rounded-lg border border-teal-500/20 shadow-[0_0_15px_rgba(20,184,166,0.15)]">
                    <Search className="h-5 w-5" />
                  </div>
                  Filter Parameters
                </CardTitle>
                <CardDescription className="text-slate-600 dark:text-slate-400 pt-1">Select criteria to aggregate student attendance into an analytics report.</CardDescription>
              </CardHeader>
              <CardContent className="pt-6">
                <form onSubmit={fetchAnalytics} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                  <div className="space-y-1.5"><Label className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Year</Label><Input value={filters.year} onChange={e => setFilters({ ...filters, year: e.target.value })} placeholder="e.g. FY" className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-teal-500 placeholder:text-slate-400 dark:placeholder:text-slate-600 h-10" /></div>
                  <div className="space-y-1.5"><Label className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Course Code / Subject</Label><Input value={filters.course_code} onChange={e => setFilters({ ...filters, course_code: e.target.value })} placeholder="e.g. CS101" className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-teal-500 placeholder:text-slate-400 dark:placeholder:text-slate-600 h-10" /></div>
                  <div className="space-y-1.5"><Label className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Panel / Class</Label><Input value={filters.panel} onChange={e => setFilters({ ...filters, panel: e.target.value })} placeholder="e.g. A1" className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-teal-500 placeholder:text-slate-400 dark:placeholder:text-slate-600 h-10" /></div>
                  <div className="space-y-1.5"><Label className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Teacher Username</Label><Input value={filters.username} onChange={e => setFilters({ ...filters, username: e.target.value })} placeholder="e.g. dr.smith" className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-teal-500 placeholder:text-slate-400 dark:placeholder:text-slate-600 h-10" /></div>
                  <div className="space-y-1.5"><Label className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">Start Date (Optional)</Label><Input type="date" value={filters.start_date} onChange={e => setFilters({ ...filters, start_date: e.target.value })} className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-teal-500 h-10 [color-scheme:dark]" /></div>
                  <div className="space-y-1.5"><Label className="text-slate-700 dark:text-slate-300 text-xs uppercase tracking-wider">End Date (Optional)</Label><Input type="date" value={filters.end_date} onChange={e => setFilters({ ...filters, end_date: e.target.value })} className="bg-white dark:bg-black/20 border-slate-300 dark:border-white/10 text-slate-900 dark:text-white focus-visible:ring-teal-500 h-10 [color-scheme:dark]" /></div>

                  <div className="md:col-span-3 flex justify-end mt-4">
                    <Button type="submit" disabled={generating} className="bg-teal-600 hover:bg-teal-500 text-slate-900 dark:text-white border border-teal-500/50 shadow-[0_0_15px_rgba(20,184,166,0.2)] transition-all duration-300 px-8 h-10">
                      {generating ? 'Aggregating Data...' : 'Generate Dashboard'}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>

            {/* DASHBOARD RESULTS */}
            {reportData && (
              <div className="space-y-6 animate-in slide-in-from-bottom-4 duration-500">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-2 border-b border-slate-300 dark:border-white/10">
                  <h3 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <BarChart3 className="h-6 w-6 text-teal-400" /> Report: {reportData.subject} ({reportData.panel})
                  </h3>
                  <Button onClick={downloadCSV} className="bg-purple-600 hover:bg-purple-500 text-slate-900 dark:text-white border border-purple-500/50 shadow-[0_0_15px_rgba(147,51,234,0.2)] transition-all duration-300">
                    <Download className="mr-2 h-4 w-4" /> Download CSV
                  </Button>
                </div>

                {/* KPI Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Card className="bg-white dark:bg-white/5 border-slate-300 dark:border-white/10 backdrop-blur-xl shadow-xl hover:bg-slate-100 dark:hover:bg-white/[0.07] transition-all duration-300">
                    <CardContent className="flex items-center gap-4 p-6">
                      <div className="bg-indigo-500/20 p-3 rounded-xl border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.15)] text-indigo-400"><CalendarCheck className="h-6 w-6" /></div>
                      <div><p className="text-sm font-medium text-slate-600 dark:text-slate-400 tracking-wide uppercase">Total Lectures</p><p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">{reportData.totalLectures}</p></div>
                    </CardContent>
                  </Card>
                  <Card className="bg-white dark:bg-white/5 border-slate-300 dark:border-white/10 backdrop-blur-xl shadow-xl hover:bg-slate-100 dark:hover:bg-white/[0.07] transition-all duration-300">
                    <CardContent className="flex items-center gap-4 p-6">
                      <div className="bg-purple-500/20 p-3 rounded-xl border border-purple-500/20 shadow-[0_0_15px_rgba(168,85,247,0.15)] text-purple-400"><Users className="h-6 w-6" /></div>
                      <div><p className="text-sm font-medium text-slate-600 dark:text-slate-400 tracking-wide uppercase">Total Students</p><p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">{reportData.students.length}</p></div>
                    </CardContent>
                  </Card>
                  <Card className="bg-white dark:bg-white/5 border-slate-300 dark:border-white/10 backdrop-blur-xl shadow-xl hover:bg-slate-100 dark:hover:bg-white/[0.07] transition-all duration-300">
                    <CardContent className="flex items-center gap-4 p-6">
                      <div className="bg-teal-500/20 p-3 rounded-xl border border-teal-500/20 shadow-[0_0_15px_rgba(20,184,166,0.15)] text-teal-400"><Percent className="h-6 w-6" /></div>
                      <div><p className="text-sm font-medium text-slate-600 dark:text-slate-400 tracking-wide uppercase">Overall Attendance</p><p className="text-3xl font-bold text-teal-400 mt-1">{reportData.overallPercentage}%</p></div>
                    </CardContent>
                  </Card>
                </div>

                {/* Student Table */}
                <Card className="bg-white dark:bg-white/5 border-slate-300 dark:border-white/10 backdrop-blur-xl shadow-xl relative overflow-hidden">
                  <CardHeader className="border-b border-slate-200 dark:border-white/5 pb-4">
                    <CardTitle className="text-slate-900 dark:text-white">Attendance Breakdown</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-4 p-0 sm:p-6 sm:pt-4">
                    <div className="rounded-md border border-slate-300 dark:border-white/10 overflow-hidden">
                      <Table>
                        <TableHeader className="bg-white dark:bg-black/20 border-b border-slate-300 dark:border-white/10">
                          <TableRow className="border-b border-slate-300 dark:border-white/10 hover:bg-transparent">
                            <TableHead className="font-semibold text-slate-700 dark:text-slate-300">PRN</TableHead>
                            <TableHead className="font-semibold text-slate-700 dark:text-slate-300">Name</TableHead>
                            <TableHead className="text-center font-semibold text-slate-700 dark:text-slate-300">Lectures</TableHead>
                            <TableHead className="text-center font-semibold text-teal-400">Present</TableHead>
                            <TableHead className="text-center font-semibold text-red-400">Absent</TableHead>
                            <TableHead className="text-right font-semibold text-slate-700 dark:text-slate-300">Percent (%)</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {reportData.students.map((s, i) => {
                            const p = Math.round((s.present / s.total) * 100);
                            return (
                              <TableRow key={i} className="border-b border-slate-200 dark:border-white/5 hover:bg-slate-100 dark:hover:bg-white/5 transition-colors">
                                <TableCell className="font-mono text-sm text-slate-700 dark:text-slate-300">{s.prn}</TableCell>
                                <TableCell className="font-medium text-slate-900 dark:text-white">{s.name}</TableCell>
                                <TableCell className="text-center text-slate-700 dark:text-slate-300">{s.total}</TableCell>
                                <TableCell className="text-center font-medium text-teal-400">{s.present}</TableCell>
                                <TableCell className="text-center font-medium text-red-400">{s.total - s.present}</TableCell>
                                <TableCell className="text-right">
                                  <div className="flex items-center justify-end gap-2">
                                    <div className="w-16 h-2 bg-slate-50 dark:bg-black/40 rounded-full overflow-hidden">
                                      <div className={`h-full ${p >= 75 ? 'bg-teal-500' : p >= 50 ? 'bg-amber-400' : 'bg-red-500'}`} style={{ width: `${p}%` }}></div>
                                    </div>
                                    <span className={`font-bold ${p >= 75 ? 'text-teal-400' : p >= 50 ? 'text-amber-400' : 'text-red-400'}`}>{p}%</span>
                                  </div>
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
