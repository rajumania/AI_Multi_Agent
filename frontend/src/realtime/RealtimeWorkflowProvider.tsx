import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  ReactNode,
} from 'react';
import { buildEventsWsUrl } from '../services/api';
import { LiveEvent } from '../types';
import {
  IncidentWorkflowState,
  RealtimeWorkflowState,
  getActiveWorkflow,
  getIncidentWorkflow,
  initialRealtimeState,
  reduceRealtime,
} from './workflowReducer';

// ---------------------------------------------------------------------------
// RealtimeWorkflowProvider (Phase 2).
//
// Owns ONE WebSocket connection to the EXISTING backend events endpoint
// (`/api/v1/events/ws`, via the shared buildEventsWsUrl helper) and folds every
// real event through the pure `reduceRealtime` reducer. It exposes the derived,
// per-incident agent-workflow state that the 3D command center and any live
// view will render.
//
// This deliberately does NOT create a second WebSocket server or a parallel
// event system — it is one more browser client of the single existing endpoint,
// token-scoped exactly like every other connection. The operator dashboard's
// current inline socket is left untouched; later phases mount this provider
// around the command-center view (which is not rendered at the same time as the
// legacy dashboard), so there is no redundant connection in practice.
//
// The connection is passive: it only reads live events. All state mutations on
// the backend still go through the existing REST APIs.
// ---------------------------------------------------------------------------

type WsStatus = 'CONNECTED' | 'CONNECTING' | 'OFFLINE';

interface RealtimeWorkflowContextValue {
  state: RealtimeWorkflowState;
  wsState: WsStatus;
  /** The incident currently showing live activity (focus target), if any. */
  activeWorkflow: IncidentWorkflowState | undefined;
  /** Look up a specific incident's workflow state. */
  getWorkflow: (incidentId: string | null | undefined) => IncidentWorkflowState | undefined;
  /** The most recent raw event folded in (useful for lightweight subscribers). */
  lastEvent: LiveEvent | null;
}

const RealtimeWorkflowContext = createContext<RealtimeWorkflowContextValue | undefined>(undefined);

export function RealtimeWorkflowProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reduceRealtime, initialRealtimeState());
  const [wsState, setWsState] = useState<WsStatus>('CONNECTING');
  const [lastEvent, setLastEvent] = useState<LiveEvent | null>(null);
  // Latest connection status held in a ref so the effect body never re-runs on
  // status change (mirrors the operator dashboard's proven pattern).
  const disposedRef = useRef(false);

  useEffect(() => {
    disposedRef.current = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let reconnectDelay = 1000;

    const connect = () => {
      if (disposedRef.current) return;
      setWsState('CONNECTING');
      try {
        socket = new WebSocket(buildEventsWsUrl());
      } catch {
        setWsState('OFFLINE');
        reconnectTimer = window.setTimeout(connect, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, 10000);
        return;
      }

      socket.onopen = () => {
        reconnectDelay = 1000;
        setWsState('CONNECTED');
        // Identify this client; the backend ignores the payload but the send
        // keeps parity with the existing dashboard connection.
        try {
          socket?.send('command-center');
        } catch {
          /* non-fatal */
        }
      };

      socket.onerror = () => setWsState('OFFLINE');

      socket.onclose = () => {
        if (disposedRef.current) return;
        setWsState('OFFLINE');
        reconnectTimer = window.setTimeout(connect, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, 10000);
      };

      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data) as LiveEvent;
          dispatch(event);
          setLastEvent(event);
        } catch {
          // Ignore malformed frames; keep the socket alive.
        }
      };
    };

    connect();

    return () => {
      disposedRef.current = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  const value = useMemo<RealtimeWorkflowContextValue>(
    () => ({
      state,
      wsState,
      activeWorkflow: getActiveWorkflow(state),
      getWorkflow: (incidentId) => getIncidentWorkflow(state, incidentId),
      lastEvent,
    }),
    [state, wsState, lastEvent],
  );

  return (
    <RealtimeWorkflowContext.Provider value={value}>
      {children}
    </RealtimeWorkflowContext.Provider>
  );
}

export function useRealtimeWorkflow(): RealtimeWorkflowContextValue {
  const ctx = useContext(RealtimeWorkflowContext);
  if (!ctx) {
    throw new Error('useRealtimeWorkflow must be used within a <RealtimeWorkflowProvider>');
  }
  return ctx;
}
