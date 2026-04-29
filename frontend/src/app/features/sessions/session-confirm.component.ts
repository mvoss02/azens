import {
  Component,
  DestroyRef,
  ElementRef,
  OnInit,
  ViewChild,
  computed,
  inject,
  signal,
} from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router, RouterLink } from '@angular/router';
import { environment } from '../../../environments/environment';

// Shape of what session-setup hands off through router state. Kept flat and
// JSON-serialisable — Angular router state is fine with objects but matching
// the /session/start payload means we can forward it verbatim on confirm.
export interface PendingSessionPayload {
  session_type: 'cv_screen' | 'knowledge_drill' | 'case_study';
  cv_id: string | null;
  cv_filename: string | null;
  seniority_level: string;
  language: string;
  duration_minutes: number;
  personality: string;
}

@Component({
  selector: 'app-session-confirm',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './session-confirm.component.html',
  styleUrl: './session-confirm.component.css',
})
export class SessionConfirmComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);

  @ViewChild('selfVideo') selfVideoEl?: ElementRef<HTMLVideoElement>;

  // Payload is captured once on init and never mutated here — any edits go
  // back through session-setup. If missing (someone URL-typed to this page),
  // we redirect out.
  payload = signal<PendingSessionPayload | null>(null);
  isStarting = signal(false);
  errorMessage = signal('');

  // True for the two billing-related 403s the backend can return on
  // /session/start: monthly limit reached, or no/expired subscription.
  // Drives a richer error block in the template that includes a "Manage
  // subscription" CTA pointing at /app/billing. Other errors (verify
  // email, validation) fall through to the plain error box.
  showBillingCta = signal(false);

  // Device-check state. This whole block used to live in session-room's
  // "lobby" view. We pulled it forward so the session is only created AFTER
  // the user has verified their mic actually works — otherwise a broken
  // mic would still eat their monthly quota.
  micPermission = signal<'unknown' | 'granted' | 'denied'>('unknown');
  camPermission = signal<'unknown' | 'granted' | 'denied'>('unknown');
  isCamOn = signal(false);
  micLevel = signal(0); // 0..1 from the AnalyserNode RMS

  // Confirm button stays disabled until the mic is actually available.
  // We intentionally DON'T gate on micLevel > 0 — someone in a quiet room
  // shouldn't be locked out for not speaking. Granted permission is enough
  // confidence that hardware is plugged in and accessible.
  readonly canConfirm = computed(
    () => this.micPermission() === 'granted' && !this.isStarting(),
  );

  // Human-readable labels used in the read-only summary card. Partial<Record>
  // (not plain Record) so TypeScript treats missing keys as `undefined`,
  // making the `?? p.<field>` fallbacks in the template type-correct and
  // silencing Angular's NG8102 nullish-coalescing diagnostic.
  readonly sessionTypeLabels: Partial<Record<string, string>> = {
    cv_screen: 'CV Screening',
    knowledge_drill: 'Knowledge Drill',
    case_study: 'Case Study',
  };
  readonly seniorityLabels: Partial<Record<string, string>> = {
    intern: 'Intern',
    analyst: 'Analyst',
    associate: 'Associate',
    'vp+': 'VP and above',
  };
  readonly languageLabels: Partial<Record<string, string>> = {
    english: 'English',
    german: 'German',
    spanish: 'Spanish',
    italian: 'Italian',
    dutch: 'Dutch',
  };
  readonly personalityLabels: Partial<Record<string, { label: string; desc: string }>> = {
    supportive: { label: 'Supportive', desc: 'Encouraging, patient, helps you showcase your knowledge' },
    balanced:   { label: 'Balanced', desc: 'Fair and professional: probes but doesn\'t pressure' },
    strict:     { label: 'Strict', desc: 'Demanding and thorough: expects precise answers' },
  };

  // Non-reactive plumbing. Kept off the signal graph because these are
  // coarse audio/video resources — changes in them don't need to re-render.
  private mediaStream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private rafId: number | null = null;

  constructor(private http: HttpClient, private router: Router) {}

  ngOnInit(): void {
    // Clean up any device resources when the user navigates away (back,
    // forward, or into the room itself). Without this, AudioContext and
    // MediaStreamTracks leak into the next page.
    this.destroyRef.onDestroy(() => this.stopMedia());

    const state = history.state as { sessionPayload?: PendingSessionPayload };
    if (!state?.sessionPayload) {
      this.router.navigate(['/app/sessions/new']);
      return;
    }
    this.payload.set(state.sessionPayload);

    // Prompt for the mic immediately so the user sees the permission dialog
    // as soon as the page loads. Matches the old lobby behaviour.
    void this.requestMicPermission();
  }

  // ── Device checks ──────────────────────────────────────────────────

  async requestMicPermission(): Promise<void> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.micPermission.set('granted');
      this.attachMicMeter(stream);
      this.mediaStream = this.mediaStream
        ? this.mergeStreams(this.mediaStream, stream)
        : stream;
    } catch {
      this.micPermission.set('denied');
    }
  }

  async requestCamPermission(): Promise<void> {
    // Toggle off if already running — acts as an on/off switch.
    if (this.camPermission() === 'granted' && this.isCamOn()) {
      this.stopCameraTracks();
      this.isCamOn.set(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      this.camPermission.set('granted');
      this.isCamOn.set(true);
      this.mediaStream = this.mediaStream
        ? this.mergeStreams(this.mediaStream, stream)
        : stream;
      // Defer the video attach by one tick so Angular's @if has rendered
      // the <video #selfVideo> element before we bind a stream to it.
      setTimeout(() => {
        if (this.selfVideoEl) {
          this.selfVideoEl.nativeElement.srcObject = stream;
        }
      });
    } catch {
      this.camPermission.set('denied');
    }
  }

  private attachMicMeter(stream: MediaStream): void {
    // Build an AnalyserNode, read time-domain bytes each frame, compute RMS
    // → map to 0..1. Drives the level meter so the user can visually confirm
    // their mic is picking up sound.
    const ctx = new AudioContext();
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    this.audioContext = ctx;

    const buffer = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      analyser.getByteTimeDomainData(buffer);
      let sum = 0;
      for (const b of buffer) {
        const v = (b - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / buffer.length);
      this.micLevel.set(Math.min(1, rms * 4));
      this.rafId = requestAnimationFrame(tick);
    };
    tick();
  }

  private stopCameraTracks(): void {
    this.mediaStream?.getVideoTracks().forEach((t) => t.stop());
    if (this.selfVideoEl) {
      this.selfVideoEl.nativeElement.srcObject = null;
    }
  }

  private mergeStreams(a: MediaStream, b: MediaStream): MediaStream {
    const out = new MediaStream();
    a.getTracks().forEach((t) => out.addTrack(t));
    b.getTracks().forEach((t) => out.addTrack(t));
    return out;
  }

  private stopMedia(): void {
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    this.audioContext?.close().catch(() => {});
    this.audioContext = null;
    this.mediaStream?.getTracks().forEach((t) => t.stop());
    this.mediaStream = null;
  }

  // ── Navigation ─────────────────────────────────────────────────────

  goBack(): void {
    // Pass the current selections BACK to setup as a pre-fill so the user
    // lands on their own settings — not a blank form. They may want to
    // tweak one field, not re-enter everything.
    this.stopMedia();
    const p = this.payload();
    this.router.navigate(['/app/sessions/new'], {
      state: { prefill: p },
    });
  }

  confirm(): void {
    const p = this.payload();
    if (!p || this.isStarting() || !this.canConfirm()) return;

    // This is the moment the session becomes real: Daily room created,
    // Pipecat bot started, session row committed. Everything before this
    // has been client-only — we want exactly one chance to do it right.
    this.isStarting.set(true);
    this.errorMessage.set('');
    this.showBillingCta.set(false);

    // Strip the display-only cv_filename before hitting the backend — the
    // /session/start schema doesn't know about it.
    const apiPayload = {
      session_type: p.session_type,
      cv_id: p.session_type === 'cv_screen' ? p.cv_id : null,
      seniority_level: p.seniority_level,
      language: p.language,
      duration_minutes: p.duration_minutes,
      personality: p.personality,
    };

    // Grab the user's cam choice BEFORE we tear down the stream, so we can
    // pass it to the room. Pipecat starts its own fresh getUserMedia
    // session, so our stream being closed isn't a problem.
    const enableCam = this.isCamOn();
    this.stopMedia();

    this.http
      .post<any>(`${environment.apiUrl}/session/start`, apiPayload)
      .subscribe({
        next: (session) => {
          this.router.navigate(
            ['/app/sessions', session.id, 'room'],
            {
              state: {
                daily_room_url: session.daily_room_url,
                daily_token: session.daily_token,
                enable_cam: enableCam,
              },
            },
          );
        },
        error: (err) => {
          const detail =
            err.error?.detail ?? 'Failed to start session. Please try again.';
          this.errorMessage.set(detail);
          // Detect billing-actionable 403s. Substring match is brittle —
          // if you change the wording in sessions.py (limit reached) or
          // deps.py (subscription required), update these patterns too.
          // The "verify email" 403 deliberately doesn't match — that
          // user goes to /verify, not /billing.
          this.showBillingCta.set(
            err.status === 403 &&
              /limit reached|active subscription/i.test(detail),
          );
          this.isStarting.set(false);
          // Best-effort: re-attach mic so the user's still-visible meter
          // keeps animating when they try again.
          void this.requestMicPermission();
        },
      });
  }
}
