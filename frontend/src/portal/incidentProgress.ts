// ---------------------------------------------------------------------------
// Citizen-safe incident progress (Increment 2, requirement #11).
//
// PURE, DOM-FREE. Maps the backend incident `status` to a simplified, five-phase
// public timeline. It deliberately exposes NO internal agent reasoning, tool
// traces, confidence scores, resource IDs, approvals, or per-agent state — only
// a friendly high-level phase a citizen who reported the incident may see.
//
// The citizen incident payload (IncidentRead) never includes ownership metadata
// or agent internals, so this derivation works purely from the public `status`.
// ---------------------------------------------------------------------------

export type PhaseState = 'done' | 'active' | 'todo';

export interface ProgressPhase {
  key: string;
  label: string;
  state: PhaseState;
}

export interface CitizenProgress {
  phases: ProgressPhase[];
  headline: string;
  /** True for rejected/cancelled/failed states — shown as a neutral "on hold". */
  onHold: boolean;
  /** True once the incident is resolved/closed. */
  resolved: boolean;
}

const PHASE_KEYS = ['reported', 'assessed', 'planned', 'dispatched', 'resolved'] as const;

const PHASE_LABELS: Record<(typeof PHASE_KEYS)[number], string> = {
  reported: 'Incident Reported',
  assessed: 'Assessed by Safety Team',
  planned: 'Response Plan Prepared',
  dispatched: 'Responders Dispatched',
  resolved: 'Resolved & Verified',
};

const ACTIVE_HEADLINES = [
  'Your report has been received.',
  'The campus safety team is assessing the situation.',
  'A response plan is being prepared.',
  'Responders are being dispatched to the location.',
];

// Map the raw backend status to the index of the current public phase (0-4).
function currentPhaseIndex(status: string): number {
  switch (status) {
    case 'reported':
      return 0;
    case 'analyzing':
    case 'assessing':
    case 'classified':
      return 1;
    case 'planning':
    case 'response_planning':
    case 'awaiting_approval':
    case 'approved':
    case 'authorized':
      return 2;
    case 'in_progress':
    case 'response_in_progress':
    case 'dispatched':
    case 'monitoring':
      return 3;
    case 'resolved':
    case 'closed':
      return 4;
    default:
      // rejected / cancelled / action_failed / unknown
      return 1;
  }
}

export function citizenProgress(status?: string | null): CitizenProgress {
  const s = (status || '').toLowerCase();
  const resolved = s === 'resolved' || s === 'closed';
  const onHold = s === 'rejected' || s === 'cancelled' || s === 'action_failed';
  const current = currentPhaseIndex(s);

  const phases: ProgressPhase[] = PHASE_KEYS.map((key, i) => {
    let state: PhaseState;
    if (resolved) {
      state = 'done';
    } else if (i < current) {
      state = 'done';
    } else if (i === current) {
      state = 'active';
    } else {
      state = 'todo';
    }
    return { key, label: PHASE_LABELS[key], state };
  });

  let headline: string;
  if (resolved) {
    headline = 'Resolved and verified by campus safety.';
  } else if (onHold) {
    headline = 'On hold — campus safety is reviewing your report.';
  } else {
    headline = ACTIVE_HEADLINES[current] || ACTIVE_HEADLINES[0];
  }

  return { phases, headline, onHold, resolved };
}
