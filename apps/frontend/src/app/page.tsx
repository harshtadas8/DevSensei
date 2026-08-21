"use client";

import { useState, useEffect, useRef } from "react";
import { Terminal, Code, Code2, Settings, Bug, Play, GitBranch, ShieldCheck, Database, LayoutTemplate, Activity, X, Menu, MessageSquare, Send, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import mermaid from "mermaid";
import { motion } from "framer-motion";

const MermaidDiagram = ({ chart }: { chart: string }) => {
  const [svg, setSvg] = useState<string>("");

  useEffect(() => {
    mermaid.initialize({ startOnLoad: false, theme: "dark" });
    const id = `mermaid-${Math.random().toString(36).substring(7)}`;
    mermaid.render(id, chart).then((res) => setSvg(res.svg)).catch(console.error);
  }, [chart]);

  return (
    <div 
      className="flex justify-center p-4 bg-slate-900/50 rounded-lg border border-slate-700/50 my-4 shadow-inner overflow-x-auto [&>svg]:max-w-full [&>svg]:h-auto"
      dangerouslySetInnerHTML={{ __html: svg }} 
    />
  );
};

export default function Home() {
  const [targetPath, setTargetPath] = useState(".");
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [results, setResults] = useState<any>(null);
  
  // Phase 6: Code Viewer State
  const [viewerPath, setViewerPath] = useState("");
  const [viewerLoading, setViewerLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "review" | "test" | "code">("review");
  const [leftWidth, setLeftWidth] = useState(40); // 40% default for left pane
  const [isLeftCollapsed, setIsLeftCollapsed] = useState(false);
  const [isMainSidebarOpen, setIsMainSidebarOpen] = useState(true);
  const isDragging = useRef(false);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const containerWidth = window.innerWidth - 256; // minus sidebar
      const mouseX = e.clientX - 256;
      let newWidth = (mouseX / containerWidth) * 100;
      if (newWidth < 20) newWidth = 20;
      if (newWidth > 80) newWidth = 80;
      setLeftWidth(newWidth);
    };

    const handleMouseUp = () => {
      if (isDragging.current) {
        isDragging.current = false;
        document.body.style.cursor = 'default';
      }
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  const handleMouseDown = () => {
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isChatLoading) return;
    
    const userMsg = chatInput.trim();
    setChatInput("");
    setChatMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setIsChatLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userMsg, repo_path: results?.repo_path || "" })
      });
      const data = await res.json();
      
      setChatMessages(prev => [...prev, { 
        role: "assistant", 
        content: data.answer || data.error || "Sorry, I couldn't generate a response." 
      }]);
    } catch (err: any) {
      setChatMessages(prev => [...prev, { role: "assistant", content: `Error: ${err.message}` }]);
    } finally {
      setIsChatLoading(false);
    }
  };

  // Phase 5: PR Config Modal
  const [showPrModal, setShowPrModal] = useState(false);

  // Phase 9 Option B: Chat State
  const [chatMessages, setChatMessages] = useState<{role: string, content: string}[]>([
    { role: "assistant", content: "Hi! I'm DevSensei. I have analyzed this repository. Ask me anything about the code!" }
  ]);
  const [chatInput, setChatInput] = useState("");
  const [isChatLoading, setIsChatLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const loadFile = async (fileName: string) => {
    setActiveTab("code");
    setViewerPath(fileName);
    setViewerLoading(true);
    try {
      // Clean path if it has backticks
      let cleanPath = fileName.replace(/`/g, "").trim();
      // If we have a repo_path in results, we need to fetch the file from that directory!
      const basePath = results?.repo_path;
      if (basePath && !cleanPath.startsWith(basePath)) {
          cleanPath = `${basePath}/${cleanPath}`;
      }

      const res = await fetch(`/api/file?path=${encodeURIComponent(cleanPath)}`);
      if (!res.ok) throw new Error("File not found or access denied");
      const data = await res.json();
      setViewerContent(data.content);
    } catch (err: any) {
      setViewerContent(`Error loading file:\n${err.message}`);
    } finally {
      setViewerLoading(false);
    }
  };

  const runAnalysis = async () => {
    setLoading(true);
    setResults(null);
    setLogs(["Initializing connection to Orchestrator..."]);
    
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_path: targetPath }),
      });
      
      const reader = res.body?.getReader();
      if (!reader) throw new Error("No reader");
      
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        let boundary = buffer.indexOf('\n\n');
        while (boundary !== -1) {
          const chunk = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          
          if (chunk.startsWith('data: ')) {
            const dataStr = chunk.substring(6).trim();
            if (dataStr) {
              try {
                const data = JSON.parse(dataStr);
                if (data.stage === 'complete') {
                   setResults(data.results);
                   setLoading(false);
                } else if (data.log) {
                   setLogs(prev => [...prev, data.log]);
                }
              } catch (e) {
                console.error("Parse error:", e, "String was:", dataStr);
              }
            }
          }
          boundary = buffer.indexOf('\n\n');
        }
      }
    } catch (error) {
      console.error(error);
      setResults({
        status: "error",
        reviewer_notes: "Analysis API Error: Stream disconnected.",
      });
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-[#0d1117] text-slate-300 font-sans overflow-hidden selection:bg-teal-500/30">
      
      {/* SIDEBAR */}
      {isMainSidebarOpen && (
        <div className="w-64 bg-[#010409] border-r border-slate-800 flex flex-col shadow-2xl z-20 shrink-0">
          <div className="h-16 flex items-center px-6 border-b border-slate-800">
            <Terminal className="w-6 h-6 text-teal-400 mr-3 shrink-0" />
            <h1 className="text-xl font-bold text-white tracking-tight">DevSensei</h1>
          </div>
          <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
            <button className="w-full flex items-center px-4 py-3 bg-teal-500/10 text-teal-400 rounded-lg font-medium border border-teal-500/20 shadow-inner">
              <LayoutTemplate className="w-5 h-5 mr-3" />
              Onboarder
            </button>
            <button onClick={() => setShowPrModal(true)} className="w-full flex items-center px-4 py-3 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors group">
              <GitBranch className="w-5 h-5 mr-3 group-hover:text-teal-400 transition-colors" />
              PR Bot Config
            </button>
          </nav>
          <div className="p-4 border-t border-slate-800 flex items-center">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-teal-500 to-blue-500 flex items-center justify-center text-white font-bold text-sm shadow-lg mr-3">
              N
            </div>
            <div className="flex-1">
              <p className="text-xs text-slate-400 font-medium">DevSensei v0.6.0</p>
            </div>
            <Settings className="w-4 h-4 text-slate-500 hover:text-white cursor-pointer transition-colors" />
          </div>
        </div>
      )}

      {/* PR CONFIG MODAL */}
      {showPrModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center">
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="bg-[#0d1117] border border-slate-700 rounded-xl shadow-2xl w-[500px] overflow-hidden">
            <div className="bg-slate-900 border-b border-slate-800 p-4 flex items-center justify-between">
              <h3 className="font-semibold text-slate-200 flex items-center"><GitBranch className="w-5 h-5 mr-2 text-teal-400" /> PR Bot Configuration</h3>
              <button onClick={() => setShowPrModal(false)} className="text-slate-500 hover:text-white"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-6 space-y-4 text-sm text-slate-300">
              <p>Configure DevSensei to automatically analyze pull requests using GitHub Webhooks.</p>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Webhook URL</label>
                <code className="block w-full p-2 bg-[#010409] border border-slate-800 rounded text-teal-400 select-all">http://your-server-ip:8000/api/github/webhook</code>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Webhook Secret</label>
                <code className="block w-full p-2 bg-[#010409] border border-slate-800 rounded text-amber-400 select-all">devsensei_secret</code>
              </div>
              <div className="p-3 bg-teal-950/30 border border-teal-900/50 rounded text-teal-200 text-xs">
                <strong>Status:</strong> The /api/github/webhook endpoint is currently <strong>Active</strong> and listening for `pull_request` events.
              </div>
            </div>
            <div className="border-t border-slate-800 p-4 bg-[#010409] flex justify-end">
              <button onClick={() => setShowPrModal(false)} className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded font-medium text-sm transition-colors">Done</button>
            </div>
          </motion.div>
        </div>
      )}

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 flex flex-col h-full bg-[#0d1117]">
        {/* HEADER */}
        <header className="h-16 border-b border-slate-800 bg-[#0d1117]/80 backdrop-blur-sm flex items-center justify-between px-6 z-10">
          <div className="flex items-center space-x-2">
            <button 
              onClick={() => setIsMainSidebarOpen(!isMainSidebarOpen)}
              className="mr-3 p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-md transition-colors"
              title={isMainSidebarOpen ? "Collapse Sidebar" : "Expand Sidebar"}
            >
              <Menu className="w-5 h-5" />
            </button>
            <span className="text-sm text-slate-500 font-mono">TARGET_REPO</span>
            <input
              type="text"
              value={targetPath}
              onChange={(e) => setTargetPath(e.target.value)}
              className="bg-[#010409] border border-slate-700 text-white px-3 py-1.5 rounded-md text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 w-80 font-mono transition-all"
              placeholder="./my-repo"
            />
          </div>
          <button
            onClick={runAnalysis}
            disabled={loading}
            className={`flex items-center px-5 py-2 rounded-md font-semibold text-sm transition-all shadow-lg ${
              loading ? "bg-slate-700 text-slate-400 cursor-not-allowed" : "bg-teal-600 hover:bg-teal-500 text-white hover:shadow-teal-500/20"
            }`}
          >
            {loading ? (
              <span className="flex items-center"><div className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin mr-2" /> Ingesting...</span>
            ) : (
              <><Play className="w-4 h-4 mr-2" /> Start Ingestion</>
            )}
          </button>
        </header>

        {/* WORKSPACE AREA */}
        {loading && !results ? (
          /* SSE PROGRESS STREAM */
          <div className="flex-1 flex flex-col items-center justify-center p-8 overflow-hidden relative">
            <div className="absolute inset-0 bg-teal-900/5 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-teal-900/20 via-[#0d1117] to-[#0d1117]" />
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="w-full max-w-2xl bg-[#010409]/80 backdrop-blur-md border border-slate-700/50 rounded-xl shadow-2xl shadow-teal-900/20 overflow-hidden flex flex-col h-96 z-10">
              <div className="bg-slate-900/80 border-b border-slate-700/50 p-4 flex items-center">
                 <Activity className="w-5 h-5 text-teal-400 mr-3 animate-pulse" />
                 <h3 className="font-semibold text-slate-200">Real-time Ingestion Pipeline</h3>
              </div>
              <div className="p-6 flex-1 overflow-y-auto space-y-3 font-mono text-sm">
                {logs.map((log, i) => (
                  <motion.div 
                    initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                    key={i} className="flex items-start text-teal-400/90"
                  >
                    <span className="mr-3 opacity-40 shrink-0">[{new Date().toLocaleTimeString().split(' ')[0]}]</span>
                    <span>{log}</span>
                  </motion.div>
                ))}
                <div ref={(el) => el?.scrollIntoView({ behavior: 'smooth' })} />
              </div>
            </motion.div>
          </div>
        ) : results ? (
          /* SPLIT PANE RESULTS */
          <div className="flex-1 flex overflow-hidden">
            {/* LEFT PANE: DIAGRAM (Architect) */}
            <motion.div 
              initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}
              className="border-r border-slate-800 p-8 overflow-y-auto bg-[#0d1117] flex-shrink-0"
              style={{ width: `${leftWidth}%` }}
            >
              <div className="flex items-center space-x-3 mb-8">
                <div className="p-2 bg-teal-500/10 rounded-lg">
                  <Database className="w-5 h-5 text-teal-400" />
                </div>
                <h2 className="text-xl font-semibold text-white tracking-tight">System Architecture</h2>
              </div>
              <div className="prose prose-invert max-w-none prose-pre:bg-transparent prose-pre:p-0">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    code({ node, inline, className, children, ...props }: any) {
                      const match = /language-(\w+)/.exec(className || "");
                      if (!inline && match && match[1] === "mermaid") {
                        return <MermaidDiagram chart={String(children).replace(/\n$/, "")} />;
                      }
                      return <code className={className} {...props}>{children}</code>;
                    },
                    table({ children, ...props }: any) {
                      return <div className="overflow-x-auto w-full my-6 ring-1 ring-slate-800 rounded-lg bg-[#010409]"><table className="w-full text-left border-collapse" {...props}>{children}</table></div>;
                    },
                    th({ children, ...props }: any) {
                      return <th className="px-4 py-3 border-b border-slate-700 bg-slate-900/50 text-slate-300 font-medium text-sm whitespace-nowrap" {...props}>{children}</th>;
                    },
                    td({ children, ...props }: any) {
                      return <td className="px-4 py-3 border-b border-slate-800/50 text-slate-400 text-sm align-top" {...props}>{children}</td>;
                    }
                  }}
                >
                  {results.architect_notes}
                </ReactMarkdown>
              </div>
            </motion.div>

            {/* DRAGGABLE RESIZER */}
            <div 
              className="w-1.5 bg-slate-800/50 hover:bg-teal-500 cursor-col-resize flex-shrink-0 flex items-center justify-center z-20"
              onMouseDown={handleMouseDown}
            >
              <div className="w-0.5 h-8 bg-slate-600 hover:bg-white rounded-full" />
            </div>

            {/* RIGHT PANE: ANALYSIS / CHAT */}
            <motion.div 
              initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
              className="flex-1 flex flex-col bg-[#010409] min-w-0"
            >
              {/* Tabs */}
              <div className="flex px-2 pt-2 space-x-1 bg-[#010409] border-b border-slate-800 overflow-x-auto no-scrollbar items-center">
                <button 
                  onClick={() => setIsLeftCollapsed(!isLeftCollapsed)}
                  className="mr-2 p-2 text-slate-500 hover:text-teal-400 hover:bg-slate-800/50 rounded-lg transition-colors"
                  title={isLeftCollapsed ? "Show Architecture Panel" : "Hide Architecture Panel"}
                >
                  <LayoutTemplate className="w-4 h-4" />
                </button>
                <div className="h-6 w-px bg-slate-800 mx-2" />
                
                {[
                  { id: "review", label: "Security Review", icon: ShieldCheck },
                  { id: "test", label: "Test Coverage", icon: Bug },
                  { id: "synthesizer", label: "Synthesizer", icon: Code2 },
                  { id: "chat", label: "Chat", icon: MessageSquare },
                  { id: "code", label: "Code Viewer", icon: Terminal }
                ].map((tab) => (
                  <button 
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`px-4 py-3 font-medium text-sm flex items-center transition-all border-b-2 rounded-t-lg hover:bg-slate-800/30 whitespace-nowrap ${activeTab === tab.id ? "text-teal-400 border-teal-400 bg-slate-800/30" : "text-slate-400 border-transparent"}`}
                  >
                    <tab.icon className="w-4 h-4 mr-2" /> {tab.label}
                  </button>
                ))}
              </div>

                {/* Tab Content */}
                <div className="flex-1 overflow-hidden flex flex-col">
                  {activeTab === "code" ? (
                    <div className="p-8 h-full flex flex-col">
                     <div className="bg-[#0d1117] rounded-xl border border-slate-700/50 shadow-inner h-full flex overflow-hidden">
                       {/* FILE EXPLORER SIDEBAR */}
                       {results.files && results.files.length > 0 && (
                         <div className="w-48 bg-[#010409]/50 border-r border-slate-800 flex flex-col">
                           <div className="px-4 py-2 border-b border-slate-800 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                             Explorer
                           </div>
                           <div className="flex-1 overflow-y-auto py-2">
                             {results.files.map((file: string) => (
                               <button 
                                 key={file}
                                 onClick={() => loadFile(file)}
                                 className={`w-full text-left px-4 py-1.5 text-xs font-mono truncate transition-colors ${viewerPath === file ? "bg-teal-500/10 text-teal-400 border-l-2 border-teal-500" : "text-slate-400 hover:bg-slate-800 hover:text-slate-200 border-l-2 border-transparent"}`}
                               >
                                 {file.split('/').pop()}
                               </button>
                             ))}
                           </div>
                         </div>
                       )}

                       {/* CODE EDITOR PANE */}
                       <div className="flex-1 flex flex-col min-w-0">
                         <div className="bg-slate-900/80 px-4 py-2 border-b border-slate-800 flex items-center shrink-0">
                           <div className="flex space-x-2 mr-4">
                             <div className="w-3 h-3 rounded-full bg-slate-700" />
                             <div className="w-3 h-3 rounded-full bg-slate-700" />
                             <div className="w-3 h-3 rounded-full bg-slate-700" />
                           </div>
                           <p className="text-teal-500 font-mono text-xs truncate">{viewerPath || "No file selected"}</p>
                         </div>
                         <div className="p-4 overflow-y-auto flex-1 font-mono text-sm text-slate-300">
                           {viewerLoading ? (
                             <div className="flex items-center text-slate-500 h-full justify-center"><div className="w-5 h-5 border-2 border-slate-500 border-t-transparent rounded-full animate-spin mr-3" /> Loading file source...</div>
                           ) : viewerContent ? (
                             <pre className="whitespace-pre-wrap">{viewerContent}</pre>
                           ) : (
                             <div className="h-full flex flex-col items-center justify-center text-slate-600">
                               <Terminal className="w-12 h-12 mb-4 opacity-20" />
                               <p>Select a file from the explorer or click a cited file path in the chat.</p>
                             </div>
                           )}
                         </div>
                       </div>
                     </div>
                    </div>
                  ) : activeTab === "chat" ? (
                    <div className="flex flex-col h-full bg-[#0d1117] relative">
                      <div className="flex-1 p-6 overflow-y-auto space-y-6">
                        {chatMessages.map((msg, i) => (
                          <motion.div 
                            key={i}
                            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                          >
                            <div className={`max-w-[85%] rounded-2xl px-6 py-4 ${
                              msg.role === 'user' 
                                ? 'bg-teal-600 text-white shadow-lg shadow-teal-900/20 rounded-tr-sm' 
                                : 'bg-[#010409] text-slate-300 border border-slate-700/50 shadow-xl rounded-tl-sm prose prose-invert prose-teal max-w-none prose-pre:bg-slate-900/50 prose-pre:border prose-pre:border-slate-800'
                            }`}>
                              {msg.role === 'user' ? (
                                <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                              ) : (
                                <ReactMarkdown
                                  remarkPlugins={[remarkGfm]}
                                  components={{
                                    code({ node, inline, className, children, ...props }: any) {
                                      if (inline) return <code className="bg-slate-800/50 px-1.5 py-0.5 rounded text-slate-300" {...props}>{children}</code>;
                                      return <code className={className} {...props}>{children}</code>;
                                    }
                                  }}
                                >
                                  {msg.content}
                                </ReactMarkdown>
                              )}
                            </div>
                          </motion.div>
                        ))}
                        {isChatLoading && (
                          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
                            <div className="bg-[#010409] border border-slate-700/50 rounded-2xl rounded-tl-sm px-6 py-4 shadow-xl flex items-center space-x-3 text-slate-400">
                              <Loader2 className="w-5 h-5 animate-spin text-teal-500" />
                              <span className="text-sm font-medium animate-pulse">DevSensei is thinking...</span>
                            </div>
                          </motion.div>
                        )}
                        <div ref={messagesEndRef} />
                      </div>
                      
                      <div className="p-4 bg-[#0d1117] border-t border-slate-800">
                        <form onSubmit={handleChatSubmit} className="relative max-w-4xl mx-auto">
                          <input
                            type="text"
                            value={chatInput}
                            onChange={(e) => setChatInput(e.target.value)}
                            placeholder="Ask a question about your code..."
                            className="w-full bg-[#010409] border border-slate-700 text-white pl-4 pr-12 py-4 rounded-xl text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 shadow-inner transition-all"
                            disabled={isChatLoading}
                          />
                          <button 
                            type="submit" 
                            disabled={!chatInput.trim() || isChatLoading}
                            className="absolute right-2 top-2 bottom-2 aspect-square bg-teal-600 hover:bg-teal-500 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded-lg flex items-center justify-center transition-all shadow-lg"
                          >
                            <Send className="w-4 h-4" />
                          </button>
                        </form>
                      </div>
                    </div>
                  ) : (
                    <div className="p-8 overflow-y-auto">
                      <div className="prose prose-invert prose-teal max-w-none prose-headings:text-slate-100 prose-a:text-teal-400 prose-strong:text-slate-200">
                        <ReactMarkdown 
                          remarkPlugins={[remarkGfm]}
                          components={{
                            code({ node, inline, className, children, ...props }: any) {
                              const text = String(children);
                              if (inline && (text.includes('/') || text.endsWith('.py') || text.endsWith('.ts') || text.endsWith('.json') || text.endsWith('.yml') || text.endsWith('.js') || text.endsWith('.css') || text.endsWith('.html'))) {
                                return (
                                  <code 
                                    {...props} 
                                    onClick={() => loadFile(text)}
                                    className="cursor-pointer text-teal-300 hover:text-white hover:bg-teal-900/50 underline decoration-dashed decoration-teal-700/50 bg-teal-950/30 px-1.5 py-0.5 rounded transition-all duration-200"
                                    title={`View ${text} in Code Viewer`}
                                  >
                                    {children}
                                  </code>
                                );
                              }
                              return <code className={`${className} bg-slate-800/50 px-1.5 py-0.5 rounded text-slate-300`} {...props}>{children}</code>;
                            },
                            table({ children, ...props }: any) {
                              return <div className="overflow-x-auto w-full my-6 ring-1 ring-slate-800 rounded-lg bg-[#0d1117] shadow-xl"><table className="w-full text-left border-collapse" {...props}>{children}</table></div>;
                            },
                            th({ children, ...props }: any) {
                              return <th className="px-4 py-3 border-b border-slate-700 bg-slate-900/80 text-slate-200 font-medium text-sm whitespace-nowrap" {...props}>{children}</th>;
                            },
                            td({ children, ...props }: any) {
                              return <td className="px-4 py-3 border-b border-slate-800/50 text-slate-400 text-sm align-top leading-relaxed" {...props}>{children}</td>;
                            }
                          }}
                        >
                          {activeTab === "review" ? results.reviewer_notes : 
                           activeTab === "test" ? results.tester_notes : 
                           results.final_report || "No synthesized report generated."}
                        </ReactMarkdown>
                      </div>
                    </div>
                  )}
                </div>
            </motion.div>
          </div>
        ) : (
          /* EMPTY STATE */
          <div className="flex-1 flex flex-col items-center justify-center relative overflow-hidden">
            <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-5 mix-blend-overlay" />
            <div className="absolute w-96 h-96 bg-teal-500/10 rounded-full blur-3xl -top-20 -left-20 pointer-events-none" />
            <div className="absolute w-96 h-96 bg-blue-500/10 rounded-full blur-3xl bottom-0 right-0 pointer-events-none" />
            
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="relative z-10 flex flex-col items-center text-center">
              <div className="w-24 h-24 mb-8 rounded-2xl bg-gradient-to-br from-teal-500/20 to-blue-500/20 flex items-center justify-center shadow-2xl shadow-teal-900/20 border border-white/5 backdrop-blur-xl">
                <ShieldCheck className="w-12 h-12 text-teal-400" />
              </div>
              <h2 className="text-4xl font-bold text-white mb-4 tracking-tight">AI-Powered PR Reviews</h2>
              <p className="text-lg max-w-lg text-slate-400 leading-relaxed mb-8">
                DevSensei analyzes your codebase, identifies security risks, generates tests, and architects solutions in real-time.
              </p>
              
              <div className="flex space-x-4">
                <div className="flex items-center text-sm text-slate-500 bg-slate-900/50 px-4 py-2 rounded-full border border-slate-800">
                  <Database className="w-4 h-4 mr-2 text-teal-500" /> ChromaDB RAG
                </div>
                <div className="flex items-center text-sm text-slate-500 bg-slate-900/50 px-4 py-2 rounded-full border border-slate-800">
                  <Activity className="w-4 h-4 mr-2 text-blue-500" /> LangGraph Agents
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </div>
    </div>
  );
}
