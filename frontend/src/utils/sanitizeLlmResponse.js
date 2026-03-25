/**
 * LLM Response Sanitization Utility
 * ===================================
 * Cleans up raw LLM output before displaying in the UI.
 *
 * Modes:
 *   plain_text      — strip all markdown, normalize whitespace (default)
 *   preserve_lists  — strip markdown but keep list structure
 *   preserve_code   — strip markdown but keep code fence content
 *   json_passthrough — return as-is (no destructive changes)
 *
 * Usage:
 *   import { sanitizeLlmResponse } from "../utils/sanitizeLlmResponse";
 *   const clean = sanitizeLlmResponse(rawText);
 *   const clean = sanitizeLlmResponse(rawText, { mode: "preserve_lists" });
 *   const clean = sanitizeLlmResponse(rawText, { removeFillerPhrases: false });
 */

// ── Filler phrases the LLM commonly prepends ─────────────────────────────────
const FILLER_PHRASES = [
  /^sure[,!.]?\s*(here'?s?|i'?ll|let me).*?[:!]\s*/i,
  /^certainly[,!.]?\s*/i,
  /^of course[,!.]?\s*/i,
  /^absolutely[,!.]?\s*/i,
  /^great[,!.]?\s*(here'?s?|let me).*?[:!]\s*/i,
  /^here'?s?\s+(the|a|your|an)?\s*(response|answer|result|summary|cleaned|updated|revised).*?[:!]\s*/i,
  /^let me (help|assist|explain|break).*?[:!]\s*/i,
  /^i'?d? ?(be )?happy to.*?[:!]\s*/i,
  /^no problem[,!.]?\s*/i,
  /^thanks for (asking|your question)[,!.]?\s*/i,
];

// ── Default options ───────────────────────────────────────────────────────────
const DEFAULTS = {
  mode: "plain_text",           // plain_text | preserve_lists | preserve_code | json_passthrough
  removeMarkdown: true,
  removeCodeFences: true,
  preserveLists: false,
  collapseWhitespace: true,
  removeFillerPhrases: true,
  decodeEntities: true,
};

// ── Main export ───────────────────────────────────────────────────────────────
export function sanitizeLlmResponse(text, options = {}) {
  if (!text || typeof text !== "string") return text ?? "";

  const opts = { ...DEFAULTS, ...options };

  // Mode shortcuts
  if (opts.mode === "json_passthrough") return text;
  if (opts.mode === "preserve_lists")  opts.preserveLists = true;
  if (opts.mode === "preserve_code")   opts.removeCodeFences = false;

  let out = text;

  // 1. Decode HTML entities
  if (opts.decodeEntities) out = decodeEntities(out);

  // 2. Unescape over-escaped sequences
  out = unescapeOverEscaped(out);

  // 3. Strip code fences (keep inner content)
  if (opts.removeCodeFences) out = stripCodeFences(out);

  // 4. Remove markdown formatting
  if (opts.removeMarkdown) out = stripMarkdown(out, opts.preserveLists);

  // 5. Remove filler phrases from the start
  if (opts.removeFillerPhrases) out = stripFillerPhrases(out);

  // 6. Normalize whitespace
  if (opts.collapseWhitespace) out = normalizeWhitespace(out);

  // 7. Remove trailing artifacts
  out = removeTrailingArtifacts(out);

  return out.trim();
}

// ── Step implementations ──────────────────────────────────────────────────────

function decodeEntities(text) {
  return text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ");
}

function unescapeOverEscaped(text) {
  return text
    .replace(/\\n/g, "\n")
    .replace(/\\t/g, "\t")
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'")
    // stray backslashes not part of a valid escape
    .replace(/\\([^\\ntr"'`*_#[\](){}|])/g, "$1");
}

function stripCodeFences(text) {
  // ```lang\n...content...\n``` → content
  return text.replace(/```[\w]*\n?([\s\S]*?)```/g, (_, inner) => inner.trim());
}

function stripMarkdown(text, preserveLists) {
  let out = text;

  // Headings: ### Heading → Heading
  out = out.replace(/^#{1,6}\s+(.+)$/gm, "$1");

  // Bold+italic: ***text*** or ___text___
  out = out.replace(/\*{3}(.+?)\*{3}/g, "$1");
  out = out.replace(/_{3}(.+?)_{3}/g, "$1");

  // Bold: **text** or __text__
  out = out.replace(/\*{2}(.+?)\*{2}/g, "$1");
  out = out.replace(/_{2}(.+?)_{2}/g, "$1");

  // Italic: *text* or _text_  (not inside words)
  out = out.replace(/(?<!\w)\*(.+?)\*(?!\w)/g, "$1");
  out = out.replace(/(?<!\w)_(.+?)_(?!\w)/g, "$1");

  // Inline code: `code`
  out = out.replace(/`([^`]+)`/g, "$1");

  // Blockquotes: > text
  out = out.replace(/^>\s?/gm, "");

  // Horizontal rules: ---, ***, ___
  out = out.replace(/^[-*_]{3,}\s*$/gm, "");

  // Strikethrough: ~~text~~
  out = out.replace(/~~(.+?)~~/g, "$1");

  // Links: [text](url) → text
  out = out.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");

  // Images: ![alt](url) → alt
  out = out.replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1");

  // Bullet list markers
  if (!preserveLists) {
    // - item, * item, • item at line start
    out = out.replace(/^[\s]*[-*•]\s+/gm, "");
    // Numbered lists: 1. item → item
    out = out.replace(/^[\s]*\d+\.\s+/gm, "");
  } else {
    // Normalize bullets to a consistent "• " format
    out = out.replace(/^[\s]*[-*•]\s+/gm, "• ");
    out = out.replace(/^[\s]*\d+\.\s+/gm, (m) => m); // keep numbered as-is
  }

  // Surrounding quotes (LLM sometimes wraps entire response in "...")
  out = out.replace(/^"([\s\S]+)"$/, "$1");
  out = out.replace(/^'([\s\S]+)'$/, "$1");

  return out;
}

function stripFillerPhrases(text) {
  let out = text.trim();
  for (const pattern of FILLER_PHRASES) {
    out = out.replace(pattern, "");
  }
  return out.trim();
}

function normalizeWhitespace(text) {
  return text
    // Collapse 3+ consecutive blank lines to 2
    .replace(/\n{3,}/g, "\n\n")
    // Remove trailing spaces on each line
    .replace(/[ \t]+$/gm, "")
    // Collapse multiple spaces (not newlines) to single space
    .replace(/[ \t]{2,}/g, " ");
}

function removeTrailingArtifacts(text) {
  return text
    // Orphaned trailing colon on its own line
    .replace(/:\s*$/gm, (m, offset, str) => {
      // Only remove if it's the very last non-empty line
      const after = str.slice(offset + m.length).trim();
      return after === "" ? "" : m;
    })
    // Duplicate punctuation: "!!" → "!", ".." → "." (but not "...")
    .replace(/([!?])\1+/g, "$1")
    .replace(/\.{2}(?!\.)/g, ".")
    // Unfinished markdown fence at end
    .replace(/```\s*$/g, "");
}

// ── Convenience wrappers ──────────────────────────────────────────────────────

/** Strip everything — plain readable text */
export const toPlainText = (text) =>
  sanitizeLlmResponse(text, { mode: "plain_text" });

/** Keep list structure, strip other markdown */
export const toPlainTextWithLists = (text) =>
  sanitizeLlmResponse(text, { mode: "preserve_lists" });

/** Keep code fence content, strip other markdown */
export const toPlainTextWithCode = (text) =>
  sanitizeLlmResponse(text, { mode: "preserve_code" });

/** Pass JSON through untouched */
export const passthrough = (text) =>
  sanitizeLlmResponse(text, { mode: "json_passthrough" });
