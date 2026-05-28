/**
 * ESLint rule: no-hardcoded-credentials
 * Detects hardcoded passwords, API keys, and secrets in source code.
 */
module.exports = {
  meta: {
    type: "problem",
    docs: {
      description: "Disallow hardcoded passwords, API keys, and secrets",
      category: "Security",
    },
    messages: {
      hardcodedCred:
        "Possible hardcoded credential detected. Use environment variables instead.",
    },
    schema: [],
  },
  create(context) {
    const PATTERNS = [
      /password\s*[:=]\s*["'][^"']{4,}["']/i,
      /api[_-]?key\s*[:=]\s*["'][^"']{8,}["']/i,
      /secret\s*[:=]\s*["'][^"']{8,}["']/i,
      /token\s*[:=]\s*["'][A-Za-z0-9+/=]{20,}["']/i,
    ];

    const ALLOW_LIST = [
      "password",
      "changeme",
      "test",
      "example",
      "placeholder",
      "your-",
      "xxx",
      "***",
    ];

    return {
      Literal(node) {
        if (typeof node.value !== "string") return;
        const parent = node.parent;
        if (!parent) return;

        const src = context.getSourceCode().getText(parent);
        const isMatch = PATTERNS.some(p => p.test(src));
        if (!isMatch) return;

        const isAllowed = ALLOW_LIST.some(a =>
          node.value.toLowerCase().includes(a)
        );
        if (isAllowed) return;

        context.report({ node, messageId: "hardcodedCred" });
      },
    };
  },
};
