import {
  AlertCircle,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  ShieldCheck,
  Store,
} from 'lucide-react';
import { motion } from 'motion/react';
import { type FormEvent, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { STORE_INFO } from '../config';
import { TRANSLATIONS } from '../i18n/translations';
import { useLedgerStore } from '../store/useLedgerStore';
import type { LanguageCode } from '../types/domain';

const STORE_PHOTO_SRC = '/src/assets/images/kirana_store_interior_1795154911313.jpg';

export function LandingLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const language = useLedgerStore((s) => s.language);
  const setLanguage = useLedgerStore((s) => s.setLanguage);
  const loginOwner = useLedgerStore((s) => s.loginOwner);

  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [imageFailed, setImageFailed] = useState(false);

  const t = TRANSLATIONS[language];

  const languages: { code: LanguageCode; label: string }[] = [
    { code: 'en', label: 'EN' },
    { code: 'hi', label: 'हिंदी' },
    { code: 'kn', label: 'ಕನ್ನಡ' },
  ];

  const highlights = [
    { index: '01', label: t.landingHighlight1 },
    { index: '02', label: t.landingHighlight2 },
    { index: '03', label: t.landingHighlight3 },
  ];

  const fromPath =
    (location.state as { from?: string } | null)?.from &&
    (location.state as { from?: string } | null)?.from !== '/login'
      ? (location.state as { from?: string }).from!
      : '/';

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    setErrorMsg(null);
    if (!password.trim()) {
      setErrorMsg(t.loginEmptyError);
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await loginOwner(password);
      if (result.ok) {
        setPassword('');
        navigate(fromPath, { replace: true });
      } else if (result.errorCode === 'empty') {
        setErrorMsg(t.loginEmptyError);
      } else {
        setErrorMsg(t.loginInvalidError);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#FAF7EF] text-[#172B22] grid grid-cols-1 lg:grid-cols-12 overflow-x-hidden">
      {/* LEFT SECTION — BRANDING & IDENTITY (Desktop left 7 cols; mobile stacks cleanly) */}
      <section
        aria-label="Trexo store management identity"
        className="relative lg:col-span-7 bg-[#103D2B] text-[#FAF7EF] px-5 py-6 sm:px-10 sm:py-9 lg:px-14 lg:py-12 flex flex-col justify-between gap-6 lg:gap-8 overflow-hidden"
      >
        {/* Subtle Indian architectural lattice texture — ultra-restrained hairline opacity */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-[0.045]"
          style={{
            backgroundImage:
              'radial-gradient(circle at 1px 1px, #C6A15B 1px, transparent 0)',
            backgroundSize: '28px 28px',
          }}
        />

        {/* Top: Logo Wordmark + Mobile Language Switcher */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 flex items-center justify-between gap-4"
        >
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 sm:h-10 sm:w-10 items-center justify-center rounded-xl bg-[#145C3A] border border-[#C6A15B]/55 text-[#FAF7EF] shadow-[inset_0_1px_0_rgba(255,255,255,0.12)]">
              <svg
                viewBox="0 0 24 24"
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M5 7h14" />
                <path d="M12 7v11" />
                <path d="M8.5 18h7" className="stroke-[#C6A15B]" />
              </svg>
            </span>
            <span className="text-lg sm:text-xl font-bold tracking-[0.14em] text-[#FAF7EF] whitespace-nowrap">
              TREXO
            </span>
          </div>

          {/* Mobile language switcher */}
          <div
            className="flex lg:hidden items-center gap-1 rounded-lg bg-[#145C3A]/80 p-1 border border-[#C6A15B]/25"
            role="group"
            aria-label="Display language"
          >
            {languages.map((lang) => (
              <button
                key={lang.code}
                type="button"
                onClick={() => setLanguage(lang.code)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors whitespace-nowrap ${
                  language === lang.code
                    ? 'bg-[#FAF7EF] text-[#103D2B]'
                    : 'text-[#FAF7EF]/80 hover:text-[#FAF7EF]'
                }`}
              >
                {lang.label}
              </button>
            ))}
          </div>
        </motion.div>

        {/* Center: Editorial Copy + Store Photograph + Highlights */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 space-y-5 lg:space-y-6 my-auto"
        >
          <div className="space-y-3 sm:space-y-4 max-w-xl">
            <p className="text-[11px] font-semibold tracking-[0.18em] text-[#C6A15B]">
              {t.landingEyebrow}
            </p>

            <h1 className="text-2xl sm:text-4xl xl:text-[2.85rem] font-bold tracking-tight leading-[1.12] text-[#FAF7EF] text-balance">
              <span className="block">{t.landingHeadlineLine1}</span>
              <span className="block">{t.landingHeadlineLine2}</span>
              <span className="block text-[#C6A15B]">{t.landingHeadlineLine3}</span>
            </h1>

            <p className="text-sm sm:text-[15px] leading-relaxed text-[#FAF7EF]/80 max-w-[54ch]">
              {t.landingSubtitle}
            </p>
          </div>

          {/* Modern Indian Neighborhood Kirana Store Visual */}
          <div className="relative rounded-2xl overflow-hidden border border-[#C6A15B]/25 bg-[#0C2F21] shadow-lg max-w-2xl">
            {imageFailed ? (
              <div className="h-44 sm:h-56 lg:h-auto lg:aspect-video w-full bg-gradient-to-br from-[#145C3A] to-[#0B2A1E] flex flex-col items-center justify-center p-6 text-center">
                <Store className="h-10 w-10 text-[#C6A15B]" />
                <p className="mt-3 text-sm font-semibold text-[#FAF7EF]">{STORE_INFO.shopName}</p>
                <p className="mt-1 text-xs text-[#FAF7EF]/70">{STORE_INFO.location}</p>
              </div>
            ) : (
              <img
                src={STORE_PHOTO_SRC}
                alt="Clean modern Indian neighborhood kirana store shelves stocked with rice, lentils, pulses, and everyday household essentials"
                referrerPolicy="no-referrer"
                onError={() => setImageFailed(true)}
                className="h-44 sm:h-56 lg:h-auto lg:aspect-video w-full object-cover object-center block"
              />
            )}
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-[#103D2B]/80 via-[#103D2B]/25 to-transparent"
            />
            <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between text-xs text-[#FAF7EF]/95">
              <span className="font-medium truncate">{STORE_INFO.shopName}</span>
              <span className="text-[#C6A15B] font-medium whitespace-nowrap shrink-0 ml-3">
                {STORE_INFO.location.split(',')[0]}
              </span>
            </div>
          </div>

          {/* Three Short Product Highlights (clean unboxed typographic layout) */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 pt-2 border-t border-[#FAF7EF]/12 max-w-2xl">
            {highlights.map((item) => (
              <div key={item.index} className="flex sm:flex-col items-baseline gap-2 sm:gap-1">
                <span className="font-mono text-xs font-medium text-[#C6A15B] tabular-nums">
                  {item.index}
                </span>
                <p className="text-sm font-medium text-[#FAF7EF] leading-snug">{item.label}</p>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Bottom Branding */}
        <div className="relative z-10 pt-3 border-t border-[#FAF7EF]/10 flex flex-wrap items-center justify-between gap-2 text-xs text-[#FAF7EF]/65">
          <span>{t.landingFooterNote}</span>
          <span className="text-[#C6A15B]/85">{t.landingSupporting}</span>
        </div>
      </section>

      {/* RIGHT SECTION — OWNER LOGIN PANEL */}
      <section
        aria-label="Store owner sign in"
        className="lg:col-span-5 bg-[#FAF7EF] px-6 py-8 sm:px-10 sm:py-12 lg:px-12 flex flex-col justify-between min-h-[540px] lg:min-h-screen"
      >
        {/* Top utility row on desktop: Language selector */}
        <div className="hidden lg:flex items-center justify-end">
          <div
            className="inline-flex items-center gap-1 rounded-lg bg-[#EFEAE0] p-1"
            role="group"
            aria-label="Display language"
          >
            {languages.map((lang) => (
              <button
                key={lang.code}
                type="button"
                onClick={() => setLanguage(lang.code)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${
                  language === lang.code
                    ? 'bg-white text-[#172B22] shadow-xs'
                    : 'text-[#718078] hover:text-[#172B22]'
                }`}
              >
                {lang.label}
              </button>
            ))}
          </div>
        </div>

        {/* Centered Login Card */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-md mx-auto my-auto py-4"
        >
          <div className="rounded-2xl border border-[#E5DFD2] bg-white p-7 sm:p-9 shadow-[0_12px_40px_-18px_rgba(16,61,43,0.14)]">
            {/* Business Identity Lockup */}
            <div className="flex items-start gap-3.5 pb-6 border-b border-[#EFEAE0]">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#FAF7EF] border border-[#E5DFD2] text-[#145C3A]">
                <Store className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-[#172B22] leading-snug">
                  {STORE_INFO.shopName}
                </p>
                <p className="mt-0.5 text-xs text-[#718078] truncate">{STORE_INFO.location}</p>
              </div>
            </div>

            {/* Welcome Heading */}
            <div className="mt-6 space-y-1.5">
              <h2 className="text-2xl font-bold tracking-tight text-[#172B22]">
                {t.loginWelcome}
              </h2>
              <p className="text-sm text-[#718078]">{t.loginPrompt}</p>
            </div>

            {/* Owner Login Form */}
            <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-5">
              <div className="space-y-2">
                <label
                  htmlFor="store-password"
                  className="block text-xs font-semibold text-[#172B22]"
                >
                  {t.loginPasswordLabel}
                </label>

                <div className="relative">
                  <input
                    id="store-password"
                    name="store-password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    autoFocus
                    disabled={isSubmitting}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (errorMsg) setErrorMsg(null);
                    }}
                    placeholder={t.loginPasswordPlaceholder}
                    aria-invalid={errorMsg ? 'true' : 'false'}
                    aria-describedby={errorMsg ? 'login-error-message' : undefined}
                    className={`w-full rounded-xl border bg-white py-3 pl-4 pr-11 text-sm text-[#172B22] placeholder:text-[#718078]/75 transition-colors focus:outline-none ${
                      errorMsg
                        ? 'border-red-600 focus:border-red-700'
                        : 'border-[#D9D3C5] focus:border-[#145C3A]'
                    }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    disabled={isSubmitting}
                    aria-label={showPassword ? 'Hide store password' : 'Show store password'}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-lg p-2 text-[#718078] hover:bg-[#FAF7EF] hover:text-[#172B22] transition-colors"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>

                {/* Inline Error Feedback */}
                {errorMsg && (
                  <motion.div
                    id="login-error-message"
                    role="alert"
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.18 }}
                    className="flex items-start gap-2 pt-1 text-xs font-medium text-red-700"
                  >
                    <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                    <span>{errorMsg}</span>
                  </motion.div>
                )}
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-[#145C3A] px-5 py-3.5 text-sm font-semibold text-white hover:bg-[#103D2B] active:scale-[0.995] disabled:opacity-75 transition-all whitespace-nowrap"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>{t.loginSigningIn}</span>
                  </>
                ) : (
                  <>
                    <Lock className="h-4 w-4" />
                    <span>{t.loginButton}</span>
                  </>
                )}
              </button>
            </form>

            {/* Private Access Security Note */}
            <div className="mt-6 pt-5 border-t border-[#EFEAE0] flex items-start gap-2.5 text-xs text-[#718078]">
              <ShieldCheck className="h-4 w-4 text-[#237A50] shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <p className="font-medium text-[#172B22]">{t.loginPrivateNote}</p>
                <p className="text-[#718078]">{t.localSavedNote}</p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Quiet Right Footer */}
        <p className="text-center text-xs text-[#718078] mt-6 lg:mt-0">
          Trexo · {STORE_INFO.ownerName}
        </p>
      </section>
    </div>
  );
}
