import About from "./pages/About";
import GetHelp from "./pages/GetHelp";
import RightDetail from "./pages/RightDetail";
import KnowYourRights from "./pages/KnowYourRights";
import LegalAssistant from "./pages/LegalAssistant";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import MainLayout from "./layouts/MainLayout";
import Home from "./pages/Home";
import "./App.css";

function Placeholder({ title }) {
  return (
    <div className="placeholder-page">
      <h1>{title}</h1>
      <p>This page is under development.</p>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <MainLayout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/assistant" element={<LegalAssistant />} />
          <Route path="/rights" element={<KnowYourRights />} />
          <Route path="/rights/:topicSlug" element={<RightDetail />} />
          <Route path="/get-help" element={<GetHelp />} />
          <Route path="/documents" element={<Placeholder title="My Documents" />} />
          <Route path="/about" element={<About />} />
        </Routes>
      </MainLayout>
    </BrowserRouter>
  );
}