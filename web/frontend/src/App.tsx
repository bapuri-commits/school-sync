import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import ErrorBoundary from "./components/ErrorBoundary";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import CourseDetail from "./pages/CourseDetail";
import AskChat from "./pages/AskChat";
import SyncControl from "./pages/SyncControl";
import LessonAssist from "./pages/LessonAssist";
import Notices from "./pages/Notices";

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
              <Route path="courses/:name" element={<ErrorBoundary><CourseDetail /></ErrorBoundary>} />
              <Route path="ask" element={<ErrorBoundary><AskChat /></ErrorBoundary>} />
              <Route path="notices" element={<ErrorBoundary><Notices /></ErrorBoundary>} />
              <Route path="sync" element={<ErrorBoundary><SyncControl /></ErrorBoundary>} />
              <Route path="lesson-assist" element={<ErrorBoundary><LessonAssist /></ErrorBoundary>} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}
