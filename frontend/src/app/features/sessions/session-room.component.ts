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

type View =
  | 'loading' // fetching /session/:id
  | 'lobby' // asking permissions, showing pre-join summary
  | 'joining' // pipecat connect in flight
  | 'connected' // in the room, talking to the bot
  | 'ending' // user hit Leave, disconnect in flight
  | 'error'; // unrecoverable setup failure

@Component({
  selector: 'app-session-room',
  standalone: true,
  imports: [CommonModule, OrbComponent],
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

  // Permission state. camPermission stays 'unknown' until the user clicks
  // the camera toggle — we only ask for the prompt on demand, matching the
  // "camera is optional" product decision.
  readonly micPermission = signal<'unknown' | 'granted' | 'denied'>('unknown');
  readonly camPermission = signal<'unknown' | 'granted' | 'denied'>('unknown');

  // Drives the lobby mic-meter. 0..1 from the AnalyserNode RMS.
  readonly micLevel = signal(0);

  // In-room controls
  readonly isMicOn = signal(true);
  readonly isCamOn = signal(false);

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
  private lobbyMediaStream: MediaStream | null = null;
  private lobbyAudioContext: AudioContext | null = null;
  private lobbyRafId: number | null = null;
  private timerIntervalId: ReturnType<typeof setInterval> | null = null;

  ngOnInit(): void {
    this.destroyRef.onDestroy(() => this.cleanup());

    const sessionId = this.route.snapshot.paramMap.get('id');
    if (!sessionId) {
      this.router.navigate(['/app/sessions']);
      return;
    }

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

    // Rejoin case: the bot is still running on the backend. Skip the lobby
    // and drop the user straight into the room — their clock's already
    // ticking and we don't want them wasting interview time on permissions.
    if (s.status === 'active' && s.started_at) {
      const elapsed = Math.max(
        0,
        Math.floor((Date.now() - new Date(s.started_at).getTime()) / 1000),
      );
      this.elapsedSeconds.set(elapsed);
      this.joinSession({ skipLobby: true });
      return;
    }

    // Fresh join — show the lobby, ask for mic upfront.
    this.view.set('lobby');
    this.requestMicPermission();
  }

  // ── Lobby: permissions, meter, preview ─────────────────────────────

  async requestMicPermission(): Promise<void> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.micPermission.set('granted');
      this.attachLobbyMicMeter(stream);
      this.lobbyMediaStream = this.lobbyMediaStream
        ? this.mergeStreams(this.lobbyMediaStream, stream)
        : stream;
    } catch {
      this.micPermission.set('denied');
    }
  }

  async requestCamPermission(): Promise<void> {
    // Toggle off if already running.
    if (this.camPermission() === 'granted' && this.isCamOn()) {
      this.stopLobbyCameraTracks();
      this.isCamOn.set(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      this.camPermission.set('granted');
      this.isCamOn.set(true);
      this.lobbyMediaStream = this.lobbyMediaStream
        ? this.mergeStreams(this.lobbyMediaStream, stream)
        : stream;
      // Wait a tick for the @if to render the <video> element before binding.
      setTimeout(() => {
        if (this.selfVideoEl) {
          this.selfVideoEl.nativeElement.srcObject = stream;
        }
      });
    } catch {
      this.camPermission.set('denied');
    }
  }

  private attachLobbyMicMeter(stream: MediaStream): void {
    // Build an AnalyserNode → read time-domain data each frame → compute RMS
    // → map to 0..1. This drives the meter bar in the lobby so users can
    // verify their mic is actually picking up sound.
    const ctx = new AudioContext();
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    this.lobbyAudioContext = ctx;

    const buffer = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      analyser.getByteTimeDomainData(buffer);
      // RMS around 128 (silent). Scale to 0..1 with some headroom.
      let sum = 0;
      for (const b of buffer) {
        const v = (b - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / buffer.length);
      this.micLevel.set(Math.min(1, rms * 4));
      this.lobbyRafId = requestAnimationFrame(tick);
    };
    tick();
  }

  private stopLobbyCameraTracks(): void {
    this.lobbyMediaStream?.getVideoTracks().forEach((t) => t.stop());
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

  // ── Join / leave ───────────────────────────────────────────────────

  async joinSession(opts: { skipLobby?: boolean } = {}): Promise<void> {
    const s = this.session();
    if (!s || !s.daily_room_url || !s.daily_token) {
      this.errorMessage.set('Session credentials are missing — please try again.');
      this.view.set('error');
      return;
    }

    // From lobby, release the preview streams — Pipecat will grab its own.
    if (!opts.skipLobby) {
      this.stopLobbyMedia();
    }

    this.view.set('joining');

    this.pipecatClient = new PipecatClient({
      transport: new DailyTransport(),
      enableMic: true,
      enableCam: this.isCamOn(),
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
    // Start the ticking timer. It reflects the user's clock, not the bot's
    // — bot-side wrap-up is independent.
    this.timerIntervalId = setInterval(() => {
      this.elapsedSeconds.update((s) => s + 1);
      // Hard-stop safety: if we're somehow past the zombie deadline with no
      // bot-side end, the room stops counting. The backend will auto-end
      // the session on the next /session/:id read.
      if (this.elapsedSeconds() >= this.durationSeconds() + 60) {
        this.leaveSession();
      }
    }, 1000);
  }

  private onDisconnected(): void {
    // Transport dropped. If we weren't explicitly leaving, it's a failure.
    if (this.view() === 'connected') {
      this.errorMessage.set('Connection lost. Please rejoin.');
      this.view.set('error');
    }
  }

  private onTrackStarted(track: MediaStreamTrack, participant?: Participant): void {
    // Only local video — we don't render bot video yet (Phase B / future).
    if (!participant?.local || track.kind !== 'video') return;
    // DOM may not have the <video #selfVideo> element yet if cam was just
    // toggled on; defer to next tick so change detection has rendered it.
    queueMicrotask(() => {
      if (this.selfVideoEl) {
        this.selfVideoEl.nativeElement.srcObject = new MediaStream([track]);
      }
    });
  }

  openLeaveConfirm(): void {
    this.leaveConfirmOpen.set(true);
  }

  cancelLeave(): void {
    this.leaveConfirmOpen.set(false);
  }

  async confirmLeave(): Promise<void> {
    this.leaveConfirmOpen.set(false);
    await this.leaveSession();
  }

  private async leaveSession(): Promise<void> {
    const s = this.session();
    if (!s) return;

    this.view.set('ending');
    this.stopTimer();

    try {
      await this.pipecatClient?.disconnect();
    } catch {
      // Non-fatal — server-side end call below is what matters.
    }

    this.http
      .post(`${environment.apiUrl}/session/${s.id}/end?error=false`, {})
      .subscribe({
        next: () => this.router.navigate(['/app/feedback', s.id]),
        error: () => this.router.navigate(['/app/feedback', s.id]),
      });
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

  private stopLobbyMedia(): void {
    if (this.lobbyRafId !== null) {
      cancelAnimationFrame(this.lobbyRafId);
      this.lobbyRafId = null;
    }
    this.lobbyAudioContext?.close().catch(() => {});
    this.lobbyAudioContext = null;
    this.lobbyMediaStream?.getTracks().forEach((t) => t.stop());
    this.lobbyMediaStream = null;
  }

  private cleanup(): void {
    this.stopTimer();
    this.stopLobbyMedia();
    // Best-effort — component is being destroyed anyway.
    this.pipecatClient?.disconnect().catch(() => {});
    this.pipecatClient = null;
  }
}
