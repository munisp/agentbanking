/**
 * ESLint rule: no-raw-sql
 * Detects sql.raw() usage that may be vulnerable to SQL injection.
 * Encourages parameterized queries instead.
 */
module.exports = {
  meta: {
    type: "problem",
    docs: {
      description: "Disallow sql.raw() in favor of parameterized queries",
      category: "Security",
    },
    messages: {
      noRawSql:
        "Avoid sql.raw(). Use parameterized queries or sql`...` tagged templates instead.",
    },
    schema: [],
  },
  create(context) {
    return {
      CallExpression(node) {
        if (
          node.callee.type === "MemberExpression" &&
          node.callee.object.name === "sql" &&
          node.callee.property.name === "raw"
        ) {
          context.report({ node, messageId: "noRawSql" });
        }
      },
    };
  },
};
