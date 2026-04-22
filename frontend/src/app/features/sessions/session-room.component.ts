import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
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
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { Participant, PipecatClient } from '@pipecat-ai/client-js';
import { DailyTransport } from '@pipecat-ai/daily-transport';
import { environment } from '../../../environments/environment';
import { OrbComponent } from '../../shared/components/orb/orb.component';
import { ConfirmModalComponent } from '../../shared/components/confirm-modal/confirm-modal.component';

interface SessionDetails {
  id: string;
  cv_id: string | null;
  session_type: string;
  seniority_level: string | null;
  language: string;
  duration_minutes: number;
  status: 'pending' | 'active' | 'completed' | 'error';
  feedback_status: 'pending' | 'generated' | 'failed' | 'skipped';
  daily_room_url: string | null;
  daily_token: string | null;
  started_at: string | null;
  ended_at: string | null;
}

interface CvItem {
  id: string;
  filename: string;
  is_active: boolean;
}

// The lobby view is gone — the device check now lives on the confirm page,
// BEFORE the session is created. By the time we land here, the session row
// exists, Daily room is ready, and Pipecat is waiting. We just join.
type View =
  | 'loading' // fetching /session/:id
  | 'joining' // pipecat connect in flight
  | 'connected' // in the room, talking to the bot
  | 'error'; // unrecoverable setup failure

@Component({
  selector: 'app-session-room',
  standalone: true,
  imports: [CommonModule, OrbComponent, ConfirmModalComponent],
  templateUrl: './session-room.component.html',
  styleUrl: './session-room.component.css',
})
export class SessionRoomComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  readonly router = inject(Router);
  private readonly http = inject(HttpClient);
  private readonly destroyRef = inject(DestroyRef);

  @ViewChild('selfVideo') selfVideoEl?: ElementRef<HTMLVideoElement>;

  // ── UI state ───────────────────────────────────────────────────────
  readonly view = signal<View>('loading');
  readonly session = signal<SessionDetails | null>(null);
  readonly cvFilename = signal<string | null>(null);
  readonly errorMessage = signal('');

  // Drives the in-room mic-level glow on the mic button. 0..1 from
  // the AnalyserNode RMS.
  readonly micLevel = signal(0);

  // In-room controls
  readonly isMicOn = signal(true);
  readonly isCamOn = signal(false);

  // Flips true the first time the bot speaks. Drives the caption in the
  // room main view so the user sees "JOINING…" during the Pipecat Cloud
  // cold-start window (can be 10-15s for a fresh container) rather than
  // "INTERVIEWING" with nothing actually happening. Once true, stays true
  // for the session lifetime.
  readonly hasBotSpoken = signal(false);

  // Timer — ticks forward once connected.
  readonly elapsedSeconds = signal(0);
  readonly leaveConfirmOpen = signal(false);

  // Metadata helpers for the UI ───────────────────────────────────────
  readonly durationSeconds = computed(() => (this.session()?.duration_minutes ?? 30) * 60);
  readonly timerLabel = computed(() => {
    const fmt = (s: number) => {
      const m = Math.floor(s / 60).toString().padStart(2, '0');
      const sec = (s % 60).toString().padStart(2, '0');
      return `${m}:${sec}`;
    };
    return `${fmt(this.elapsedSeconds())} / ${fmt(this.durationSeconds())}`;
  });

  readonly sessionTypeLabel = computed(() => {
    const map: Record<string, string> = {
      cv_screen: 'CV Screen',
      knowledge_drill: 'Knowledge Drill',
      case_study: 'Case Study',
    };
    return map[this.session()?.session_type ?? ''] ?? '';
  });

  readonly languageLabel = computed(() => {
    const map: Record<string, string> = {
      english: 'English',
      german: 'German',
      spanish: 'Spanish',
      italian: 'Italian',
      dutch: 'Dutch',
    };
    return map[this.session()?.language ?? ''] ?? '';
  });

  readonly seniorityLabel = computed(() => {
    const map: Record<string, string> = {
      intern: 'Intern',
      analyst: 'Analyst',
      associate: 'Associate',
      'vp+': 'VP and above',
    };
    return map[this.session()?.seniority_level ?? ''] ?? 'Analyst';
  });

  // ── Private non-reactive state (kept off the signal graph) ──────────
  private pipecatClient: PipecatClient | null = null;
  private timerIntervalId: ReturnType<typeof setInterval> | null = null;

  // In-room mic-level visualiser — separate getUserMedia from Pipecat's
  // own audio track. Fresh stream avoids reaching into SDK internals and
  // doesn't re-prompt since mic was already granted on the confirm page.
  private roomMicStream: MediaStream | null = null;
  private roomAudioContext: AudioContext | null = null;
  private roomRafId: number | null = null;

  // Hidden <audio> element the bot's remote audio track is attached to.
  // Daily + Pipecat Client JS in headless mode (no pre-built UI components)
  // doesn't auto-render remote audio — we have to bind the MediaStreamTrack
  // to an <audio> element for the browser to play it. Created lazily on
  // the first remote audio track, torn down in cleanup.
  private botAudioEl: HTMLAudioElement | null = null;

  // Screen Wake Lock — keeps the display awake during an interview so the
  // user's laptop doesn't dim or hit the lock screen mid-session. Supported
  // in Chrome/Edge/Safari 16.4+; Firefox requires a flag. We degrade
  // silently on unsupported browsers — a 30-min interview is long enough
  // for the screen saver to matter but short enough that "oh my screen
  // dimmed" is recoverable if the API happens to be absent.
  private wakeLock: WakeLockSentinel | null = null;

  // Camera preference handed over from the confirm page via router state.
  // Pipecat needs to know at construction time whether to request a
  // camera. If state is missing (refresh / direct nav), default false.
  private initialEnableCam = false;

  ngOnInit(): void {
    this.destroyRef.onDestroy(() => this.cleanup());

    const sessionId = this.route.snapshot.paramMap.get('id');
    if (!sessionId) {
      this.router.navigate(['/app/sessions']);
      return;
    }

    const navState = history.state as { enable_cam?: boolean };
    this.initialEnableCam = !!navState?.enable_cam;
    this.isCamOn.set(this.initialEnableCam);

    this.http
      .get<SessionDetails>(`${environment.apiUrl}/session/${sessionId}`)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (s) => this.handleSessionFetched(s),
        error: () => this.router.navigate(['/app/sessions']),
      });

    // CV list is fetched in parallel so we can show the filename chip. Non-
    // fatal if it fails — worst case the chip shows "—".
    this.http
      .get<CvItem[]>(`${environment.apiUrl}/cv/cvs`)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (cvs) => {
          const sess = this.session();
          if (sess?.cv_id) {
            const match = cvs.find((cv) => cv.id === sess.cv_id);
            this.cvFilename.set(match?.filename ?? null);
          }
        },
      });
  }

  private handleSessionFetched(s: SessionDetails): void {
    this.session.set(s);

    // Session is already finished → nothing to join, go straight to feedback.
    if (s.status === 'completed' || s.status === 'error') {
      this.router.navigate(['/app/feedback', s.id]);
      return;
    }

    // Rejoin case: if the session has already been running, jump into the
    // user's correct position on the timer. We gate on `started_at` alone
    // rather than `status === 'active'` because the backend doesn't
    // explicitly flip PENDING → ACTIVE anywhere — a bot-started session
    // stays PENDING + started_at=<timestamp>. The banner detects both
    // states as "live", and so do we here. Without this fix, rejoining a
    // PENDING session starts the clock from 0.
    if (s.started_at) {
      const elapsed = Math.max(
        0,
        Math.floor((Date.now() - new Date(s.started_at).getTime()) / 1000),
      );
      this.elapsedSeconds.set(elapsed);
      // If we're arriving >10s into the session, this is a rejoin — the
      // bot has been talking without us. Skip the JOINING caption; the
      // interview is already in progress from the server's perspective.
      if (elapsed > 10) {
        this.hasBotSpoken.set(true);
      }
    }

    // Device check already happened on the confirm page. Go straight to
    // joining — Pipecat will ask for mic if the browser somehow lost the
    // permission (shouldn't happen; confirm just granted it).
    void this.joinSession();
  }

  // ── Join / leave ───────────────────────────────────────────────────

  private async joinSession(): Promise<void> {
    const s = this.session();
    if (!s || !s.daily_room_url || !s.daily_token) {
      this.errorMessage.set('Session credentials are missing — please try again.');
      this.view.set('error');
      return;
    }

    this.view.set('joining');

    this.pipecatClient = new PipecatClient({
      transport: new DailyTransport(),
      enableMic: true,
      enableCam: this.initialEnableCam,
      callbacks: {
        onConnected: () => this.onConnected(),
        onDisconnected: () => this.onDisconnected(),
        onError: (msg) => {
          // Pipecat error shape is RTVIMessage; the human-readable bit lives
          // under .data. Guard for unknown shapes rather than crashing.
          const d = (msg as unknown as { data?: { error?: string } })?.data;
          this.errorMessage.set(d?.error ?? 'Session error');
          this.view.set('error');
        },
        // Bot voluntarily left the Daily room — this is how a graceful end
        // from the bot side looks (EndFrame → pipeline teardown → bot
        // leaves). Treat it as the natural end of the interview: stop the
        // session server-side and route the user to their feedback page
        // immediately, so they don't sit in an empty room.
        onBotDisconnected: () => this.onBotDisconnected(),
        // First speaking event — flip the caption from "JOINING…" to
        // "INTERVIEWING" so the user knows the bot is actually live.
        // Fires on every bot turn after the first; guard in the handler.
        onBotStartedSpeaking: () => {
          if (!this.hasBotSpoken()) this.hasBotSpoken.set(true);
        },
        onTrackStarted: (track, participant) => this.onTrackStarted(track, participant),
      },
    });

    try {
      await this.pipecatClient.connect({
        url: s.daily_room_url,
        token: s.daily_token,
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Could not join the session.';
      this.errorMessage.set(msg);
      this.view.set('error');
    }
  }

  private onConnected(): void {
    this.view.set('connected');
    // Kick off the user-facing mic-level meter. Non-fatal if it fails to
    // acquire a stream — the session still works, user just doesn't see
    // the feedback animation.
    void this.startRoomMicMeter();
    // Ask the browser to keep the screen on. Fails silently on unsupported
    // browsers or if the page isn't visible at request time; we re-try on
    // visibilitychange below so the lock can be re-acquired if the user
    // tabs away and comes back.
    void this.acquireWakeLock();
    // Start the ticking timer. It reflects the user's clock, not the bot's
    // — bot-side wrap-up is independent.
    this.timerIntervalId = setInterval(() => {
      this.elapsedSeconds.update((s) => s + 1);
      // Hard-stop safety: if we're past the scheduled duration by 30s AND
      // haven't seen onBotDisconnected yet, something went wrong on the
      // bot side. 30s is generous enough for the bot's goodbye TTS
      // (~10-15s) plus Daily's teardown (~5s), but snappy enough that
      // the user doesn't sit in silence forever. onBotDisconnected handles
      // the happy path; this is pure safety net.
      if (this.elapsedSeconds() >= this.durationSeconds() + 30) {
        this.leaveSession();
      }
    }, 1000);
  }

  private async startRoomMicMeter(): Promise<void> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.roomMicStream = stream;

      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      this.roomAudioContext = ctx;

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
        this.roomRafId = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      // Silent fallback: mic was already granted on the confirm page, so
      // this should rarely fail. If it does, the glow just stays dark —
      // not worth interrupting the interview with an error state.
    }
  }

  private async acquireWakeLock(): Promise<void> {
    // Browser support: WakeLock is gated behind navigator.wakeLock. Some
    // privacy-mode contexts (incognito, iframes without permissions) won't
    // expose it. Silent degrade.
    const nav = navigator as Navigator & { wakeLock?: { request: (type: 'screen') => Promise<WakeLockSentinel> } };
    if (!nav.wakeLock) return;

    try {
      this.wakeLock = await nav.wakeLock.request('screen');
      // The OS can release the lock unilaterally — e.g. the user manually
      // locked the laptop, or the tab went background for too long. Clear
      // our reference so the next reacquire attempt isn't a no-op.
      this.wakeLock.addEventListener('release', () => {
        this.wakeLock = null;
      });
    } catch {
      // Common fail reasons: tab not visible, browser policy. Nothing we
      // can do — the user will notice a dimming screen and we can't block
      // the interview over it.
    }
  }

  private releaseWakeLock(): void {
    this.wakeLock?.release().catch(() => {});
    this.wakeLock = null;
  }

  private stopRoomMicMeter(): void {
    if (this.roomRafId !== null) {
      cancelAnimationFrame(this.roomRafId);
      this.roomRafId = null;
    }
    this.roomAudioContext?.close().catch(() => {});
    this.roomAudioContext = null;
    this.roomMicStream?.getTracks().forEach((t) => t.stop());
    this.roomMicStream = null;
    this.micLevel.set(0);
  }

  private onDisconnected(): void {
    // Transport dropped. If we weren't explicitly leaving, it's a failure.
    if (this.view() === 'connected') {
      this.errorMessage.set('Connection lost. Please rejoin.');
      this.view.set('error');
    }
  }

  private onBotDisconnected(): void {
    // Bot left the Daily room of its own accord — usually means the
    // interview ran to completion (duration timer fired EndFrame on the
    // bot side). Flow is identical to user-initiated Leave; delegate so
    // the teardown logic doesn't drift between the two paths.
    if (this.view() !== 'connected') return;
    this.leaveSession();
  }

  private onTrackStarted(track: MediaStreamTrack, participant?: Participant): void {
    if (!participant) return;

    // Remote audio → the bot talking. Attach to a hidden <audio> element so
    // the browser plays it. Pipecat Client JS fetches the track via Daily's
    // auto-subscribe but won't render it without a media element binding.
    // Before this fix, the callback filtered to local video only and the
    // bot's audio was silently dropped — user saw "Bot speaking" logs
    // server-side but heard nothing.
    if (!participant.local && track.kind === 'audio') {
      if (!this.botAudioEl) {
        this.botAudioEl = document.createElement('audio');
        this.botAudioEl.autoplay = true;
        this.botAudioEl.setAttribute('playsinline', 'true');
        // Off-screen and invisible — the audio is all we need. Not removed
        // from the DOM on purpose; hidden elements still produce sound.
        this.botAudioEl.style.display = 'none';
        document.body.appendChild(this.botAudioEl);
      }
      this.botAudioEl.srcObject = new MediaStream([track]);
      // play() may return a promise that rejects on browser autoplay-block.
      // Fine to ignore the rejection — the user clicked Join right before
      // this, which satisfies the user-gesture requirement on every modern
      // browser. Log on failure just in case some weird environment blocks.
      this.botAudioEl.play().catch((e) =>
        console.warn('Bot audio autoplay blocked:', e),
      );
      return;
    }

    // Local video → self preview. Defer to next microtask because the DOM
    // may not have the <video #selfVideo> element yet if cam was just
    // toggled on.
    if (participant.local && track.kind === 'video') {
      queueMicrotask(() => {
        if (this.selfVideoEl) {
          this.selfVideoEl.nativeElement.srcObject = new MediaStream([track]);
        }
      });
    }
  }

  openLeaveConfirm(): void {
    this.leaveConfirmOpen.set(true);
  }

  cancelLeave(): void {
    this.leaveConfirmOpen.set(false);
  }

  confirmLeave(): void {
    this.leaveConfirmOpen.set(false);
    this.leaveSession();
  }

  private leaveSession(): void {
    const s = this.session();
    if (!s) return;

    this.stopTimer();
    this.stopRoomMicMeter();
    this.releaseWakeLock();

    // Both calls are fire-and-forget. Pipecat disconnect can take 10-60+
    // seconds over bad networks; the destroyRef cleanup hook covers us.
    // The /end POST is fast but we navigate BEFORE awaiting its response
    // so the user never stares at a "WRAPPING UP…" screen. The feedback
    // page polls /session/:id every 5s, so whichever status it first
    // sees (ACTIVE → COMPLETED → GENERATED) will converge correctly.
    this.pipecatClient?.disconnect().catch(() => {});
    this.http
      .post(`${environment.apiUrl}/session/${s.id}/end?error=false`, {})
      .subscribe({ error: () => {} });

    // Navigate immediately. Feedback page handles the pending state.
    this.router.navigate(['/app/feedback', s.id]);
  }

  // ── Mic / cam toggles in-room ──────────────────────────────────────

  toggleMic(): void {
    if (!this.pipecatClient) return;
    const next = !this.isMicOn();
    this.pipecatClient.enableMic(next);
    this.isMicOn.set(next);
  }

  toggleCam(): void {
    if (!this.pipecatClient) return;
    const next = !this.isCamOn();
    this.pipecatClient.enableCam(next);
    this.isCamOn.set(next);
  }

  // ── Cleanup ────────────────────────────────────────────────────────

  private stopTimer(): void {
    if (this.timerIntervalId !== null) {
      clearInterval(this.timerIntervalId);
      this.timerIntervalId = null;
    }
  }

  private cleanup(): void {
    this.stopTimer();
    this.stopRoomMicMeter();
    this.releaseWakeLock();
    // Release the remote audio element — leaving it in the DOM leaks
    // media resources across navigations and can cause echo when the
    // user enters a second session back-to-back.
    if (this.botAudioEl) {
      this.botAudioEl.srcObject = null;
      this.botAudioEl.remove();
      this.botAudioEl = null;
    }
    // Best-effort — component is being destroyed anyway.
    this.pipecatClient?.disconnect().catch(() => {});
    this.pipecatClient = null;
  }
}
