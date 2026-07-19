---
name: commerce-video-director
description: Use when private_tenant needs competitor commerce-video analysis, shot-by-shot breakdowns, AI video prompts, storyboards, editing plans, template selection, music licensing checks, CapCut handoff, or creative QA for Amazon, TikTok Shop, B2B apparel, POD, DTG or DTF content.
---

# Commerce Video Director

## Workflow

1. Identify platform, country/site, product, audience, conversion objective and available product facts.
2. Analyze user-provided or public competitor evidence. Separate observed facts from inference.
3. Record technical structure: duration, aspect ratio, resolution, fps, audio, cut times and keyframes.
4. Break down hook, shots, camera, lighting, product actions, captions, edit rhythm, music role, proof, CTA and comment buying signals.
5. Distill reusable structure. Never copy trademarks, people, dialogue, protected scenes or unlicensed audio.
6. Generate an original storyboard and prompt pack that preserves product color, material, quantity, fit and other verified facts.
7. Select an editing template, subtitle safe area and licensed music source.
8. Handoff to CapCut or another approved editor, then review product accuracy, continuity, text fit, audio rights and CTA.
9. Put public upload, creator outreach and ad spend into the approval queue.

## Tool Order

- Use `ai_ecommerce_director.creative_video` for local metadata, scene cuts, keyframes and prompt packs.
- Use the installed CapCut bridge for manual editing.
- Treat PySceneDetect, whisper.cpp and librosa as isolated pilots only.
- Treat Remotion and OpenCut as design references until license and runtime gates pass.

## Required Output

- Evidence source and capture time
- Observed technical facts
- Shot timeline with timestamps
- Hook/proof/CTA analysis
- Reusable pattern and prohibited-copy list
- Original storyboard
- Generation prompt and negative prompt
- Edit, subtitle and music plan
- Three test variants
- Approval boundary

Use `config/creative_video_capabilities.json` as the canonical schema and template registry.
