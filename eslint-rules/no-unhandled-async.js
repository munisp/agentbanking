/**
 * ESLint rule: no-unhandled-async
 * Detects async functions in routers that lack try/catch error handling.
 */
module.exports = {
  meta: {
    type: "suggestion",
    docs: {
      description: "Require error handling in async router procedures",
      category: "Best Practices",
    },
    messages: {
      noUnhandledAsync:
        "Async function in router should include try/catch for proper error handling.",
    },
    schema: [],
  },
  create(context) {
    const filename = context.getFilename();
    if (!filename.includes("/routers/")) return {};

    return {
      "CallExpression[callee.property.name='query'] > ArrowFunctionExpression[async=true]"(
        node
      ) {
        const body = node.body;
        if (body.type !== "BlockStatement") return;
        const hasTryCatch = body.body.some(
          stmt => stmt.type === "TryStatement"
        );
        if (!hasTryCatch && body.body.length > 3) {
          context.report({ node, messageId: "noUnhandledAsync" });
        }
      },
      "CallExpression[callee.property.name='mutation'] > ArrowFunctionExpression[async=true]"(
        node
      ) {
        const body = node.body;
        if (body.type !== "BlockStatement") return;
        const hasTryCatch = body.body.some(
          stmt => stmt.type === "TryStatement"
        );
        if (!hasTryCatch && body.body.length > 3) {
          context.report({ node, messageId: "noUnhandledAsync" });
        }
      },
    };
  },
};
