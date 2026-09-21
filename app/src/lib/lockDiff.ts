/**
 * Lock-diff gate — transparent synonym / drift rule.
 *
 * Compare every lock text for the same entity (card paragraph, lock fields,
 * still `lockFromStill`). Identity keywords must not rotate.
 *
 * Rule L1 (rotating synonym): if two lock texts for the same named entity
 * each contain a member of the same synonym group, those members must be
 * identical. `brown` vs `brunette` is red. Canonical form is whatever the
 * character/prop card lock paragraph used first; later hops may not swap it.
 *
 * Groups are explicit lists below — not embeddings, not fuzzy matching.
 */

import { CHARACTER_LOCK_FIELDS, type CapturePack } from "../types.ts";
import { filled } from "./pack.ts";
import { isBlankStill } from "./stills.ts";

export const LOCK_SYNONYM_GROUPS: readonly (readonly string[])[] = [
  ["brown", "brunette", "chestnut"],
  ["blond", "blonde"],
  ["grey", "gray"],
  ["red", "ginger", "auburn", "redhead"],
  ["cloak", "cape"],
  ["tunic", "shirt"],
  ["beard", "goatee"],
];

export type LockText = {
  entityName: string;
  entityKind: "character" | "prop";
  source: string;
  text: string;
};

export type LockDiffProblem = {
  entityName: string;
  group: readonly string[];
  leftSource: string;
  leftToken: string;
  rightSource: string;
  rightToken: string;
  detail: string;
};

const TOKEN_RE = /[a-z0-9]+/gi;

export function tokenizeLock(text: string): string[] {
  return (text.toLowerCase().match(TOKEN_RE) ?? []).filter(Boolean);
}

export function synonymHits(tokens: readonly string[]): { group: readonly string[]; token: string }[] {
  const set = new Set(tokens);
  const hits: { group: readonly string[]; token: string }[] = [];
  for (const group of LOCK_SYNONYM_GROUPS) {
    for (const token of group) {
      if (set.has(token)) hits.push({ group, token });
    }
  }
  return hits;
}

export function collectLockTexts(pack: CapturePack): LockText[] {
  const rows: LockText[] = [];
  for (const card of pack.characters) {
    if (!filled(card.name)) continue;
    if (filled(card.lockParagraph)) {
      rows.push({
        entityName: card.name.trim(),
        entityKind: "character",
        source: "character lock paragraph",
        text: card.lockParagraph,
      });
    }
    for (const field of CHARACTER_LOCK_FIELDS) {
      const value = card[field.key];
      if (!filled(value)) continue;
      if (/^none\b/i.test(value.trim())) continue;
      rows.push({
        entityName: card.name.trim(),
        entityKind: "character",
        source: `character field ${field.label}`,
        text: value,
      });
    }
  }
  for (const card of pack.props) {
    if (!filled(card.name) || !filled(card.lockParagraph)) continue;
    rows.push({
      entityName: card.name.trim(),
      entityKind: "prop",
      source: "prop lock paragraph",
      text: card.lockParagraph,
    });
  }
  for (const card of pack.stills) {
    if (isBlankStill(card) || !filled(card.entity) || !filled(card.lockFromStill)) continue;
    const name = card.entity.trim();
    const kind = pack.characters.some((item) => item.name.trim().toLowerCase() === name.toLowerCase())
      ? "character"
      : pack.props.some((item) => item.name.trim().toLowerCase() === name.toLowerCase())
        ? "prop"
        : null;
    if (!kind) continue;
    rows.push({
      entityName: name,
      entityKind: kind,
      source: `still ${card.role || "card"} · ${name}`,
      text: card.lockFromStill,
    });
  }
  return rows;
}

function sameEntity(a: LockText, b: LockText): boolean {
  return a.entityKind === b.entityKind && a.entityName.trim().toLowerCase() === b.entityName.trim().toLowerCase();
}

export function diffLockTexts(texts: readonly LockText[]): LockDiffProblem[] {
  const problems: LockDiffProblem[] = [];
  for (let i = 0; i < texts.length; i += 1) {
    for (let j = i + 1; j < texts.length; j += 1) {
      const left = texts[i];
      const right = texts[j];
      if (!sameEntity(left, right)) continue;
      const leftHits = synonymHits(tokenizeLock(left.text));
      const rightHits = synonymHits(tokenizeLock(right.text));
      for (const lh of leftHits) {
        const rh = rightHits.find((hit) => hit.group === lh.group);
        if (!rh) continue;
        if (rh.token === lh.token) continue;
        problems.push({
          entityName: left.entityName,
          group: lh.group,
          leftSource: left.source,
          leftToken: lh.token,
          rightSource: right.source,
          rightToken: rh.token,
          detail: `${left.entityName}: rotating synonym ${lh.token} / ${rh.token} (${lh.group.join("/")}) — ${left.source} vs ${right.source}. Same keywords every hop.`,
        });
      }
    }
  }
  return problems;
}

export function lockDiffProblems(pack: CapturePack): LockDiffProblem[] {
  return diffLockTexts(collectLockTexts(pack));
}
