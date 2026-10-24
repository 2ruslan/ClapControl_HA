# Changelog

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
