// ---------------------------------------------------------------------------
// Command Center 3D — lazy entry point (Phase 3).
//
// This is the ONLY module the operator shell imports directly. It code-splits
// the heavy 3D view (three.js) behind React.lazy so the main bundle — and the
// login/signup path — never pays for it (Rules 24–26). A Suspense fallback
// covers the chunk load, and an error boundary degrades gracefully if the chunk
// fails to load or the 3D view throws, so the command center is never bricked.
// ---------------------------------------------------------------------------

import { Component, Suspense, lazy, type ReactNode } from 'react';
import type { CommandCenter3DProps } from './CommandCenter3D';

// Dynamic import => separate chunk. three.js is pulled in only when this runs.
const CommandCenter3D = lazy(() => import('./CommandCenter3D'));

function CenteredNote({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '360px',
        color: 'var(--text-secondary)',
        fontSize: '0.85rem',
        gap: '0.6rem',
      }}
    >
      {children}
    </div>
  );
}

class CommandCenterBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    // eslint-disable-next-line no-console
    console.warn('[command3d] failed to load 3D command center', error);
  }

  render() {
    if (this.state.failed) {
      return (
        <CenteredNote>
          The 3D command center could not be loaded. Live agent status is still available in the other tabs.
        </CenteredNote>
      );
    }
    return this.props.children;
  }
}

export function CommandCenter3DLazy(props: CommandCenter3DProps) {
  return (
    <CommandCenterBoundary>
      <Suspense
        fallback={
          <CenteredNote>
            <span className="spin" style={{ width: '16px', height: '16px', border: '2px solid rgba(148,163,184,0.4)', borderTopColor: 'var(--primary-600)', borderRadius: '50%', display: 'inline-block' }} />
            Loading 3D command center…
          </CenteredNote>
        }
      >
        <CommandCenter3D {...props} />
      </Suspense>
    </CommandCenterBoundary>
  );
}
