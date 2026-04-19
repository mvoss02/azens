import { Component, input } from '@angular/core';

/**
 * Amber gradient sphere representing the AI interviewer.
 *
 * Used on the landing product cards and in the session room. Size is
 * input-driven so the same component scales from a card preview (~130px)
 * up to a full session-room centrepiece (~260px+).
 *
 * Phase A: static pulsing animation (no audio-reactivity).
 * Phase B will add bot-state variants (listening / thinking / speaking)
 * driven by Pipecat events — that's why this is a component and not
 * just a reusable CSS class.
 */
@Component({
  selector: 'app-orb',
  standalone: true,
  templateUrl: './orb.component.html',
  styleUrl: './orb.component.css',
})
export class OrbComponent {
  /** Diameter in pixels. Defaults to the landing card size. */
  readonly size = input<number>(130);
}
