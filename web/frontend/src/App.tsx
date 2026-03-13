import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import CourseDetail from "./pages/CourseDetail";
import AskChat from "./pages/AskChat";
import SyncControl from "./pages/SyncControl";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="courses/:name" element={<CourseDetail />} />
            <Route path="ask" element={<AskChat />} />
            <Route path="sync" element={<SyncControl />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
