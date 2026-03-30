import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import ResearchDetail from "./pages/ResearchDetail";
import TraceDetail from "./pages/TraceDetail";
import CostDashboard from "./pages/CostDashboard";
import SystemOverview from "./pages/SystemOverview";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/research/:id" element={<ResearchDetail />} />
        <Route path="/research/:id/trace" element={<TraceDetail />} />
        <Route path="/research/:id/costs" element={<CostDashboard />} />
        <Route path="/system" element={<SystemOverview />} />
      </Routes>
    </Layout>
  );
}
