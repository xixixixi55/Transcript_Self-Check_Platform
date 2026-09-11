# <!-- change title -->

workflow_level: 2
lifecycle_status: in-progress
spec_sync_status: pending

## 关联判断

- 候选：<!-- active or archived candidate -->
- 结论：<!-- reuse or create, with behavior-based reason -->

## 1. Implementation

- [ ] 1.1 <!-- concrete implementation task and affected file -->

## 2. Verification and reconciliation

- [ ] 2.1 <!-- focused regression or check -->
- [ ] 2.2 Reconcile the delta with the living spec and record `spec_sync_evidence`
- [ ] 2.3 Run `npm run verify:quick` and `npm run verify:docs:strict -- --change <name>`
