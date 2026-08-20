"use client";

import { useState, useEffect } from "react";
import { Terminal, Code, Settings, Bug, Play, GitBranch, ShieldCheck, Database, LayoutTemplate, Activity, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import mermaid from "mermaid";
import { motion } from "framer-motion";

const MermaidDiagram = ({ chart }: { chart: string }) => {
  const [svg, setSvg] = useState<string>("");

  useEffect(() => {
    mermaid.initialize({ startOnLoad: false, theme: "dark", background: "transparent" });
    const id = `mermaid-${Math.random().toString(36).substring(7)}`;
    mermaid.render(id, chart).then((res) => setSvg(res.svg)).catch(console.error);
  }, [chart]);

  return (
    <div 
      className="flex justify-center p-4 bg-slate-900/50 rounded-lg border border-slate-700/50 my-4 shadow-inner"
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
  const [viewerPath, setViewerPath] = useState<string>("");
  const [viewerContent, setViewerContent] = useState<string>("");
  const [viewerLoading, setViewerLoading] = useState<boolean>(false);

  // Phase 5: PR Config Modal
  const [showPrModal, setShowPrModal] = useState(false);

  const [activeTab, setActiveTab] = useState<"chat" | "review" | "test" | "code">("review");

  const loadFile = async (path: string) => {
    setActiveTab("code");
    setViewerPath(path);
    setViewerLoading(true);
    try {
      // Clean path if it has backticks
      const cleanPath = path.replace(/`/g, "").trim();
      const res = await fetch(`http://localhost:8000/file?path=${encodeURIComponent(cleanPath)}`);
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
      <div className="w-64 bg-[#010409] border-r border-slate-800 flex flex-col shadow-2xl z-10">
        <div className="h-16 flex items-center px-6 border-b border-slate-800">
          <Terminal className="w-6 h-6 text-teal-400 mr-3" />
          <h1 className="text-xl font-bold text-white tracking-tight">DevSensei</h1>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <button className="w-full flex items-center px-4 py-3 bg-teal-500/10 text-teal-400 rounded-lg font-medium border border-teal-500/20 transition-all">
            <LayoutTemplate className="w-4 h-4 mr-3" /> Onboarder
          </button>
          <button onClick={() => setShowPrModal(true)} className="w-full flex items-center px-4 py-3 text-slate-400 hover:bg-slate-800/50 hover:text-white rounded-lg transition-all">
            <GitBranch className="w-4 h-4 mr-3" /> PR Bot Config
          </button>
        </nav>
        <div className="p-4 border-t border-slate-800 text-xs text-slate-500 flex items-center justify-between">
          <span>DevSensei v0.6.0</span>
          <Settings className="w-4 h-4 cursor-pointer hover:text-slate-300 transition-colors" />
        </div>
      </div>

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
          <div className="flex-1 flex flex-col items-center justify-center p-8 overflow-hidden">
            <div className="w-full max-w-2xl bg-[#010409] border border-slate-800 rounded-xl shadow-2xl overflow-hidden flex flex-col h-96">
              <div className="bg-slate-900 border-b border-slate-800 p-4 flex items-center">
                 <Activity className="w-5 h-5 text-teal-400 mr-3 animate-pulse" />
                 <h3 className="font-semibold text-slate-200">Real-time Ingestion Pipeline</h3>
              </div>
              <div className="p-6 flex-1 overflow-y-auto space-y-3 font-mono text-sm">
                {logs.map((log, i) => (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                    key={i} className="flex items-start text-teal-400/80"
                  >
                    <span className="mr-3 opacity-50">[{new Date().toLocaleTimeString().split(' ')[0]}]</span>
                    {log}
                  </motion.div>
                ))}
                <div ref={(el) => el?.scrollIntoView({ behavior: 'smooth' })} />
              </div>
            </div>
          </div>
        ) : results ? (
          /* SPLIT PANE RESULTS */
          <div className="flex-1 flex overflow-hidden">
            {/* LEFT PANE: DIAGRAM (Architect) */}
            <motion.div 
              initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}
              className="w-1/2 border-r border-slate-800 p-6 overflow-y-auto bg-gradient-to-br from-[#0d1117] to-[#010409]"
            >
              <div className="flex items-center space-x-2 mb-6 text-teal-400">
                <Database className="w-5 h-5" />
                <h2 className="text-lg font-semibold text-white">System Architecture</h2>
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
                  }}
                >
                  {results.architect_notes}
                </ReactMarkdown>
              </div>
            </motion.div>

            {/* RIGHT PANE: ANALYSIS / CHAT */}
            <motion.div 
              initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
              className="w-1/2 flex flex-col bg-[#0d1117]"
            >
              {/* Tabs */}
              <div className="flex border-b border-slate-800 px-6 pt-4 space-x-6 bg-[#010409]">
                <button 
                  onClick={() => setActiveTab("review")}
                  className={`pb-3 font-medium text-sm flex items-center transition-all ${activeTab === "review" ? "text-teal-400 border-b-2 border-teal-400" : "text-slate-500 hover:text-slate-300"}`}
                >
                  <ShieldCheck className="w-4 h-4 mr-2" /> Security Review
                </button>
                <button 
                  onClick={() => setActiveTab("test")}
                  className={`pb-3 font-medium text-sm flex items-center transition-all ${activeTab === "test" ? "text-teal-400 border-b-2 border-teal-400" : "text-slate-500 hover:text-slate-300"}`}
                >
                  <Bug className="w-4 h-4 mr-2" /> Test Coverage
                </button>
                <button 
                  onClick={() => setActiveTab("chat")}
                  className={`pb-3 font-medium text-sm flex items-center transition-all ${activeTab === "chat" ? "text-teal-400 border-b-2 border-teal-400" : "text-slate-500 hover:text-slate-300"}`}
                >
                  <Code className="w-4 h-4 mr-2" /> Synthesizer
                </button>
                <button 
                  onClick={() => setActiveTab("code")}
                  className={`pb-3 font-medium text-sm flex items-center transition-all ${activeTab === "code" ? "text-teal-400 border-b-2 border-teal-400" : "text-slate-500 hover:text-slate-300"}`}
                >
                  <Terminal className="w-4 h-4 mr-2" /> Code Viewer
                </button>
              </div>

              {/* Tab Content */}
              <div className="flex-1 p-6 overflow-y-auto">
                <div className="prose prose-invert prose-teal max-w-none prose-headings:text-slate-200 prose-a:text-teal-400">
                  {activeTab === "code" ? (
                     <div className="p-4 bg-[#010409] rounded-lg border border-slate-800 font-mono text-sm text-slate-300 h-full overflow-y-auto">
                       <p className="text-teal-500 mb-4 font-bold">// Code Viewer: {viewerPath || "No file selected"}</p>
                       {viewerLoading ? (
                         <div className="flex items-center text-slate-500"><div className="w-4 h-4 border-2 border-slate-500 border-t-transparent rounded-full animate-spin mr-2" /> Loading file...</div>
                       ) : viewerContent ? (
                         <pre className="whitespace-pre-wrap">{viewerContent}</pre>
                       ) : (
                         <div>
                           <p className="mb-2 text-slate-500">Clicking a cited file path in the chat will automatically load the file contents here.</p>
                         </div>
                       )}
                     </div>
                  ) : (
                    <ReactMarkdown 
                      remarkPlugins={[remarkGfm]}
                      components={{
                        code({ node, inline, className, children, ...props }: any) {
                          const text = String(children);
                          if (inline && (text.includes('/') || text.endsWith('.py') || text.endsWith('.ts') || text.endsWith('.json') || text.endsWith('.yml'))) {
                            return (
                              <code 
                                {...props} 
                                onClick={() => loadFile(text)}
                                className="cursor-pointer text-teal-300 hover:text-teal-100 underline decoration-dashed decoration-teal-700 bg-teal-950/30 px-1 py-0.5 rounded transition-colors"
                                title={`View ${text} in Code Viewer`}
                              >
                                {children}
                              </code>
                            );
                          }
                          return <code className={className} {...props}>{children}</code>;
                        }
                      }}
                    >
                      {activeTab === "review" ? results.reviewer_notes : 
                       activeTab === "test" ? results.tester_notes : 
                       results.final_report || "No synthesized report generated."}
                    </ReactMarkdown>
                  )}
                </div>
              </div>
            </motion.div>
          </div>
        ) : (
          /* EMPTY STATE */
          <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
            <div className="w-24 h-24 mb-6 rounded-full bg-slate-800/30 flex items-center justify-center shadow-inner border border-slate-700/30">
              <Code className="w-10 h-10 text-slate-600" />
            </div>
            <h2 className="text-xl font-medium text-slate-300 mb-2">DevSensei is ready</h2>
            <p className="text-sm max-w-md text-center leading-relaxed mt-2">
              Enter a repository path above and click <strong className="text-slate-400">Start Ingestion</strong> to generate the live Mermaid architecture graph and deep PR analysis.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
