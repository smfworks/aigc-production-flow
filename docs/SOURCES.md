# Sources

Inline numbers match the 2026-09-17 research pass.

1. [MiniMax-AI/MiniMax-H3](https://github.com/MiniMax-AI/MiniMax-H3) — official weights and `h3-prompt-writing` (`references/base-en.txt`).
2. [joeygambino/MiniMax-H3-Multishot-Workflow](https://huggingface.co/joeygambino/MiniMax-H3-Multishot-Workflow) — last-frame → first-frame chain, `context_pin`, preview shot 1, texture ratchet on long extend-takes.
3. [Kling: character consistency guide](https://kling.ai/blog/ai-character-consistency-guide) — master description, identical keywords, negative/forbidden, reference images.
4. [StudioBinder shot list](https://www.studiobinder.com/blog/shot-list-template-free-download) — scene, shot, description, size, movement, subject.
5. [Pixel Valley: script continuity sheet](https://pixelvalleystudio.com/pmf-articles/script-continuity-sheet-and-other-important-film-production-notes) — what changed; stills of costumes/props; circle takes.
6. [Memento (arXiv 2606.14667)](https://arxiv.org/html/2606.14667v1) — identity grounding vs local continuation.
7. [StoryMem (arXiv 2512.19539)](https://arxiv.org/html/2512.19539v1) — visual memory for multi-shot story.
8. [GroundShot (arXiv 2606.20799)](https://arxiv.org/html/2606.20799v1) — entity-grounded shot scheduling.
9. [FL2VA first/last frame notes](https://minimax3.com/blog/minimax-h3-first-last-frame) — path between stills, not two descriptions; alignment line + one shot.

SMF measured numbers (walls, peaks, 262.846 s join) are from spark-56bc `sigils.jsonl`, published in the Sigils Clearinghouse post. They are not vendor claims.
