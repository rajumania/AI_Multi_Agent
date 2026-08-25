import React, { FormEvent, useEffect, useRef, useState } from 'react';
import { Bot, ChevronDown, Loader2, Send, Sparkles, Trash2, X } from 'lucide-react';
import { api, ChatMessage } from '../services/api';

export interface PersonalAssistantOpenRequest {
  id: number;
  prompt?: string;
}

interface PersonalAssistantProps {
  openRequest?: PersonalAssistantOpenRequest;
}

export const PersonalAssistant: React.FC<PersonalAssistantProps> = ({ openRequest }) => {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unread, setUnread] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setUnread(false);
    if (historyLoaded || loadingHistory) return;
    setLoadingHistory(true);
    void api.getChatHistory().then((history) => {
      setMessages(history.messages || []);
      setConversationId(history.conversation_id || undefined);
    }).catch((err: any) => setError(err.message || 'Unable to load assistant history.'))
      .finally(() => { setLoadingHistory(false); setHistoryLoaded(true); });
  }, [open, historyLoaded, loadingHistory]);

  useEffect(() => {
    if (!openRequest) return;
    setOpen(true);
    setError(null);
    if (openRequest.prompt) setDraft(openRequest.prompt);
  }, [openRequest?.id]);

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, open]);

  const send = async () => {
    const message = draft.trim();
    if (!message || loading) return;
    setDraft('');
    setError(null);
    setLoading(true);
    try {
      const reply = await api.sendChatMessage(message, conversationId);
      const now = new Date().toISOString();
      setConversationId(reply.conversation_id);
      setMessages((previous) => [
        ...previous,
        { id: -Date.now(), conversation_id: reply.conversation_id, sender: 'user', message, created_at: now },
        { id: -Date.now() - 1, conversation_id: reply.conversation_id, sender: 'assistant', message: reply.message, created_at: reply.timestamp },
      ]);
      if (!open) setUnread(true);
    } catch (err: any) {
      setError(err.message || 'The assistant is temporarily unavailable.');
    } finally {
      setLoading(false);
    }
  };

  const clear = async () => {
    try {
      await api.clearChatHistory();
      setMessages([]);
      setConversationId(undefined);
      setHistoryLoaded(true);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Unable to clear assistant history.');
    }
  };

  return (
    <div className="personal-assistant-float">
      {open && (
        <section className="personal-assistant-panel" aria-label="CampusFlow AI personal assistant" style={{ width: 'min(360px, calc(100vw - 2rem))', height: 480, display: 'flex', flexDirection: 'column', background: '#fff', border: '1px solid #c7d2fe', borderRadius: 16, boxShadow: '0 18px 45px rgba(15,23,42,.24)', overflow: 'hidden', marginBottom: '.7rem', animation: 'assistant-pop .18s ease-out' }}>
          <header className="personal-assistant-panel-header" style={{ display: 'flex', alignItems: 'center', gap: '.55rem', padding: '.75rem .85rem', color: '#fff', background: 'linear-gradient(135deg,#312e81,#0f766e)' }}>
            <Sparkles size={17} /><div style={{ flex: 1 }}><strong style={{ display: 'block', fontSize: '.82rem' }}>CampusFlow AI</strong><span style={{ fontSize: '.65rem', color: '#c7d2fe' }}>Personal Assistant</span></div>
            <button aria-label="Clear assistant conversation" title="Clear conversation" onClick={() => void clear()} style={{ border: 0, background: 'transparent', color: '#c7d2fe', cursor: 'pointer' }}><Trash2 size={15} /></button>
            <button aria-label="Close assistant" onClick={() => setOpen(false)} style={{ border: 0, background: 'transparent', color: '#fff', cursor: 'pointer' }}><X size={17} /></button>
          </header>
          <div className="personal-assistant-log" role="log" aria-live="polite" style={{ flex: 1, overflowY: 'auto', padding: '.8rem', background: '#f8fafc' }}>
            {loadingHistory && <div style={{ color: '#64748b', fontSize: '.75rem' }}>Loading your conversation…</div>}
            {!loadingHistory && messages.length === 0 && <div style={{ padding: '1rem .35rem', color: '#64748b', fontSize: '.76rem', lineHeight: 1.5 }}><Bot size={21} color="#6366f1" /><p style={{ marginTop: '.45rem' }}>Ask about campus safety, reporting, or your available profile preferences.</p></div>}
            {messages.map((item) => <div key={item.id} style={{ display: 'flex', justifyContent: item.sender === 'user' ? 'flex-end' : 'flex-start', marginBottom: '.6rem' }}><div style={{ maxWidth: '87%', padding: '.55rem .65rem', borderRadius: item.sender === 'user' ? '12px 12px 3px 12px' : '12px 12px 12px 3px', background: item.sender === 'user' ? '#e0e7ff' : '#fff', border: '1px solid #e2e8f0', color: '#1e293b', fontSize: '.76rem', lineHeight: 1.45 }}><div>{item.message}</div><time style={{ display: 'block', marginTop: '.28rem', color: '#94a3b8', fontSize: '.58rem' }}>{new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time></div></div>)}
            {loading && <div style={{ color: '#64748b', fontSize: '.72rem', display: 'flex', gap: '.3rem', alignItems: 'center' }}><Loader2 size={13} className="spin" /> Assistant is thinking…</div>}
            <div ref={endRef} />
          </div>
          {error && <div role="alert" style={{ padding: '.45rem .75rem', color: '#b91c1c', background: '#fef2f2', fontSize: '.68rem' }}>{error}</div>}
      <form onSubmit={(event: FormEvent) => { event.preventDefault(); void send(); }} style={{ display: 'flex', gap: '.4rem', padding: '.65rem', borderTop: '1px solid #e2e8f0', background: '#fff' }}>
            <textarea aria-label="Message CampusFlow AI" value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send(); } }} placeholder="Type a message…" rows={1} style={{ flex: 1, resize: 'none', padding: '.5rem .6rem', border: '1px solid #cbd5e1', borderRadius: 8, font: 'inherit', fontSize: '.76rem' }} />
            <button aria-label="Send message" disabled={!draft.trim() || loading} style={{ border: 0, borderRadius: 8, padding: '0 .65rem', background: '#4f46e5', color: '#fff', cursor: 'pointer', opacity: !draft.trim() || loading ? .5 : 1 }}><Send size={15} /></button>
          </form>
        </section>
      )}
      <button className="personal-assistant-float-button" aria-expanded={open} aria-label={open ? 'Close CampusFlow AI assistant' : 'Open CampusFlow AI assistant'} title={open ? 'Close CampusFlow AI assistant' : 'Open CampusFlow AI assistant'} onClick={() => setOpen((value) => !value)}><Sparkles size={17} /> <span className="sr-only">{open ? 'Close' : 'Open'} CampusFlow AI</span>{unread && <span className="personal-assistant-unread" aria-label="Unread assistant response" />}{open ? <ChevronDown size={14} /> : null}</button>
    </div>
  );
};
