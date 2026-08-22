import React, { useState } from 'react';
import { Shield, Lock, User, Sparkles, AlertCircle } from 'lucide-react';
import { api } from '../services/api';

interface LoginPageProps {
  onLoginSuccess: (user: any, token?: string) => void;
  onNavigateToSignup: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess, onNavigateToSignup }) => {
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) {
      setError('Please fill in all fields.');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const data = await api.login(username, password);
      localStorage.setItem('cf_token', data.token);
      localStorage.setItem('cf_user', JSON.stringify(data.user));
      onLoginSuccess(data.user, data.token);
    } catch (err: any) {
      setError(err.message || 'Invalid username or password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '0.5rem',
      fontFamily: 'Inter, sans-serif'
    }}>
      {/* Background Decorative Elements */}
      <div style={{
        position: 'absolute',
        width: '400px',
        height: '400px',
        background: 'rgba(99, 102, 241, 0.1)',
        filter: 'blur(100px)',
        borderRadius: '50%',
        top: '10%',
        left: '15%',
        pointerEvents: 'none'
      }} />
      <div style={{
        position: 'absolute',
        width: '400px',
        height: '400px',
        background: 'rgba(14, 165, 233, 0.1)',
        filter: 'blur(100px)',
        borderRadius: '50%',
        bottom: '10%',
        right: '15%',
        pointerEvents: 'none'
      }} />

      <div style={{
        background: 'rgba(30, 41, 59, 0.7)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '2.5rem',
        width: '100%',
        maxWidth: '440px',
        boxShadow: '0 20px 40px rgba(0, 0, 0, 0.3)',
        color: '#ffffff',
        zIndex: 10
      }}>
        {/* Header/Logo */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            display: 'inline-flex',
            background: 'linear-gradient(135deg, #6366f1 0%, #0ea5e9 100%)',
            padding: '0.75rem',
            borderRadius: '12px',
            boxShadow: '0 8px 16px rgba(99, 102, 241, 0.3)',
            marginBottom: '1rem'
          }}>
            <Shield size={32} color="#ffffff" />
          </div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, margin: 0, letterSpacing: '-0.025em' }}>
            CAMPUSFLOW AI
          </h2>
          <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '0.35rem' }}>
            Vignan University Emergency Command Center
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid #ef4444',
            borderRadius: '8px',
            padding: '0.75rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.8rem',
            color: '#f87171',
            marginBottom: '1.25rem'
          }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Username Input */}
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.4rem', textTransform: 'uppercase' }}>
              Username
            </label>
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: '#64748b', display: 'flex', alignItems: 'center' }}>
                <User size={16} />
              </div>
              <input
                type="text"
                placeholder="Enter username"
                style={{
                  width: '100%',
                  padding: '0.65rem 0.75rem 0.65rem 2.25rem',
                  background: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  color: '#ffffff',
                  fontSize: '0.875rem',
                  outline: 'none',
                  transition: 'border-color 0.15s ease'
                }}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onFocus={(e) => e.target.style.borderColor = '#6366f1'}
                onBlur={(e) => e.target.style.borderColor = '#334155'}
              />
            </div>
          </div>

          {/* Password Input */}
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.4rem', textTransform: 'uppercase' }}>
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: '#64748b', display: 'flex', alignItems: 'center' }}>
                <Lock size={16} />
              </div>
              <input
                type="password"
                placeholder="••••••••"
                style={{
                  width: '100%',
                  padding: '0.65rem 0.75rem 0.65rem 2.25rem',
                  background: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  color: '#ffffff',
                  fontSize: '0.875rem',
                  outline: 'none',
                  transition: 'border-color 0.15s ease'
                }}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onFocus={(e) => e.target.style.borderColor = '#6366f1'}
                onBlur={(e) => e.target.style.borderColor = '#334155'}
              />
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '0.75rem',
              background: 'linear-gradient(135deg, #6366f1 0%, #0ea5e9 100%)',
              border: 'none',
              borderRadius: '8px',
              color: '#ffffff',
              fontSize: '0.875rem',
              fontWeight: 700,
              cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 12px rgba(99, 102, 241, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.4rem',
              transition: 'opacity 0.15s ease',
              marginTop: '0.5rem'
            }}
            onMouseOver={(e) => e.currentTarget.style.opacity = '0.9'}
            onMouseOut={(e) => e.currentTarget.style.opacity = '1'}
          >
            {loading ? (
              <span>Authenticating...</span>
            ) : (
              <>
                <Sparkles size={16} />
                <span>SIGN IN TO COMMAND CENTER</span>
              </>
            )}
          </button>
        </form>

        {/* Signup Link */}
        <div style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.8rem', color: '#94a3b8' }}>
          New to Vignan Emergency Intel?{' '}
          <span
            onClick={onNavigateToSignup}
            style={{ color: '#38bdf8', fontWeight: 600, cursor: 'pointer', textDecoration: 'underline' }}
          >
            Create an Account
          </span>
        </div>

        {/* Demo Credentials Footer */}
        <div style={{
          marginTop: '1.75rem',
          paddingTop: '1rem',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          fontSize: '0.75rem',
          color: '#64748b',
          textAlign: 'center'
        }}>
          💡 Demo Operator: <strong>admin</strong> / <strong>password123</strong>
        </div>
      </div>
    </div>
  );
};
