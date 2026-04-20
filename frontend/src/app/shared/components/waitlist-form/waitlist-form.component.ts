import { Component, Input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../../environments/environment';
import { I18nService } from '../../../core/i18n/i18n.service';

type FormState = 'idle' | 'submitting' | 'success' | 'error';

@Component({
  selector: 'app-waitlist-form',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './waitlist-form.component.html',
  styleUrl: './waitlist-form.component.css',
})
export class WaitlistFormComponent {
  // `source` records WHERE the signup came from (e.g. 'case_studies',
  // 'footer'). User-facing copy is intentionally broader — product updates
  // list — so we don't lock ourselves into emailing people only about the
  // specific feature they signed up near.
  @Input({ required: true }) source!: string;

  email = signal('');
  state = signal<FormState>('idle');
  errorMessage = signal('');

  constructor(private http: HttpClient, public i18n: I18nService) {}

  submit(): void {
    // Guard against double-submit and re-submits after success.
    if (this.state() === 'submitting' || this.state() === 'success') return;

    const email = this.email().trim();
    if (!this.isValidEmail(email)) {
      this.state.set('error');
      this.errorMessage.set(this.i18n.t('waitlist.error.invalid_email'));
      return;
    }

    this.state.set('submitting');
    this.errorMessage.set('');

    this.http
      .post(`${environment.apiUrl}/waitlist/join`, {
        email,
        source: this.source,
        language: this.i18n.backendValue(),
      })
      .subscribe({
        next: () => this.state.set('success'),
        error: (err) => {
          this.state.set('error');
          this.errorMessage.set(
            err.error?.detail ?? this.i18n.t('waitlist.error.generic'),
          );
        },
      });
  }

  // HTML5 `type="email"` catches most bad input at the browser level, but
  // we still validate in TS because the server is authoritative and users
  // can paste/autofill past the browser check.
  private isValidEmail(email: string): boolean {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }
}
