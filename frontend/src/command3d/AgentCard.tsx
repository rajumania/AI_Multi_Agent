// ---------------------------------------------------------------------------
// Command Center 3D — reusable AgentCard (Phase 3).
//
// The DOM companion to the 3D AgentNode: a compact, self-contained card that
// shows one agent's identity, its live status badge, the latest status message,
// and any STRUCTURED output the backend attached on completion (counts / flags
// only — never raw reasoning). Presentational and pure: it renders exactly what
// it is given, so it works both as an overlay on the WebGL stage and as the
// non-3D fallback when WebGL is unavailable.
// ---------------------------------------------------------------------------

import { STATUS_VISUALS, type DisplayStatus } from './agentStatus';

export interface AgentCardProps {
  title: string;
  subtitle: string;
  accent: string;
  status: DisplayStatus;
  message?: string;
  output?: Record<string, unknown>;
  /** Highlight this card as the currently-focused agent. */
  active?: boolean;
  selected?: boolean;
  onClick?: () => void;
}

function humanizeKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// Render at most a handful of primitive output values as small chips. Objects
// and arrays are skipped (the detail panel in a later phase handles depth).
function outputChips(output: Record<string, unknown> | undefined): Array<{ label: string; value: string }> {
  if (!output) return [];
  const chips: Array<{ label: string; value: string }> = [];
  for (const [key, raw] of Object.entries(output)) {
    if (chips.length >= 4) break;
    let value: string;
    if (typeof raw === 'boolean') value = raw ? 'Yes' : 'No';
    else if (typeof raw === 'number') value = String(raw);
    else if (typeof raw === 'string') value = raw;
    else continue; // skip nested objects/arrays
    chips.push({ label: humanizeKey(key), value });
  }
  return chips;
}

export function AgentCard({ title, subtitle, accent, status, message, output, active, selected, onClick }: AgentCardProps) {
  const visual = STATUS_VISUALS[status];
  const chips = outputChips(output);

  return (
    <div
      onClick={onClick}
      style={{
        position: 'relative',
        background: 'rgba(15, 23, 42, 0.62)',
        border: `1px solid ${selected ? '#ffffff' : (active ? visual.color : 'rgba(148, 163, 184, 0.22)')}`,
        borderLeft: `3px solid ${accent}`,
        borderRadius: '10px',
        padding: '0.7rem 0.8rem',
        boxShadow: selected 
          ? `0 0 12px ${accent}aa, 0 8px 22px rgba(2, 6, 23, 0.5)` 
          : (active ? `0 0 0 1px ${visual.color}55, 0 8px 22px rgba(2, 6, 23, 0.45)` : '0 6px 16px rgba(2, 6, 23, 0.35)'),
        backdropFilter: 'blur(6px)',
        WebkitBackdropFilter: 'blur(6px)',
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
        cursor: onClick ? 'pointer' : 'default',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#e2e8f0', lineHeight: 1.2 }}>{title}</div>
          <div style={{ fontSize: '0.66rem', color: '#94a3b8', marginTop: '0.1rem' }}>{subtitle}</div>
        </div>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.3rem',
            flexShrink: 0,
            fontSize: '0.6rem',
            fontWeight: 800,
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            color: visual.color,
            background: `${visual.color}1f`,
            border: `1px solid ${visual.color}55`,
            borderRadius: '999px',
            padding: '0.16rem 0.45rem',
          }}
        >
          <span
            className={visual.pulse ? 'pulse' : undefined}
            style={{ width: '6px', height: '6px', borderRadius: '50%', background: visual.color, display: 'inline-block' }}
          />
          {visual.label}
        </span>
      </div>

      {message && (
        <div style={{ fontSize: '0.68rem', color: '#cbd5e1', marginTop: '0.5rem', lineHeight: 1.35 }}>{message}</div>
      )}

      {chips.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', marginTop: '0.55rem' }}>
          {chips.map((chip) => (
            <span
              key={chip.label}
              style={{
                fontSize: '0.6rem',
                color: '#e2e8f0',
                background: 'rgba(51, 65, 85, 0.55)',
                border: '1px solid rgba(148, 163, 184, 0.2)',
                borderRadius: '6px',
                padding: '0.14rem 0.4rem',
              }}
            >
              <span style={{ color: '#94a3b8' }}>{chip.label}:</span> <strong style={{ fontWeight: 700 }}>{chip.value}</strong>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
