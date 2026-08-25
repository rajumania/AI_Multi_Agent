import React, { useEffect, useState } from 'react';
import { Cpu, Orbit, ScanLine, Sparkles, X } from 'lucide-react';
import { GENAI_TEAM, GenAITeamMember } from './teamGenAIData';

const positions = ['top-left', 'top-right', 'bottom-left', 'bottom-right'] as const;

export const TeamGenAIShowcase: React.FC = () => {
  const [selectedMember, setSelectedMember] = useState<GenAITeamMember | null>(null);

  useEffect(() => {
    if (!selectedMember) return undefined;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSelectedMember(null);
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [selectedMember]);

  return (
    <>
      <section className="team-genai-showcase" aria-label="GENAI team showcase">
        <div className="team-genai-atmosphere" aria-hidden="true" />
        <div className="team-genai-grid" aria-hidden="true" />
        <div className="team-genai-network" aria-hidden="true">
          <span className="team-genai-network-line team-genai-network-line-a" />
          <span className="team-genai-network-line team-genai-network-line-b" />
          <span className="team-genai-network-line team-genai-network-line-c" />
          <span className="team-genai-network-line team-genai-network-line-d" />
        </div>

        <div className="team-genai-heading">
          <div className="team-genai-kicker"><Sparkles size={13} /> TEAM GENAI <span>•</span> RESPONSE INTELLIGENCE</div>
          <h1>GENAI</h1>
          <p>AI EMERGENCY RESPONSE SYSTEM</p>
        </div>

        <div className="team-genai-orbit" aria-hidden="true">
          <span className="team-genai-orbit-ring team-genai-orbit-ring-one" />
          <span className="team-genai-orbit-ring team-genai-orbit-ring-two" />
          <span className="team-genai-orbit-core"><Cpu size={22} /></span>
        </div>

        {GENAI_TEAM.map((member, index) => (
          <button
            key={member.regNo}
            type="button"
            className={`team-genai-member team-genai-member-${positions[index]}`}
            onClick={() => setSelectedMember(member)}
            aria-label={`View team member ${member.name}, registration number ${member.regNo}`}
          >
            <span className="team-genai-member-signal" aria-hidden="true"><ScanLine size={13} /></span>
            <img className="team-genai-avatar" src={member.photo} alt="" aria-hidden="true" />
            <span className="team-genai-member-copy">
              <strong>{member.name}</strong>
              <small>{member.regNo}</small>
            </span>
            <span className="team-genai-member-label">GENAI NODE 0{index + 1}</span>
          </button>
        ))}

        <div className="team-genai-status" aria-hidden="true">
          <span className="team-genai-status-dot" /> FOUR CONTRIBUTORS <span>•</span> ONE RESPONSE MISSION
        </div>
      </section>

      {selectedMember && (
        <div
          className="team-genai-profile-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setSelectedMember(null);
          }}
        >
          <div className="team-genai-profile" role="dialog" aria-modal="true" aria-labelledby="team-genai-profile-title">
            <button type="button" className="team-genai-profile-close" onClick={() => setSelectedMember(null)} aria-label="Close team member profile">
              <X size={18} />
            </button>
            <div className="team-genai-profile-overline"><Orbit size={14} /> TEAM MEMBER PROFILE</div>
            <img className="team-genai-profile-avatar" src={selectedMember.photo} alt={selectedMember.name} />
            <h2 id="team-genai-profile-title">{selectedMember.name}</h2>
            <p className="team-genai-profile-reg">{selectedMember.regNo}</p>
            <div className="team-genai-profile-team"><span /> GENAI <span /></div>
            <p className="team-genai-profile-note">Contributing to CampusFlow AI emergency-response intelligence.</p>
          </div>
        </div>
      )}
    </>
  );
};
