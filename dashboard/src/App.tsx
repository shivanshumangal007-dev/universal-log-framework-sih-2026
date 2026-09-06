import { useState, useCallback, useEffect } from "react";
import { api } from "./lib/api";
import { useAuth } from "./hooks/useAuth";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import LogsPage from "./pages/LogsPage";
import ReviewPage from "./pages/ReviewPage";

type Page = "dashboard" | "logs" | "review";

export default function App() {
  const { ready, login, logout, isAuthenticated } = useAuth();
  const [page, setPage] = useState<Page>("dashboard");

  useEffect(() => {
    document.title = "Universal Log Dashboard";
  }, []);

  const handleLogin = useCallback(
    async (username: string, password: string) => {
      await login(username, password, api.login);
    },
    [login]
  );

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-300 border-t-orange-500" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <Layout active={page} onNavigate={setPage} onLogout={logout}>
      {page === "dashboard" && <DashboardPage />}
      {page === "logs" && <LogsPage />}
      {page === "review" && <ReviewPage />}
    </Layout>
  );
}
