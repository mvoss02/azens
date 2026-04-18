import { Injectable, signal, computed } from '@angular/core';

export type AppLanguage = 'en' | 'de' | 'es' | 'it' | 'nl';

export interface LangOption {
  code: AppLanguage;
  label: string;
  backendValue: string; // matches your Language enum values
}

export const LANGUAGES: LangOption[] = [
  { code: 'en', label: 'EN', backendValue: 'english' },
  { code: 'de', label: 'DE', backendValue: 'german' },
  { code: 'es', label: 'ES', backendValue: 'spanish' },
  { code: 'it', label: 'IT', backendValue: 'italian' },
  { code: 'nl', label: 'NL', backendValue: 'dutch' },
];

const STORAGE_KEY = 'azens_lang';

@Injectable({ providedIn: 'root' })
export class I18nService {
  private _lang = signal<AppLanguage>(this.loadLang());

  readonly lang = this._lang.asReadonly();
  readonly backendValue = computed(() =>
    LANGUAGES.find(l => l.code === this._lang())?.backendValue ?? 'english'
  );

  setLang(code: AppLanguage): void {
    this._lang.set(code);
    localStorage.setItem(STORAGE_KEY, code);
  }

  t(key: string): string {
    const lang = this._lang();
    return translations[lang]?.[key] ?? translations['en'][key] ?? key;
  }

  private loadLang(): AppLanguage {
    const stored = localStorage.getItem(STORAGE_KEY) as AppLanguage | null;
    if (stored && LANGUAGES.some(l => l.code === stored)) return stored;
    return 'en';
  }
}

// ── Translation strings ──────────────────────────────────────────────────────
// All languages default to English for now.
// To translate: copy the 'en' block, change the values.

type TranslationMap = Record<string, string>;

const en: TranslationMap = {
  // Nav
  'nav.product': 'Product',
  'nav.testimonials': 'Testimonials',
  'nav.pricing': 'Pricing',
  'nav.faq': 'FAQ',
  'nav.signin': 'Sign in',
  'nav.getstarted': 'Get started',
  'nav.dashboard': 'Dashboard',
  'nav.logout': 'Log out',

  // Hero
  'hero.tag': 'Voice mock interviews for IB & PE',
  'hero.title': 'Practice the interview that gets you the',
  'hero.title.em': 'offer.',
  'hero.sub': 'Azens runs realistic voice mock interviews for investment banking and private equity candidates. Trained on your CV, tuned to your seniority, with a full feedback report after every session.',
  'hero.cta.primary': 'Get started',
  'hero.cta.secondary': '▶ Listen to a sample',
  'hero.trust.cancel': 'Cancel anytime',
  'hero.trust.gdpr': 'GDPR · EU-hosted',
  'hero.trust.langs': 'EN · DE · ES · IT · NL',

  // Product section
  'product.kicker': 'The product',
  'product.title': 'Five tools. One',
  'product.title.em': 'goal.',
  'product.side': 'Two equal pillars — CV screening and knowledge drills — both powered by a voice AI that sounds real, both followed by a detailed report. Plus case studies coming Q2.',

  // Feature 1
  'feature1.num': '01',
  'feature1.meta': 'Voice AI interviewer',
  'feature1.title': 'Talk to an interviewer that sounds',
  'feature1.title.em': 'real.',
  'feature1.desc': 'A low-latency voice agent that interrupts, probes and pushes back. Not a chatbot typing replies — an actual voice on the other end of the call.',
  'feature1.li1': 'Natural conversation — interrupts and follow-ups',
  'feature1.li2': 'Session length: 15 · 30 · 45 · 60 · 90 min',
  'feature1.li3': 'Personality modes: strict · balanced · supportive',
  'feature1.li4': 'Available in EN · DE · ES · IT · NL',
  'feature1.cta': 'See how it sounds',

  // Feature 2
  'feature2.num': '02',
  'feature2.meta': 'CV screening',
  'feature2.title': 'Defend your deal sheet, line by',
  'feature2.title.em': 'line.',
  'feature2.desc': 'Upload your CV, and the bot reads every deal, every metric, every internship. It then drills you exactly like a senior banker would.',
  'feature2.li1': 'Auto-parses deals, valuations and metrics',
  'feature2.li2': 'Seniority-aware: Intern → Analyst → Associate → VP+',
  'feature2.li3': 'Personal info stripped before any AI call',
  'feature2.cta': 'Upload a CV',

  // Feature 3
  'feature3.num': '03',
  'feature3.meta': 'Knowledge drills',
  'feature3.title': 'Technicals,',
  'feature3.title.em': 'drilled',
  'feature3.title.after': 'until they stick.',
  'feature3.desc': 'Rapid-fire questions across DCF, LBO, M&A, accounting and valuation. Difficulty climbs as you get them right.',
  'feature3.li1': '500+ questions across 5 core IB & PE topics',
  'feature3.li2': 'Adaptive difficulty 1 → 3, tuned to your answers',
  'feature3.li3': 'Per-topic score breakdown after every drill',
  'feature3.cta': 'Run a drill',

  // Feature 4
  'feature4.num': '04',
  'feature4.meta': 'Detailed feedback',
  'feature4.title': 'A feedback report you can',
  'feature4.title.em': 'actually',
  'feature4.title.after': 'act on.',
  'feature4.desc': 'Every session ends with a structured report. Scored across four categories — not a vibe check. Specific strengths, specific weaknesses, exact timestamps from the transcript.',
  'feature4.li1': 'Scored on communication, technical accuracy, structure, confidence',
  'feature4.li2': 'Transcript quoted inline with the exact moments that cost you points',
  'feature4.li3': 'Three personalised drills auto-queued for tomorrow',
  'feature4.cta': 'See a sample report',

  // Feature 5
  'feature5.num': '05',
  'feature5.meta': 'Coming Q2 2026',
  'feature5.title': 'Excel case studies,',
  'feature5.title.em': 'presented',
  'feature5.title.after': 'to the AI.',
  'feature5.desc': 'Pull a real Excel-based case from a pool of dozens — LBO, M&A, DCF, merger models. Work through it offline, then present to the AI interviewer.',
  'feature5.cta': 'Join the waitlist',

  // Testimonials
  'testimonials.kicker': 'From real candidates',
  'testimonials.title': 'They practised. They',
  'testimonials.title.em': 'landed it.',

  // Pricing
  'pricing.kicker': 'Pricing',
  'pricing.title': 'Pick your',
  'pricing.title.em': 'seat.',
  'pricing.side': 'Plans named after the jobs you\'re training for. Cancel any time.',
  'pricing.monthly': 'Monthly',
  'pricing.halfyearly': '6 months',
  'pricing.save': 'Save 20%',

  // FAQ
  'faq.kicker': 'FAQ',
  'faq.title': 'Questions,',
  'faq.title.em': 'answered.',
  'faq.side': 'Need more? The team replies within the day.',

  // CTA
  'cta.title': 'Start practising',
  'cta.title.em': 'today.',
  'cta.sub': 'Pick your plan, upload your CV, and run your first session in under five minutes. Cancel any time.',
  'cta.primary': 'Get started',
  'cta.secondary': 'See pricing',

  // Auth
  'auth.login.title': 'Welcome back',
  'auth.login.sub': 'Sign in to your Azens account',
  'auth.signup.title': 'Create your account',
  'auth.signup.sub': 'Start practising for your IB & PE interviews',
};

// All other languages fall back to English for now.
// To translate German: const de: TranslationMap = { ...en, 'hero.title': 'Übe das Interview...', ... };
const de: TranslationMap = { ...en };
const es: TranslationMap = { ...en };
const it: TranslationMap = { ...en };
const nl: TranslationMap = { ...en };

const translations: Record<AppLanguage, TranslationMap> = { en, de, es, it, nl };
