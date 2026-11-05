import { useState } from 'react';
import { Train, Lock, Eye, EyeOff, ArrowRight, Sparkles } from 'lucide-react';
import { login, register, errorMessage } from '../api';
import './LoginPage.css';

interface Props {
  onLogin: () => void;
  onGuest?: () => void;
  onRecovery?: (purpose: 'verify' | 'reset') => void;
}

export default function LoginPage({ onLogin, onGuest, onRecovery }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [signup, setSignup] = useState(false);
  const [email, setEmail] = useState('');
  const [confirmation, setConfirmation] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (signup) await register(username, email, password, confirmation);
      else await login(username, password);
      onLogin();
    } catch (err: unknown) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* Animated background */}
      <div className="login-bg">
        <div className="bg-orb bg-orb-1" />
        <div className="bg-orb bg-orb-2" />
        <div className="bg-orb bg-orb-3" />
        <div className="train-track">
          <div className="moving-train">
            <Train size={28} />
          </div>
        </div>
      </div>

      <div className="login-container animate-slide-up">
        {/* Logo */}
        <div className="login-logo">
          <div className="logo-icon">
            <Train size={28} strokeWidth={2.5} />
          </div>
          <h1>Rail<span>wise</span></h1>
          <p className="login-subtitle">
            <Sparkles size={14} />
            Your next journey starts here
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="login-form">
          <h2>{signup ? 'Create your account' : 'Welcome back'}</h2>
          <div className="input-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              required
              autoComplete="username"
              maxLength={150}
              autoFocus
            />
          </div>

          {signup && <div className="input-group"><label htmlFor="email">Email</label><input id="email" type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} required maxLength={254}/><small>We’ll send a verification link. Verify your email to enable password recovery.</small></div>}

          <div className="input-group">
            <label htmlFor="password">Password</label>
            <div className="password-wrap">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
                autoComplete={signup ? 'new-password' : 'current-password'}
                maxLength={128}
              />
              <button
                type="button"
                className="eye-btn"
                onClick={() => setShowPassword(!showPassword)}
                aria-label="Toggle password visibility"
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {signup && <div className="input-group"><label htmlFor="confirm-password">Confirm password</label><input id="confirm-password" type="password" autoComplete="new-password" value={confirmation} onChange={e => setConfirmation(e.target.value)} required maxLength={128}/><small>Use at least 8 characters. Avoid common, numeric-only passwords or your username.</small></div>}
          {error && <div className="login-error" role="alert">{error}</div>}

          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? (
              <span className="spinner" />
            ) : (
              <>
                {signup ? 'Create account' : 'Sign In'}
                <ArrowRight size={18} />
              </>
            )}
          </button>
          <button type="button" className="guest-btn" disabled={loading} onClick={() => {setSignup(!signup);setError('');setPassword('');setConfirmation('');}}>{signup ? 'Already registered? Sign in' : 'New to Railwise? Create account'}</button>
          {!signup&&onRecovery&&<><button type="button" className="guest-btn" disabled={loading} onClick={()=>onRecovery('reset')}>Forgot password?</button><button type="button" className="guest-btn" disabled={loading} onClick={()=>onRecovery('verify')}>Resend verification email</button></>}

          {onGuest && (
            <button
              type="button"
              className="guest-btn"
              onClick={onGuest}
            >
              Back to explore trains →
            </button>
          )}
        </form>

        <div className="login-footer">
          <Lock size={12} />
          <span>Independent demo · No real tickets or payments</span>
        </div>
      </div>
    </div>
  );
}
