import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/lib/auth";
import LoginPage from "@/pages/Login";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import StudentsPage from "@/pages/Students";
import StudentForm from "@/pages/StudentForm";
import EnrollFace from "@/pages/EnrollFace";
import ScanPage from "@/pages/ScanPage";
import AttendancePage from "@/pages/Attendance";
import StudentDashboard from "@/pages/StudentDashboard";
import StudentAttendance from "@/pages/StudentAttendance";
import StudentScan from "@/pages/StudentScan";

function ProtectedRoute({ children, role }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) return <Navigate to={user.role === "admin" ? "/dashboard" : "/my"} replace />;
  return children;
}

function RootRedirect() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "admin" ? "/dashboard" : "/my"} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <Toaster position="top-right" richColors />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/login" element={<LoginPage />} />

          {/* Admin */}
          <Route element={<ProtectedRoute role="admin"><Layout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/students" element={<StudentsPage />} />
            <Route path="/students/new" element={<StudentForm />} />
            <Route path="/students/:id/edit" element={<StudentForm />} />
            <Route path="/students/:id/enroll" element={<EnrollFace />} />
            <Route path="/scan" element={<ScanPage />} />
            <Route path="/attendance" element={<AttendancePage />} />
            <Route path="/settings/password" element={<ChangePassword />} />
          </Route>

          {/* Student */}
          <Route element={<ProtectedRoute role="student"><Layout /></ProtectedRoute>}>
            <Route path="/my" element={<StudentDashboard />} />
            <Route path="/my/scan" element={<StudentScan />} />
            <Route path="/my/attendance" element={<StudentAttendance />} />
            <Route path="/my/settings/password" element={<ChangePassword />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
