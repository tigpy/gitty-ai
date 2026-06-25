import React, { useEffect, useState, useRef } from 'react';
import { api } from '../../services/api';
import type { GraphNode, ChatSession, ChatMessage } from '../../types';
import { 
  Send, 
  MessageSquare, 
  Layers, 
  Code,
  Sparkles,
  Link,
  ChevronRight
} from 'lucide-react';

interface ChatProps {
  selectedRepoId: string | undefined;
  selectedNode: GraphNode | null;
  onCitationClick: (filePath: string, symbolName?: string) => void;
}

export const ChatPanel: React.FC<ChatProps> = ({
  selectedRepoId,
  selectedNode,
  onCitationClick,
}) => {
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

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

    // 1. Add user message locally for responsive UI
    const tempUserMsg: ChatMessage = {
      message_id: Math.random().toString(),
      session_id: session.session_id,
      role: 'user',
      content: userText,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, tempUserMsg]);

    // 2. Build enriched query with node context if selected
    let queryText = userText;
    if (selectedNode) {
      const lineRange = selectedNode.start_line !== undefined && selectedNode.end_line !== undefined
        ? ` (Lines: ${selectedNode.start_line}-${selectedNode.end_line})`
        : '';
      
      queryText = `[Selected Node: ${selectedNode.label} (Type: ${selectedNode.node_type}), File: ${selectedNode.file_path || 'unknown'}${lineRange}]\n\n${userText}`;
    }

    try {
      // 3. Send message to API Gateway
      const assistantReply = await api.sendChatMessage(session.session_id, queryText);
      setMessages(prev => [...prev, assistantReply]);
    } catch (err: any) {
      console.error(err);
      if (err.status === 404 && selectedRepoId) {
        console.log("Chat session not found (404). Attempting to recreate session and retry...");
        try {
          const newSess = await api.createChatSession(selectedRepoId);
          setSession(newSess);
          // Retry sending message with the new session ID
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
        content: 'Sorry, I encountered an error communicating with Gitty AI. Please verify your network and LLM provider.',
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Panel Header */}
      <div style={{ padding: '20px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <MessageSquare size={16} style={{ color: '#818cf8' }} />
        <h2 style={{ margin: 0, fontFamily: 'Outfit', fontSize: '1.15rem', fontWeight: 600 }}>Gitty Assistant</h2>
        <span style={{ 
          fontSize: '0.65rem', 
          background: 'rgba(99,102,241,0.2)', 
          color: '#818cf8', 
          padding: '2px 6px', 
          borderRadius: '4px',
          marginLeft: 'auto',
          fontWeight: 600
        }}>ONLINE</span>
      </div>

      {/* Selected Node Context Pill */}
      {selectedNode && (
        <div style={{ 
          padding: '10px 12px', 
          background: 'rgba(99,102,241,0.08)', 
          borderBottom: '1px solid rgba(99,102,241,0.15)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '0.8rem'
        }}>
          <Layers size={14} style={{ color: '#a78bfa' }} />
          <span style={{ color: 'rgba(255,255,255,0.6)' }}>Focused Node:</span>
          <span style={{ color: '#c084fc', fontWeight: 600 }}>{selectedNode.label}</span>
          <span style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.3)', fontStyle: 'italic', marginLeft: 'auto' }}>
            {selectedNode.node_type}
          </span>
        </div>
      )}

      {/* Messages Sandbox */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {messages.map((msg) => {
          const isUser = msg.role === 'user';
          // Filter out the prompt prefix before showing in UI
          const displayContent = isUser 
            ? msg.content.replace(/^\[Selected Node:.*\]\n\n/, '')
            : msg.content;

          return (
            <div key={msg.message_id} style={{
              alignSelf: isUser ? 'flex-end' : 'flex-start',
              maxWidth: '85%',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px'
            }}>
              <div style={{
                background: isUser ? '#312e81' : 'rgba(255,255,255,0.03)',
                border: isUser ? '1px solid #4338ca' : '1px solid rgba(255,255,255,0.05)',
                borderRadius: '12px',
                padding: '10px 14px',
                fontSize: '0.9rem',
                lineHeight: '1.45',
                color: 'rgba(255,255,255,0.9)',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word'
              }}>
                {displayContent}

                {/* Citations references list */}
                {!isUser && msg.citations && msg.citations.length > 0 && (
                  <div style={{ 
                    marginTop: '12px', 
                    paddingTop: '8px', 
                    borderTop: '1px solid rgba(255,255,255,0.05)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px'
                  }}>
                    <span style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.35)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Link size={10} /> SOURCE CITATIONS
                    </span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
                      {msg.citations.map((cit, idx) => (
                        <div 
                          key={idx}
                          onClick={() => onCitationClick(cit.file_path, cit.symbol_name)}
                          style={{
                            fontSize: '0.75rem',
                            background: 'rgba(99, 102, 241, 0.1)',
                            border: '1px solid rgba(99, 102, 241, 0.2)',
                            borderRadius: '4px',
                            padding: '2px 6px',
                            cursor: 'pointer',
                            color: '#a5b4fc',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            transition: 'all 0.15s ease'
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'rgba(99, 102, 241, 0.2)';
                            e.currentTarget.style.borderColor = 'rgba(99, 102, 241, 0.4)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'rgba(99, 102, 241, 0.1)';
                            e.currentTarget.style.borderColor = 'rgba(99, 102, 241, 0.2)';
                          }}
                        >
                          <Code size={10} />
                          {cit.symbol_name ? cit.symbol_name : cit.file_path.split('/').pop()}
                          <ChevronRight size={10} />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <span style={{ 
                fontSize: '0.7rem', 
                color: 'rgba(255,255,255,0.25)', 
                alignSelf: isUser ? 'flex-end' : 'flex-start' 
              }}>
                {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                {!isUser && msg.metadata?.latency_ms && ` (${msg.metadata.latency_ms}ms)`}
              </span>
            </div>
          );
        })}
        {sending && (
          <div style={{ alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.03)', borderRadius: '12px' }}>
            <Sparkles size={14} className="spinning" style={{ color: '#818cf8' }} />
            <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.4)' }}>Gitty is thinking...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <form onSubmit={handleSendMessage} style={{ padding: '12px', borderTop: '1px solid rgba(255,255,255,0.06)', background: '#0e0f15' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <input 
            type="text"
            placeholder="Ask Gitty a question..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            className="glass-input"
            style={{ flex: 1, fontSize: '0.875rem' }}
            disabled={sending}
          />
          <button 
            type="submit" 
            className="glass-btn" 
            style={{ padding: '8px 12px', background: '#6366f1', borderColor: '#818cf8', flexShrink: 0 }}
            disabled={sending}
          >
            <Send size={14} />
          </button>
        </div>
      </form>
    </div>
  );
};
