import { Component, signal, computed } from '@angular/core';
import { RouterLink } from '@angular/router';
import { NavComponent } from '../../shared/components/nav/nav.component';
import { FooterComponent } from '../../shared/components/footer/footer.component';
import { I18nService } from '../../core/i18n/i18n.service';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [RouterLink, NavComponent, FooterComponent],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.css',
})
export class LandingComponent {
  activeTab = signal<'cv' | 'drill' | 'case'>('cv');
  billingCycle = signal<'monthly' | 'halfyearly'>('monthly');
  activeTestimonial = signal(0);

  constructor(public i18n: I18nService) {}

  readonly testimonials = [
    {
      quote: 'The bot caught me bluffing the exit multiple — exactly like my MD did two weeks later. I walked into the super-day genuinely ready.',
      name: 'Marta K.',
      role: 'Associate · M&A',
      tags: ['12 SESSIONS', '8.5 HRS TOTAL', 'STRICT', 'ENGLISH'],
      score: '8.2',
    },
    {
      quote: 'I did three sessions in a week before my Goldman interview. The feedback on my DCF walkthrough was more useful than six months of WSO prep.',
      name: 'James T.',
      role: 'Analyst · Coverage',
      tags: ['7 SESSIONS', '3.5 HRS TOTAL', 'BALANCED', 'ENGLISH'],
      score: '7.8',
    },
    {
      quote: 'Endlich ein Tool das auf Deutsch funktioniert. Die Fragen waren härter als im echten Interview — genau das was ich brauchte.',
      name: 'Lukas W.',
      role: 'Intern · PE',
      tags: ['5 SESSIONS', '153 MIN TOTAL', 'SUPPORTIVE', 'GERMAN'],
      score: '6.9',
    },
    {
      quote: 'I used the knowledge drills every morning for two weeks. My accounting went from a 4 to an 8. The adaptive difficulty actually works.',
      name: 'Priya S.',
      role: 'Analyst · Restructuring',
      tags: ['18 SESSIONS', '14 HRS TOTAL', 'BALANCED', 'ENGLISH'],
      score: '9.1',
    },
  ];

  readonly plans = computed(() => {
    const isHalfYearly = this.billingCycle() === 'halfyearly';
    return [
      {
        name: 'Analyst',
        tier: 'ANALYST · ENTRY',
        price: isHalfYearly ? '€72' : '€15',
        period: isHalfYearly ? '/ 6 months' : '/ month',
        saved: isHalfYearly ? '€18' : null,
        features: [
          { text: '3 CV screens per month', included: true },
          { text: '3 knowledge drills per month', included: true },
          { text: 'Full feedback reports', included: true },
          { text: 'Case studies (not included)', included: false },
        ],
        featured: false,
        cta: 'Start on Analyst',
      },
      {
        name: 'Associate',
        tier: 'ASSOCIATE · FULL ACCESS',
        price: isHalfYearly ? '€168' : '€35',
        period: isHalfYearly ? '/ 6 months' : '/ month',
        saved: isHalfYearly ? '€42' : null,
        features: [
          { text: '15 sessions per month (any type)', included: true },
          { text: 'Full transcript history', included: true },
          { text: 'Limited case studies (1-2, Q2)', included: true },
          { text: 'Priority bot response', included: true },
        ],
        featured: true,
        cta: 'Start on Associate',
      },
      {
        name: 'Managing Director',
        tier: 'MANAGING DIRECTOR · EVERYTHING',
        price: isHalfYearly ? '€312' : '€65',
        period: isHalfYearly ? '/ 6 months' : '/ month',
        saved: isHalfYearly ? '€78' : null,
        features: [
          { text: 'Unlimited sessions', included: true },
          { text: 'All case studies (Q2)', included: true },
          { text: 'Priority processing', included: true },
          { text: 'Full transcript history', included: true },
        ],
        featured: false,
        cta: 'Start on Managing Director',
      },
    ];
  });

  setTab(tab: 'cv' | 'drill' | 'case') {
    this.activeTab.set(tab);
  }

  toggleBilling() {
    this.billingCycle.update(c => c === 'monthly' ? 'halfyearly' : 'monthly');
  }

  setTestimonial(index: number) {
    this.activeTestimonial.set(index);
  }

  nextTestimonial() {
    this.activeTestimonial.update(i => (i + 1) % this.testimonials.length);
  }

  prevTestimonial() {
    this.activeTestimonial.update(i => (i - 1 + this.testimonials.length) % this.testimonials.length);
  }
}
