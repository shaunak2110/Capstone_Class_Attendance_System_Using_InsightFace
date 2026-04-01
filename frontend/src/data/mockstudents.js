// Mock data for initial demo (4 team members from synopsis)
export const teamMembers = [
  { 
    prn: "1032221489", 
    name: "Shaunak Dalvi", 
    roll: 12,
    email: "1032221489@mitwpu.edu.in",
    status: "Present", 
    confidence: 0.98 
  },
  { 
    prn: "1032220455", 
    name: "Sudhanshu Athanimath",
    roll: 8,
    email: "1032220455@mitwpu.edu.in",
    status: "Present", 
    confidence: 0.95 
  },
  { 
    prn: "1032220257", 
    name: "Ashlesha Chikhale", 
    roll: 2,
    email: "1032220257@mitwpu.edu.in",
    status: "Absent", 
    confidence: 0.00 
  },
  { 
    prn: "1032220283", 
    name: "Srishti Pagaria", 
    roll: 5,
    email: "1032220283@mitwpu.edu.in",
    status: "Present", 
    confidence: 0.99 
  },
];

// Mock lecture data
export const lectureInfo = {
  course: "CSE Capstone Project",
  batch: "P23",
  date: new Date().toLocaleDateString(),
  time: new Date().toLocaleTimeString(),
};