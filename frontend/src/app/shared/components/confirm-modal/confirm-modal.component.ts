import { Component, EventEmitter, HostListener, Input, Output, ViewEncapsulation } from '@angular/core';

/**
 * Shared confirm-action modal. Promoted from settings / cvs / sessions after
 * the third copy of the same HTML+CSS appeared.
 *
 * Usage:
 *
 *   <app-confirm-modal
 *     [isOpen]="cvPendingDelete() !== null"
 *     title="Delete this CV?"
 *     confirmText="Yes, delete CV"
 *     confirmLoadingText="Deleting…"
 *     [loading]="isDeleting()"
 *     [errorMessage]="deleteError()"
 *     (cancel)="cancelDeleteCv()"
 *     (confirm)="confirmDeleteCv()"
 *   >
 *     <p>You're about to delete <strong>{{ cv.filename }}</strong>.</p>
 *     <p class="modal-emphasis">This cannot be undone.</p>
 *   </app-confirm-modal>
 *
 * Body content goes through <ng-content>. Classes inside projected content
 * (e.g. `.modal-emphasis`) are styled by this component's stylesheet so the
 * caller doesn't re-implement them.
 */
@Component({
  selector: 'app-confirm-modal',
  standalone: true,
  templateUrl: './confirm-modal.component.html',
  styleUrl: './confirm-modal.component.css',
  // Emulated (default) encapsulation would scope styles away from projected
  // body content — projected <p> tags get the CALLER's ngcontent attribute,
  // so modal CSS selectors targeting `p` wouldn't match. ViewEncapsulation.None
  // lifts that scoping; we compensate by prefixing every selector with
  // `.modal-card` or `.modal-backdrop` so they only match inside THIS modal.
  encapsulation: ViewEncapsulation.None,
})
export class ConfirmModalComponent {
  @Input() isOpen = false;
  @Input() title = 'Are you sure?';
  @Input() confirmText = 'Confirm';
  @Input() cancelText = 'Cancel';

  // Shown on the confirm button while `loading` is true. Falls back to
  // confirmText if not set.
  @Input() confirmLoadingText: string | null = null;

  // Disables both buttons and swaps the confirm label for confirmLoadingText.
  // Set true while the underlying action is in flight.
  @Input() loading = false;

  // Inline red error strip shown between body and actions. null/empty hides.
  @Input() errorMessage: string | null = null;

  // Optional red emphasis line rendered directly below the body content.
  // Used for "This cannot be undone." across every caller — promoted to
  // an input so callers don't have to duplicate the <p class="modal-emphasis">
  // markup or its CSS.
  @Input() emphasisText: string | null = null;

  // Primary action styling. 'danger' = red destructive button (the default
  // since every caller so far is a delete). 'primary' = amber action.
  @Input() confirmStyle: 'danger' | 'primary' = 'danger';

  @Output() cancel = new EventEmitter<void>();
  @Output() confirm = new EventEmitter<void>();

  onBackdropClick(): void {
    this.emitCancel();
  }

  onCancelClick(): void {
    this.emitCancel();
  }

  onConfirmClick(): void {
    if (this.loading) return;
    this.confirm.emit();
  }

  // Escape-to-cancel. Matches the native <dialog> behaviour users expect.
  // Listener on the component itself (not document) so it only fires while
  // the modal is open and focus is within it.
  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (!this.isOpen) return;
    this.emitCancel();
  }

  private emitCancel(): void {
    if (this.loading) return; // Block dismiss mid-request
    this.cancel.emit();
  }
}
