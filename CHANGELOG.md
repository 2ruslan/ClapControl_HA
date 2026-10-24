# Changelog

## 1.1.2

- Moved log_level to Supervisor configuration; removed it from the web panel and prevented web saves from changing it.
- Evaluate the strongest attack frame and allow more reverberation/reduced treble at high sensitivity while retaining duration and spectral gates.
- Show the last impulse decision and measured features; add rate-limited DEBUG diagnostics for rejected candidates.
- Corrected the sound meter to use the full 0–1 RMS range.
- Added tests for logging ownership, reverberant claps and rejected sounds. Hardware validation is still required.

## 1.1.1

- Fixed missed claps when PulseAudio delivers multiple PCM frames together: pulse duration, echo rejection and sequences now use the audio sample clock.
- Show maximum RMS/peak over the last second and the actual adaptive RMS threshold to make short claps visible in diagnostics.
- Added regression coverage for buffered audio delivery.

## 1.1.0

- Removed the duplicate Supervisor configuration form; use the Ingress panel for all detector and scene settings.
- Automatically migrate existing settings once and prevent legacy Supervisor options from overwriting panel changes.
- Keep the standard Home Assistant audio device selector.

## 1.0.0

- PulseAudio PCM capture with automatic recovery and bounded buffering.
- Adaptive clap detection, 1–3 clap sequences, echo rejection and cooldown.
- Ordered scene cycles, automatic Supervisor authorization and atomic persistent state.
- Ukrainian mobile-friendly Ingress settings, scene picker, diagnostics and dry-run testing.
- Optional successful-activation events, synthetic PCM tests and installation documentation.
