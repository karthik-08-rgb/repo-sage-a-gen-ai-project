import React, { useState, useEffect, useRef } from 'react';
import Editor, { OnMount } from '@monaco-editor/react';
import {
  FileCode2,
  Folder,
  Search,
  ChevronRight,
  ChevronDown,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { RepositoryFileItem, FileContent } from '../../types';
import { api } from '../../api/client';

interface CodeViewerProps {
  repositoryId: string;
  files: RepositoryFileItem[];
  selectedPath?: string;
  targetLine?: number;
  highlightRange?: [number, number];
  onSelectFile?: (path: string) => void;
}

export const CodeViewer: React.FC<CodeViewerProps> = ({
  repositoryId,
  files,
  selectedPath,
  targetLine,
  highlightRange,
  onSelectFile,
}) => {
  const [activeFile, setActiveFile] = useState<string>(selectedPath || '');
  const [fileContent, setFileContent] = useState<FileContent | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const editorRef = useRef<any>(null);

  useEffect(() => {
    if (selectedPath) {
      setActiveFile(selectedPath);
    } else if (files.length > 0 && !activeFile) {
      // Pick first non-markdown/code file or first file
      setActiveFile(files[0].file_path);
    }
  }, [selectedPath, files]);

  useEffect(() => {
    if (!activeFile || !repositoryId) return;

    const fetchContent = async () => {
      setLoading(true);
      try {
        const data = await api.getFileContent(repositoryId, activeFile);
        setFileContent(data);
      } catch (err) {
        console.error('Failed to load file content:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchContent();
  }, [activeFile, repositoryId]);

  const handleEditorMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;

    if (targetLine) {
      editor.revealLineInCenter(targetLine);
      editor.setPosition({ lineNumber: targetLine, column: 1 });
    }

    if (highlightRange) {
      editor.deltaDecorations(
        [],
        [
          {
            range: new monaco.Range(highlightRange[0], 1, highlightRange[1], 1),
            options: {
              isWholeLine: true,
              className: 'bg-emerald-500/20 border-l-2 border-emerald-400',
            },
          },
        ]
      );
    }
  };

  useEffect(() => {
    if (editorRef.current && targetLine) {
      editorRef.current.revealLineInCenter(targetLine);
      editorRef.current.setPosition({ lineNumber: targetLine, column: 1 });
    }
  }, [targetLine]);

  const filteredFiles = files.filter((f) =>
    f.file_path.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getMonacoLanguage = (lang?: string) => {
    if (!lang) return 'plaintext';
    const map: Record<string, string> = {
      python: 'python',
      javascript: 'javascript',
      typescript: 'typescript',
      json: 'json',
      yaml: 'yaml',
      markdown: 'markdown',
      sql: 'sql',
      dockerfile: 'dockerfile',
      shell: 'shell',
      c: 'c',
      cpp: 'cpp',
      csharp: 'csharp',
      go: 'go',
      rust: 'rust',
      java: 'java',
    };
    return map[lang.toLowerCase()] || 'plaintext';
  };

  return (
    <div className="flex h-[750px] rounded-xl border border-[#30363d] bg-[#0d1117] overflow-hidden">
      {/* File Tree Sidebar */}
      <div className="w-72 bg-[#161b22] border-r border-[#30363d] flex flex-col">
        <div className="p-3 border-b border-[#30363d]">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-[#8b949e] absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search files..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-[#0d1117] text-xs text-[#c9d1d9] pl-8 pr-3 py-1.5 rounded-md border border-[#30363d] focus:border-emerald-500/50 focus:outline-none"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {filteredFiles.map((f) => {
            const isSelected = f.file_path === activeFile;
            return (
              <button
                key={f.id}
                onClick={() => {
                  setActiveFile(f.file_path);
                  if (onSelectFile) onSelectFile(f.file_path);
                }}
                className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs font-mono text-left transition-colors truncate ${
                  isSelected
                    ? 'bg-emerald-500/15 text-emerald-400 font-semibold border border-emerald-500/30'
                    : 'text-[#8b949e] hover:bg-[#21262d] hover:text-[#c9d1d9]'
                }`}
              >
                <FileCode2 className={`w-3.5 h-3.5 shrink-0 ${isSelected ? 'text-emerald-400' : 'text-[#8b949e]'}`} />
                <span className="truncate">{f.file_path}</span>
              </button>
            );
          })}
          {filteredFiles.length === 0 && (
            <div className="p-4 text-center text-xs text-[#8b949e]">No files matching search.</div>
          )}
        </div>
      </div>

      {/* Editor Panel */}
      <div className="flex-1 flex flex-col bg-[#0d1117]">
        {/* Editor Tab Bar */}
        <div className="h-10 bg-[#161b22] border-b border-[#30363d] flex items-center justify-between px-4">
          <div className="flex items-center gap-2 text-xs font-mono text-[#c9d1d9]">
            <FileCode2 className="w-4 h-4 text-emerald-400" />
            <span className="font-medium">{activeFile || 'No file selected'}</span>
          </div>
          {fileContent && (
            <div className="flex items-center gap-3 text-[11px] text-[#8b949e] font-mono">
              <span>{fileContent.total_lines} lines</span>
              <span>{(fileContent.file_size / 1024).toFixed(1)} KB</span>
              <span className="uppercase px-1.5 py-0.5 rounded bg-[#21262d] text-emerald-400">
                {fileContent.language || 'Code'}
              </span>
            </div>
          )}
        </div>

        {/* Editor Main */}
        <div className="flex-1 relative">
          {loading ? (
            <div className="absolute inset-0 flex items-center justify-center bg-[#0d1117]/80 z-10">
              <div className="flex items-center gap-2 text-sm text-emerald-400">
                <Loader2 className="w-5 h-5 animate-spin" />
                Loading file content...
              </div>
            </div>
          ) : fileContent ? (
            <Editor
              height="100%"
              language={getMonacoLanguage(fileContent.language)}
              value={fileContent.content}
              theme="vs-dark"
              options={{
                readOnly: true,
                minimap: { enabled: true },
                fontSize: 13,
                fontFamily: "'JetBrains Mono', monospace",
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                automaticLayout: true,
                padding: { top: 12 },
              }}
              onMount={handleEditorMount}
            />
          ) : (
            <div className="h-full flex items-center justify-center text-xs text-[#8b949e]">
              Select a file from the tree to view its source code.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
