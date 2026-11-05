# Accessibility evidence

Implemented: semantic landmarks/navigation, skip link, labeled search, native radios, visible focus, responsive layout, live result status, readable errors, source text rendered as text, document-heading focus and restoration on back. Aborted search responses cannot replace newer results.

Automated evidence: VERIFICATION.md. Playwright covers keyboard search/modes/source/back, races, mobile overflow, and axe on initial/results/evaluation/mobile views. This is not full WCAG certification.

## Manual VoiceOver — pending
Reviewer/date/device/browser: pending. No manual pass claimed.
- [ ] Navigate landmarks, navigation, and headings.
- [ ] Find query label, type, submit without a pointer.
- [ ] Confirm selected modes and unavailable descriptions are announced.
- [ ] Verify useful completion/count announcements without excess repetition.
- [ ] Open result; focus should move to document heading.
- [ ] Go back; focus should return to originating result.
- [ ] Read complete text and attribution.
- [ ] Trigger/recover from an error.
- [ ] Navigate comparison and table row/column headings.
- [ ] Check 200% text zoom and 400% page zoom.
- [ ] Record findings, corrections, and retest.
