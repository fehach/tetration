import { Route, Routes } from "react-router-dom";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { ChatPage } from "./pages/Chat";
import { ConfigurationPage } from "./pages/Configuration";
import { HomePage } from "./pages/Home";
import { QueriesPage } from "./pages/Queries";

export default function App() {
  return (
    <div className="flex h-full bg-surface-background text-white">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="flex-1 overflow-y-auto px-6 py-6">
          <div className="mx-auto max-w-content">
            <Routes>
              <Route index element={<HomePage />} />
              <Route path="/queries" element={<QueriesPage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/configuration" element={<ConfigurationPage />} />
            </Routes>
          </div>
        </main>
      </div>
    </div>
  );
}
