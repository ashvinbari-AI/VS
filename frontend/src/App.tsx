import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/Layout/AppLayout";
import { ToastProvider } from "./components/Toast/ToastProvider";
import { FilterProvider } from "./state/FilterContext";

// Route-level code splitting: each page ships as its own chunk so the
// initial load only pays for the shell (layout + router) and the page the
// user actually lands on, instead of one large bundle up front.
const Overview = lazy(() => import("./pages/Overview"));
const Report = lazy(() => import("./pages/Report"));
const Comparison = lazy(() => import("./pages/Comparison"));
const ActivityPage = lazy(() => import("./pages/Activity"));
const Engagement = lazy(() => import("./pages/Engagement"));
const Content = lazy(() => import("./pages/Content"));
const Narratives = lazy(() => import("./pages/Narratives"));
const SentimentPage = lazy(() => import("./pages/Sentiment"));
const SentimentDetail = lazy(() => import("./pages/SentimentDetail"));
const Comments = lazy(() => import("./pages/Comments"));
const Timeline = lazy(() => import("./pages/Timeline"));
const Explorer = lazy(() => import("./pages/Explorer"));
const DataSources = lazy(() => import("./pages/DataSources"));
const SettingsPage = lazy(() => import("./pages/Settings"));
const Evaluation = lazy(() => import("./pages/Evaluation"));

export default function App() {
  return (
    <ToastProvider>
      <FilterProvider>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/overview" replace />} />
            <Route path="/overview" element={<Overview />} />
            <Route path="/report" element={<Report />} />
            <Route path="/comparison" element={<Comparison />} />
            <Route path="/activity" element={<ActivityPage />} />
            <Route path="/engagement" element={<Engagement />} />
            <Route path="/content" element={<Content />} />
            <Route path="/narratives" element={<Narratives />} />
            <Route path="/sentiment" element={<SentimentPage />} />
            <Route path="/sentiment/detail" element={<SentimentDetail />} />
            <Route path="/comments" element={<Comments />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/explorer" element={<Explorer />} />
            <Route path="/data-sources" element={<DataSources />} />
            <Route path="/evaluation" element={<Evaluation />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/overview" replace />} />
          </Route>
        </Routes>
      </FilterProvider>
    </ToastProvider>
  );
}
