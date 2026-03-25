/**
 * Sample input/output cases for sanitizeLlmResponse
 * Run with: npx vitest --run src/utils/sanitizeLlmResponse.test.js
 */
import { describe, it, expect } from "vitest";
import {
  sanitizeLlmResponse,
  toPlainText,
  toPlainTextWithLists,
  toPlainTextWithCode,
  passthrough,
} from "./sanitizeLlmResponse";

describe("sanitizeLlmResponse — plain_text mode", () => {
  it("removes bold and headings", () => {
    const input = "**Hello**\n### Summary\n- Item 1\n- Item 2";
    expect(toPlainText(input)).toBe("Hello\nSummary\nItem 1\nItem 2");
  });

  it("strips code fences and keeps inner content", () => {
    const input = '```json\n{"name": "test"}\n```';
    expect(toPlainText(input)).toBe('{"name": "test"}');
  });

  it("removes filler phrases", () => {
    const input = "Sure, here's the response:\nThe answer is 42.";
    expect(toPlainText(input)).toBe("The answer is 42.");
  });

  it("removes blockquotes", () => {
    const input = "> This is a quote\n> continued";
    expect(toPlainText(input)).toBe("This is a quote\ncontinued");
  });

  it("removes horizontal rules", () => {
    const input = "Section 1\n---\nSection 2";
    expect(toPlainText(input)).toBe("Section 1\nSection 2");
  });

  it("removes inline code backticks", () => {
    const input = "Use `print()` to output text.";
    expect(toPlainText(input)).toBe("Use print() to output text.");
  });

  it("removes italic markers", () => {
    const input = "This is *italic* and _also italic_.";
    expect(toPlainText(input)).toBe("This is italic and also italic.");
  });

  it("collapses excessive blank lines", () => {
    const input = "Line 1\n\n\n\nLine 2";
    expect(toPlainText(input)).toBe("Line 1\n\nLine 2");
  });

  it("removes surrounding quotes", () => {
    const input = '"The answer is 42."';
    expect(toPlainText(input)).toBe("The answer is 42.");
  });

  it("converts links to text only", () => {
    const input = "Visit [Google](https://google.com) for more.";
    expect(toPlainText(input)).toBe("Visit Google for more.");
  });

  it("removes strikethrough", () => {
    const input = "~~old text~~ new text";
    expect(toPlainText(input)).toBe("old text new text");
  });

  it("decodes HTML entities", () => {
    const input = "5 &gt; 3 &amp; 2 &lt; 4";
    expect(toPlainText(input)).toBe("5 > 3 & 2 < 4");
  });

  it("unescapes over-escaped sequences", () => {
    const input = "Line 1\\nLine 2\\nLine 3";
    expect(toPlainText(input)).toContain("Line 1");
    expect(toPlainText(input)).toContain("Line 2");
  });

  it("preserves URLs", () => {
    const input = "See https://example.com for details.";
    expect(toPlainText(input)).toContain("https://example.com");
  });

  it("preserves file names", () => {
    const input = "Edit the file config.json to update settings.";
    expect(toPlainText(input)).toContain("config.json");
  });

  it("preserves meaningful numbers", () => {
    const input = "The result is 3.14159 and the count is 42.";
    expect(toPlainText(input)).toContain("3.14159");
    expect(toPlainText(input)).toContain("42");
  });
});

describe("sanitizeLlmResponse — preserve_lists mode", () => {
  it("converts bullets to • format", () => {
    const input = "- Item 1\n- Item 2\n* Item 3";
    const result = toPlainTextWithLists(input);
    expect(result).toContain("• Item 1");
    expect(result).toContain("• Item 2");
    expect(result).toContain("• Item 3");
  });

  it("still removes headings and bold", () => {
    const input = "## Title\n**bold** text\n- item";
    const result = toPlainTextWithLists(input);
    expect(result).toContain("Title");
    expect(result).not.toContain("##");
    expect(result).not.toContain("**");
  });
});

describe("sanitizeLlmResponse — preserve_code mode", () => {
  it("keeps code fence content intact", () => {
    const input = "```python\nprint('hello')\n```";
    const result = toPlainTextWithCode(input);
    expect(result).toContain("print('hello')");
  });
});

describe("sanitizeLlmResponse — json_passthrough mode", () => {
  it("returns JSON completely unchanged", () => {
    const input = '{"key": "value", "num": 42}';
    expect(passthrough(input)).toBe(input);
  });
});

describe("sanitizeLlmResponse — filler phrase removal", () => {
  const fillers = [
    "Certainly! The answer is 42.",
    "Of course! The answer is 42.",
    "Sure, here's the answer: The answer is 42.",
    "Let me help with that. The answer is 42.",
    "Here's the response: The answer is 42.",
    "Here's a summary: The answer is 42.",
    "Absolutely! The answer is 42.",
  ];

  fillers.forEach((input) => {
    it(`strips filler from: "${input.slice(0, 30)}..."`, () => {
      expect(toPlainText(input)).toBe("The answer is 42.");
    });
  });
});

describe("sanitizeLlmResponse — edge cases", () => {
  it("handles empty string", () => {
    expect(sanitizeLlmResponse("")).toBe("");
  });

  it("handles null/undefined gracefully", () => {
    expect(sanitizeLlmResponse(null)).toBe("");
    expect(sanitizeLlmResponse(undefined)).toBe("");
  });

  it("handles already clean text", () => {
    const input = "The sky is blue.";
    expect(toPlainText(input)).toBe("The sky is blue.");
  });

  it("removes unfinished code fence at end", () => {
    const input = "Here is some text\n```";
    expect(toPlainText(input)).toBe("Here is some text");
  });
});
