import React, { useEffect, useState, useRef } from 'react';
import { api } from '../../services/api';
import type { GraphNode, ChatSession, ChatMessage } from '../../types';
import { ReactorCore, type ReactorState } from '../reactor/ReactorCore';
import { 
  Send, 
  Terminal, 
  Layers, 
  Code, 
  Link, 
  ChevronRight,
  Sparkles,
  Cpu
} from 'lucide-react';

interface ChatProps {
  selectedRepoId: string | undefined;
  selectedNode: GraphNode | null;
  onCitationClick: (filePath: string, symbolName?: string) => void;
  analyzing?: boolean;
}

export const ChatPanel: React.FC<ChatProps> = ({
  selectedRepoId,
  selectedNode,
  onCitationClick,
  analyzing = false,
}) => {
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Derive Reactor State
  let reactorState: ReactorState = 'IDLE';
  let reactorSubtext = 'CORE NOMINAL // IDLE';

  if (analyzing) {
    reactorState = 'ANALYZING';
    reactorSubtext = 'ANALYSIS PIPELINE ACTIVE';
  } else if (sending) {
    reactorState = 'THINKING';
    reactorSubtext = 'GITTY INFERENCE PROCESSING';
  } else if (selectedNode && selectedNode.security_score !== null && selectedNode.security_score !== undefined && selectedNode.security_score < 70) {
    reactorState = 'ALERT';
    reactorSubtext = 'VULNERABILITY DETECTED';
  }

  // Initialize or load session on repo change
  useEffect(() => {
    if (!selectedRepoId) {
      setSession(null);
      setMessages([]);
      return;
    }

    setSession(null);
    setMessages([]);

    api.createChatSession(selectedRepoId)
      .then((sess) => {
        setSession(sess);
        setMessages(sess.messages || []);
      })
      .catch(console.error);
  }, [selectedRepoId]);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || !session || sending) return;

    const userText = inputText;
    setInputText('');
    setSending(true);

    const tempUserMsg: ChatMessage = {
      message_id: Math.random().toString(),
      session_id: session.session_id,
      role: 'user',
      content: userText,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, tempUserMsg]);

    let queryText = userText;
    if (selectedNode) {
      const lineRange = selectedNode.start_line !== undefined && selectedNode.end_line !== undefined
        ? ` (Lines: ${selectedNode.start_line}-${selectedNode.end_line})`
        : '';
      
      queryText = `[Selected Node: ${selectedNode.label} (Type: ${selectedNode.node_type}), File: ${selectedNode.file_path || 'unknown'}${lineRange}]\n\n${userText}`;
    }

    try {
      const assistantReply = await api.sendChatMessage(session.session_id, queryText);
      setMessages(prev => [...prev, assistantReply]);
    } catch (err: any) {
      console.error(err);
      if (err.status === 404 && selectedRepoId) {
        try {
          const newSess = await api.createChatSession(selectedRepoId);
          setSession(newSess);
          const assistantReply = await api.sendChatMessage(newSess.session_id, queryText);
          setMessages(prev => [...prev, assistantReply]);
          return;
        } catch (retryErr) {
          console.error("Retry failed:", retryErr);
        }
      }

      const errMsg: ChatMessage = {
        message_id: Math.random().toString(),
        session_id: session.session_id,
        role: 'assistant',
        content: 'System error: Unable to complete inference request. Verify backend telemetry and LLM gateway status.',
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div 
      className="console-panel gitty-core-panel"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden'
      }}
    >
      {/* Panel Technical Header */}
      <div style={{
        padding: '12px 14px',
        borderBottom: '1px solid var(--hairline)',
        background: 'var(--bg-raised)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Cpu size={14} style={{ color: 'var(--accent-amber)' }} />
          <span className="tech-header">GITTY CORE</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span className="status-dot status-dot-green" />
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '9.5px',
            letterSpacing: '0.08em',
            color: 'var(--status-green)',
            fontWeight: 600
          }}>
            ONLINE
          </span>
        </div>
      </div>

      {/* Mechanical Reactor Core Display Module */}
      <div style={{
        padding: '14px',
        background: 'var(--bg-panel)',
        borderBottom: '1px solid var(--hairline)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        position: 'relative'
      }}>
        <div style={{
          position: 'absolute',
          top: '8px',
          left: '12px',
          fontFamily: 'var(--font-mono)',
          fontSize: '9px',
          color: 'var(--ink-muted)',
          letterSpacing: '0.08em'
        }}>
          REACTOR CORE // DEPTH MATRIX
        </div>

        <div style={{
          position: 'absolute',
          top: '8px',
          right: '12px',
          fontFamily: 'var(--font-mono)',
          fontSize: '9px',
          color: 'var(--accent-amber-bright)',
          letterSpacing: '0.08em'
        }}>
          STATE: {reactorState}
        </div>

        <div style={{ marginTop: '10px' }}>
          <ReactorCore 
            state={reactorState} 
            size={116} 
            subtext={reactorSubtext} 
          />
        </div>
      </div>

      {/* Focused Node HUD Pill */}
      {selectedNode && (
        <div style={{
          padding: '8px 12px',
          background: 'rgba(240, 164, 34, 0.07)',
          borderBottom: '1px solid rgba(240, 164, 34, 0.2)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontFamily: 'var(--font-mono)',
          fontSize: '11px',
          flexShrink: 0
        }}>
          <Layers size={13} style={{ color: 'var(--accent-amber)' }} />
          <span style={{ color: 'var(--ink-muted)' }}>TARGET:</span>
          <span style={{ color: 'var(--accent-amber-bright)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {selectedNode.label}
          </span>
          <span style={{
            fontSize: '9.5px',
            color: 'var(--ink-muted)',
            marginLeft: 'auto',
            background: 'var(--bg-ground)',
            padding: '2px 6px',
            borderRadius: '3px',
            border: '1px solid var(--hairline)'
          }}>
            {selectedNode.node_type}
          </span>
        </div>
      )}

      {/* Messages Stream */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '14px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}>
        {messages.length === 0 && (
          <div style={{
            textAlign: 'center',
            padding: '24px 12px',
            color: 'var(--ink-muted)',
            fontFamily: 'var(--font-mono)',
            fontSize: '11px'
          }}>
            <Terminal size={24} style={{ color: 'var(--ink-faint)', margin: '0 auto 8px auto', display: 'block' }} />
            <div>GITTY REASONING ENGINE READY</div>
            <div style={{ fontSize: '10px', marginTop: '4px', color: 'var(--ink-faint)' }}>
              Ask about repository architecture, security vulnerabilities, dependencies, or call paths.
            </div>
          </div>
        )}

        {messages.map((msg) => {
          const isUser = msg.role === 'user';
          const displayContent = isUser 
            ? msg.content.replace(/^\[Selected Node:.*\]\n\n/, '')
            : msg.content;

          return (
            <div 
              key={msg.message_id}
              style={{
                alignSelf: isUser ? 'flex-end' : 'flex-start',
                maxWidth: '90%',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px'
              }}
            >
              <div style={{
                background: isUser ? 'var(--bg-raised)' : 'var(--bg-ground)',
                border: '1px solid',
                borderColor: isUser ? 'var(--accent-amber)' : 'var(--hairline)',
                borderRadius: '6px',
                padding: '10px 12px',
                fontSize: '12px',
                lineHeight: '1.5',
                color: 'var(--ink-primary)',
                fontFamily: isUser ? 'var(--font-heading)' : 'var(--font-mono)',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word'
              }}>
                {displayContent}

                {/* Source Citations */}
                {!isUser && msg.citations && msg.citations.length > 0 && (
                  <div style={{
                    marginTop: '10px',
                    paddingTop: '8px',
                    borderTop: '1px solid var(--hairline)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px'
                  }}>
                    <div style={{
                      fontSize: '9.5px',
                      color: 'var(--ink-muted)',
                      letterSpacing: '0.06em',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}>
                      <Link size={10} /> REFERRED SYMBOLS
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginTop: '3px' }}>
                      {msg.citations.map((cit, idx) => (
                        <button
                          key={idx}
                          onClick={() => onCitationClick(cit.file_path, cit.symbol_name)}
                          className="console-btn"
                          style={{
                            fontSize: '10px',
                            padding: '2px 6px',
                            borderColor: 'rgba(240, 164, 34, 0.3)',
                            color: 'var(--accent-amber-bright)',
                            gap: '4px'
                          }}
                        >
                          <Code size={10} />
                          <span>{cit.symbol_name || cit.file_path.split('/').pop()}</span>
                          <ChevronRight size={10} />
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <span style={{
                fontSize: '9.5px',
                fontFamily: 'var(--font-mono)',
                color: 'var(--ink-muted)',
                alignSelf: isUser ? 'flex-end' : 'flex-start'
              }}>
                {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                {!isUser && msg.metadata?.latency_ms && ` • ${msg.metadata.latency_ms}ms`}
              </span>
            </div>
          );
        })}

        {sending && (
          <div style={{
            alignSelf: 'flex-start',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 12px',
            background: 'var(--bg-ground)',
            border: '1px solid var(--hairline)',
            borderRadius: '6px'
          }}>
            <Sparkles size={12} style={{ color: 'var(--accent-amber)', animation: 'spin 2s linear infinite' }} />
            <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--ink-muted)' }}>
              Synthesizing context across graph...
            </span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Console Input Footer */}
      <form 
        onSubmit={handleSendMessage}
        style={{
          padding: '10px 12px',
          borderTop: '1px solid var(--hairline)',
          background: 'var(--bg-panel)',
          display: 'flex',
          gap: '8px',
          flexShrink: 0
        }}
      >
        <input 
          type="text"
          placeholder="Instruct Gitty AI..."
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          className="console-input"
          style={{ flex: 1, fontSize: '11.5px' }}
          disabled={sending}
        />
        <button
          type="submit"
          className="console-btn console-btn-primary"
          style={{ padding: '6px 12px', flexShrink: 0 }}
          disabled={sending || !inputText.trim()}
        >
          <Send size={13} />
        </button>
      </form>
    </div>
  );
};
