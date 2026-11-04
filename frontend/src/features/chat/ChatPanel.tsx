import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Sparkles,
  Bot,
  User,
  FileCode2,
  ExternalLink,
  Loader2,
  MessageSquare,
  HelpCircle,
  Copy,
  Check,
  Cpu,
} from 'lucide-react';
import { ChatMessage, ChatSession, CitationItem } from '../../types';
import { api } from '../../api/client';

interface ChatPanelProps {
  repositoryId: string;
  onCitationClick: (filePath: string, startLine: number, endLine: number) => void;
}

const SUGGESTED_QUESTIONS = [
  'Explain the overall architecture and folder structure of this project.',
  'Where is user authentication and session management implemented?',
  'How does database indexing and retrieval work in this codebase?',
  'Which classes and functions handle API routing?',
];

export const ChatPanel: React.FC<ChatPanelProps> = ({ repositoryId, onCitationClick }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | undefined>(undefined);
  const [inputQuery, setInputQuery] = useState('');
  const [isAgentMode, setIsAgentMode] = useState<boolean>(false);
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const loadSessions = async () => {
      try {
        const sess = await api.getSessions(repositoryId);
        setSessions(sess);
        if (sess.length > 0) {
          setActiveSessionId(sess[0].id);
        }
      } catch (err) {
        console.error('Failed to load chat sessions:', err);
      }
    };
    if (repositoryId) loadSessions();
  }, [repositoryId]);

  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }
    const loadMessages = async () => {
      try {
        const msgs = await api.getSessionMessages(activeSessionId);
        setMessages(msgs);
      } catch (err) {
        console.error('Failed to load session messages:', err);
      }
    };
    loadMessages();
  }, [activeSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (queryText?: string) => {
    const question = (queryText || inputQuery).trim();
    if (!question || loading) return;

    setInputQuery('');
    setLoading(true);

    // Optimistic user message
    const tempUserMsg: ChatMessage = {
      id: `temp-${Date.now()}`,
      session_id: activeSessionId || '',
      role: 'user',
      content: question,
      citations: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      let assistantMsg: ChatMessage;

      if (isAgentMode) {
        const agentRes = await api.runAgentWorkflow({
          repository_id: repositoryId,
          query: question,
          session_id: activeSessionId,
        });

        const formattedContent = `### Autonomous Agent Analysis (${agentRes.intent.toUpperCase()})\n${agentRes.direct_answer}${
          agentRes.explanation ? `\n\n### Architectural Explanation\n${agentRes.explanation}` : ''
        }${agentRes.execution_flow ? `\n\n### Execution Flow\n${agentRes.execution_flow}` : ''}\n\n> 🤖 **Agent Pipeline Trace**:\n> ${agentRes.execution_log.join(' ➔ ')}`;

        assistantMsg = {
          id: `agent-${Date.now()}`,
          session_id: agentRes.session_id || activeSessionId || '',
          role: 'assistant',
          content: formattedContent,
          citations: agentRes.citations || [],
          model: 'reposage-agent-v1',
          created_at: new Date().toISOString(),
        };

        if (!activeSessionId && agentRes.session_id) {
          setActiveSessionId(agentRes.session_id);
          const updatedSessions = await api.getSessions(repositoryId);
          setSessions(updatedSessions);
        }
      } else {
        assistantMsg = await api.sendMessage({
          repository_id: repositoryId,
          question,
          session_id: activeSessionId,
        });

        if (!activeSessionId) {
          setActiveSessionId(assistantMsg.session_id);
          const updatedSessions = await api.getSessions(repositoryId);
          setSessions(updatedSessions);
        }
      }

      setMessages((prev) => [...prev.filter((m) => m.id !== tempUserMsg.id), tempUserMsg, assistantMsg]);
    } catch (err: any) {
      console.error('Failed to send question:', err);
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        session_id: activeSessionId || '',
        role: 'assistant',
        content: `Error: ${err.response?.data?.message || err.message || 'Failed to generate answer.'}`,
        citations: [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = (content: string, id: string) => {
    navigator.clipboard.writeText(content);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="flex h-[750px] rounded-xl border border-[#30363d] bg-[#0d1117] overflow-hidden">
      {/* Sessions Left Drawer */}
      <div className="w-64 bg-[#161b22] border-r border-[#30363d] flex flex-col">
        <div className="p-3 border-b border-[#30363d] flex items-center justify-between">
          <span className="text-xs font-semibold text-[#8b949e] uppercase tracking-wider">Conversations</span>
          <button
            onClick={() => {
              setActiveSessionId(undefined);
              setMessages([]);
            }}
            className="text-[11px] text-emerald-400 hover:text-emerald-300 font-medium"
          >
            + New
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveSessionId(s.id)}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-xs text-left truncate transition-colors ${
                s.id === activeSessionId
                  ? 'bg-emerald-500/15 text-emerald-400 font-medium border border-emerald-500/30'
                  : 'text-[#8b949e] hover:bg-[#21262d] hover:text-[#c9d1d9]'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">{s.title}</span>
            </button>
          ))}
          {sessions.length === 0 && (
            <div className="p-4 text-center text-xs text-[#8b949e]">No conversation history yet.</div>
          )}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col bg-[#0d1117]">
        {/* Messages Scroll Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 && (
            <div className="max-w-xl mx-auto py-12 text-center space-y-6">
              <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center mx-auto">
                <Sparkles className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-white">Ask your Codebase</h3>
                <p className="text-xs text-[#8b949e] mt-1">
                  RepoSage retrieves indexed code symbols, understands dependencies, and cites verified line numbers.
                </p>
              </div>

              {/* Starter Prompt Chips */}
              <div className="grid grid-cols-1 gap-2 pt-2 text-left">
                {SUGGESTED_QUESTIONS.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(q)}
                    className="p-3 rounded-lg bg-[#161b22] hover:bg-[#21262d] border border-[#30363d] hover:border-emerald-500/30 text-xs text-[#c9d1d9] transition-all flex items-start gap-2.5 text-left"
                  >
                    <HelpCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{q}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m) => {
            const isUser = m.role === 'user';
            return (
              <div
                key={m.id}
                className={`flex gap-3 max-w-3xl ${isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}
              >
                <div
                  className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold ${
                    isUser
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                  }`}
                >
                  {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>

                <div
                  className={`rounded-xl p-4 text-xs leading-relaxed max-w-2xl border ${
                    isUser
                      ? 'bg-emerald-500/10 border-emerald-500/20 text-[#e6edf3]'
                      : 'bg-[#161b22] border-[#30363d] text-[#c9d1d9]'
                  }`}
                >
                  <div className="flex items-center justify-between pb-2 border-b border-[#30363d]/60 mb-2">
                    <span className="font-semibold text-[11px] uppercase tracking-wider text-[#8b949e]">
                      {isUser ? 'You' : 'RepoSage Assistant'}
                    </span>
                    {!isUser && (
                      <button
                        onClick={() => handleCopy(m.content, m.id)}
                        className="text-[#8b949e] hover:text-[#c9d1d9] transition-colors p-1"
                        title="Copy Response"
                      >
                        {copiedId === m.id ? (
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    )}
                  </div>

                  {/* Body Content */}
                  <div className="whitespace-pre-wrap font-sans">{m.content}</div>

                  {/* Citations Panel */}
                  {m.citations && m.citations.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-[#30363d]">
                      <div className="text-[11px] font-semibold text-[#8b949e] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                        <FileCode2 className="w-3.5 h-3.5 text-emerald-400" />
                        Grounded Source Citations ({m.citations.length})
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {m.citations.map((c, idx) => (
                          <button
                            key={idx}
                            onClick={() => onCitationClick(c.file_path, c.start_line, c.end_line)}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#0d1117] hover:bg-[#21262d] border border-[#30363d] hover:border-emerald-500/40 text-[11px] font-mono text-emerald-400 transition-colors"
                            title="Click to jump to line in Code Viewer"
                          >
                            <span>
                              {c.file_path}:{c.start_line}-{c.end_line}
                            </span>
                            {c.symbol_name && (
                              <span className="text-[#8b949e] font-sans">({c.symbol_name})</span>
                            )}
                            <ExternalLink className="w-2.5 h-2.5 opacity-60" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {loading && (
            <div className="flex gap-3 max-w-xl mr-auto">
              <div className="w-7 h-7 rounded-lg bg-purple-500/20 text-purple-400 border border-purple-500/30 flex items-center justify-center shrink-0">
                <Loader2 className="w-4 h-4 animate-spin" />
              </div>
              <div className="p-3 rounded-xl bg-[#161b22] border border-[#30363d] text-xs text-[#8b949e] flex items-center gap-2">
                <span>Retrieving code chunks and synthesizing grounded answer...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-[#30363d] bg-[#161b22]/50 space-y-2.5">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setIsAgentMode(false)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                  !isAgentMode
                    ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-semibold'
                    : 'text-[#8b949e] hover:text-[#c9d1d9]'
                }`}
              >
                <Sparkles className="w-3 h-3" />
                Standard RAG
              </button>
              <button
                type="button"
                onClick={() => setIsAgentMode(true)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                  isAgentMode
                    ? 'bg-purple-500/15 text-purple-400 border border-purple-500/30 font-semibold'
                    : 'text-[#8b949e] hover:text-[#c9d1d9]'
                }`}
              >
                <Cpu className="w-3 h-3" />
                Autonomous Agent Workflow
              </button>
            </div>
            {isAgentMode && (
              <span className="text-[10px] text-purple-400 font-mono">
                Multi-step intent understanding & AST analysis active
              </span>
            )}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              placeholder="Ask a question about this repository's code, architecture, or logic..."
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              disabled={loading}
              className="flex-1 bg-[#0d1117] text-xs text-[#c9d1d9] px-4 py-2.5 rounded-lg border border-[#30363d] focus:border-emerald-500/50 focus:outline-none placeholder-[#8b949e]/60"
            />
            <button
              type="submit"
              disabled={loading || !inputQuery.trim()}
              className="px-4 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 disabled:opacity-40 text-black font-semibold text-xs flex items-center gap-1.5 transition-colors shadow-sm"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              <span>Send</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
