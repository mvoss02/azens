import { Component, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { I18nService, LANGUAGES, AppLanguage } from '../../../core/i18n/i18n.service';

@Component({
  selector: 'app-nav',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './nav.component.html',
  styleUrl: './nav.component.css',
})
export class NavComponent {
  readonly languages = LANGUAGES;
  langMenuOpen = signal(false);
  // Mobile collapse. Desktop ignores — CSS hides the hamburger + sheet.
  mobileMenuOpen = signal(false);

  constructor(public auth: AuthService, public i18n: I18nService) {}

  scrollTo(id: string) {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    // Close mobile sheet after the user picks a destination — otherwise
    // they'd land at the section with the menu still covering it.
    this.mobileMenuOpen.set(false);
  }

  toggleLangMenu() {
    this.langMenuOpen.update(v => !v);
  }

  selectLang(code: AppLanguage) {
    this.i18n.setLang(code);
    this.langMenuOpen.set(false);
  }

  toggleMobileMenu() {
    this.mobileMenuOpen.update(v => !v);
    // Prevent a stray language dropdown from being visible underneath
    // the sheet. Small tidy-up.
    this.langMenuOpen.set(false);
  }

  closeMobileMenu() {
    this.mobileMenuOpen.set(false);
  }
}
