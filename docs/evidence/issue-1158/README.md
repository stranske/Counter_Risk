# Issue1158 validation

Registered FCM and clearing-house aliases now share canonical limit keys across breach and missing-entity checks. Segment/custom-group policy names retain raw normalization. Caps, registry data and concentration math are unchanged.

The focused compute/config/registry/full-pipeline suite passes273tests (32slow deselected). The committed serialized original-helper control yields4assertion failures and restored4PASS. The real pipeline control independently fails under the original helper because strict policy cannot find cme, then passes after byte-identical restoration; it compares canonical, alias-only and split-alias CSV bytes plus actual manifest breach counts.

Raw console, valid JUnit, control argv and file/evidenceSHA256bindings are retained here. See manifest.json. The changed helper is compute/limits.py, not the unchanged parser named by the issue break hint. Hosted CI/review/merge/verifier and source acceptance remain pending.
