import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import Dashboard from "./pages/Dashboard";
import ExamSetup from "./pages/ExamSetup";
import Exam from "./pages/Exam";
import ExamView from "./pages/ExamView";
import Chat from "./pages/Chat";
import Books from "./pages/Books";
import AddBook from "./pages/AddBook";
import Scripts from "./pages/Scripts";
import Features from "./pages/Features";
import SignIn from "./pages/SignIn";
import SignUp from "./pages/SignUp";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/books" element={<Books />} />
          <Route path="/books/add" element={<AddBook />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/exams" element={<ExamSetup />} />
          <Route path="/exam-setup/:bookTitle" element={<ExamSetup />} />
          <Route path="/exam" element={<Exam />} />
          <Route path="/exam-view" element={<ExamView />} />
          <Route path="/scripts" element={<Scripts />} />
          <Route path="/features" element={<Features />} />
          <Route path="/signin" element={<SignIn />} />
          <Route path="/signup" element={<SignUp />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
